import os

from delta_rest_client import DeltaRestClient

from OTApp.Logger.Logger import AppLogger


class DeltaExchangeConfiguration:
    BASE_URL = 'https://api.india.delta.exchange'
    API_VERSION = 'v2'
    CLIENT = None
    API_KEY = None
    API_KEY = os.getenv('delta_api_key')
    API_SECRET = os.getenv('delta_api_secret')
    # 1. Initialize Client
    try:
        CLIENT = DeltaRestClient(
            base_url=BASE_URL,
            api_key=API_KEY,
            api_secret=API_SECRET
        )
    except Exception as e:
        # A 'catch-all' for any other unexpected errors
        AppLogger.logger.error(f"An unexpected error occurred: {e} while Delta exchange connectivity")
    else:
        AppLogger.logger.info(f"Success! Connection with Delta Exchange")


def client():
    return DeltaExchangeConfiguration.CLIENT


def API_KEY():
    return DeltaExchangeConfiguration.API_KEY


def API_SECRET():
    return DeltaExchangeConfiguration.API_SECRET


def BASE_URL():
    return DeltaExchangeConfiguration.BASE_URL
