import time
from typing import Dict, Any, Optional

import requests
from google.auth import api_key

from OTApp.Configuration import DeltaExchangeConfiguration, Enums
from OTApp.Configuration.Enums import RequestMethod
from OTApp.Security.APIRequestSecurityManager import APIRequestSecurityManager


class RequestManager:
    # API Settings
    ORDER_CHECK_INTERVAL = 2
    ORDER_TIMEOUT = 60
    POSITION_CHECK_RETRIES = 5
    API_RETRY_DELAY = 2
    MAX_API_RETRIES = 3

    def __init__(self, logger):
        self.logger = logger
        self.api_key = DeltaExchangeConfiguration.API_KEY()
        self.api_secret = DeltaExchangeConfiguration.API_SECRET()
        self.base_url = DeltaExchangeConfiguration.BASE_URL()
        self.api_version = DeltaExchangeConfiguration.API_VERSION()
        self.url_with_version = self.base_url + self.api_version

    def api_request(self, api_req_method: RequestMethod, api_context_path: str, payload: dict[str, Any],
                    query_params: Dict = None, retry_count: int = 0) -> Dict:
        """
        Make authenticated API request to Delta Exchange with retry logic.

        :param api_req_method:
        :param api_context_path:
        :param payload:
        :param query_params:
        :param retry_count:
        :return:
        """
        api_path = f"{self.api_version}{api_context_path}"
        try:
            self.logger.debug(f"API Request Method: {api_req_method}")
            url = f"{self.url_with_version}{api_context_path}"
            query_string = ''
            if query_params:
                query_string = '?' + '&'.join([f"{k}={v}" for k, v in query_params.items()])
            # TODO : look like we should return only header instead of signature, timestamp
            signature, timestamp = APIRequestSecurityManager().build_payload_signature(api_path, api_req_method.name,
                                                                                       query_string,
                                                                                       payload)
            headers = {
                'api-key': self.api_key,
                'timestamp': timestamp,
                'signature': signature,
                'User-Agent': 'OTApp',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            self.logger.debug(f"API Request: {api_req_method} {api_path} {query_string}")
            response = requests.request(
                api_req_method.value,
                url,
                json=payload,
                params=query_params or {},
                timeout=(3, 27),
                headers=headers
            )
            response_data = response.json()
            if not response_data.get('success') and retry_count < RequestManager.MAX_API_RETRIES:
                self.logger.warning(
                    f"API request failed, retrying... (Attempt {retry_count + 1}/{RequestManager.MAX_API_RETRIES})")
                time.sleep(RequestManager.API_RETRY_DELAY)
                return self.api_request(api_req_method, api_path, payload, query_params, retry_count + 1)

            return response_data

        except requests.exceptions.Timeout as e:
            self.logger.error(f"API request timeout: {str(e)}")
            if retry_count < RequestManager.MAX_API_RETRIES:
                time.sleep(RequestManager.API_RETRY_DELAY)
                return self.api_request(api_req_method, api_path, payload, query_params, retry_count + 1)
            return {'success': False, 'error': {'message': f'Timeout after {RequestManager.MAX_API_RETRIES} retries'}}
        except Exception as e:
            self.logger.error(f"Unexpected error in API request: {str(e)}", exc_info=True)
            return {'success': False, 'error': {'message': str(e)}}

    def get_ticker_price(self, symbol: str) -> Optional[float]:
        """Get current mark price via REST API."""
        try:
            response = self.api_request(api_req_method=RequestMethod.GET, api_context_path=f'/tickers/{symbol}')
            if response.get('success'):
                result = response.get('result', {})
                mark_price = result.get('mark_price')
                if mark_price:
                    return float(mark_price)
            return None
        except Exception as e:
            self.logger.error(f"Exception in get_ticker_price_rest: {str(e)}", exc_info=True)
            return None
