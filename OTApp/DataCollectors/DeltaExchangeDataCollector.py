# Fetch all products for BTC daily options
import time
from datetime import datetime, timedelta
from pprint import pprint

import requests

from OTApp.Logger.Logger import AppLogger


class DataCollector:
    BASE_URL = 'https://api.india.delta.exchange/v2'
    CE_PE_URL = BASE_URL + '/tickers'
    # Automatically get today's date in DD-MM-YYYY format
    today = datetime.now().strftime("%d-%m-%Y")

    # today = (datetime.now() + timedelta(days=1)).strftime("%d-%m-%Y")

    def fetch_btc_options(today):
        # Public endpoint for all products
        headers = {
            'Accept': 'application/json'
        }
        params = {
            "contract_types": "call_options,put_options",
            "underlying_asset_symbols": 'BTC',
            "expiry_date": today
        }

        r = requests.get(
            DataCollector.CE_PE_URL,
            params=params, headers=headers)

        # pprint(r.json())

        if r.ok and r.status_code == 200:
            return r

    def get_candles(self, symbol, resolution, limit):
        candles = []
        try:
            # 1. Fetch the last 24 hours of 1h candles
            # Resolution: Supported intervals include 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 1d
            # Note: 'get_candles' parameters vary by SDK version,
            # but 'resolution' and 'limit' are standard.
            # 1. Setup Timestamps (Last 24 hours)
            end_time = int(time.time())
            start_time = end_time - (limit * 3600)  # 24 hours ago
            # 2. Public REST Call (No API Key Required)
            url = DataCollector().BASE_URL + "/history/candles"
            params = {
                'symbol': symbol,
                'resolution': resolution,
                'start': start_time,
                'end': end_time
            }
            response = requests.get(url, params=params)
            if response.ok:
                candles = response.json().get('result', [])
                AppLogger.logger.info(f"Fetched {len(candles)} candles.")
            else:
                pass
        except Exception as e:
            AppLogger.logger.error(f"⚠️ Fetching {resolution} candle of  {symbol} has  Error: {e}")
        return candles

    def get_ticker(self, symbol):
        headers = {
            'Accept': 'application/json'
        }
        params = {
            "symbol": symbol
        }
        try:
            r = requests.get(DataCollector.BASE_URL + '/tickers/' + symbol, params={}, headers=headers)
            if r.ok:
                pprint(r.json())
            else:
                pass
        except Exception as e:
            AppLogger.logger.error(f"⚠️ Fetching {symbol} ticker has  Error: {e}")


# DataCollector().get_ticker('BTCUSD')
