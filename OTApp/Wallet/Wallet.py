import hashlib
import hmac
import time

import requests

from OTApp.Configuration import DeltaExchangeConfiguration
from OTApp.Logger.Logger import AppLogger


class Wallet:
    def getBalances(self):
        # Configuration
        PATH = '/v2/wallet/balances'

        # 1. Generate the Timestamp (Unix seconds)
        timestamp = str(int(time.time()))

        # 2. Create the Signature Payload
        # Format: method + timestamp + path + query_string + body
        method = 'GET'
        query_string = ''  # Empty for this request
        payload = method + timestamp + PATH + query_string

        # 3. Sign the payload using HMAC-SHA256
        signature = hmac.new(
            (str(DeltaExchangeConfiguration.API_SECRET())).encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # 4. Set Headers
        headers = {
            'Accept': 'application/json',
            'api-key': DeltaExchangeConfiguration.API_KEY(),
            'signature': signature,
            'timestamp': timestamp
        }
        # 5. Make the Request
        try:
            response = requests.get(DeltaExchangeConfiguration.BASE_URL() + PATH, headers=headers)
            assets_records = response.json()
            if response.ok:
                # Find the first dictionary that matches the asset_id=12
                return self.get_usd_balance(assets_records)
            else:
                AppLogger.logger.error(f"{response.status_code} : {assets_records}")
        except BaseException as bEx:
            AppLogger.logger.error(f"Error fetching margin {bEx} for USD")

    def get_usd_balance(self, assets_records):
        asset_id = 14  # USD balance
        balance = 0
        for record in assets_records.values():
            if isinstance(record, list):
                assets_records = record
                break
        if assets_records:
            # 2. Now run the 'next' logic on the actual list
            usd_record = next((asset for asset in assets_records if asset.get('asset_id') == asset_id), None)
            if usd_record:
                balance = float(usd_record.get('balance'))
                AppLogger.logger.info(f"Success! Asset ID {asset_id} balance is: {balance}")
            else:
                AppLogger.logger.warning(f"Asset ID {asset_id} not found in the list.")
        else:
            AppLogger.logger.error("Could not find a list inside the assets_records dictionary.")
        return balance
