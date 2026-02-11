import logging
import os

import pytz


class Config:
    # --- GLOBAL TOGGLE ---
    # Change to 'PROD' when running on your server
    ENV = 'DEV'

    # --- STRATEGY SETTINGS ---
    STRATEGIES = ["15_Delta", "Scalp_BTC"]

    # --- TELEGRAM SETTINGS ---
    TG_TOKEN = os.getenv('tg_softashu_bot')
    TG_CHAT_ID = os.getenv('tg_chat_id')

    # -------Time Zone ----------
    TIME_ZONE = pytz.timezone('Asia/Kolkata')

    @property
    def LOG_LEVEL(self):
        return logging.DEBUG if self.ENV == 'DEV' else logging.INFO

    @property
    def SHOW_CONSOLE(self):
        # Always show console in DEV, maybe hide in PROD to save resources
        return True if self.ENV == 'DEV' else False

    @property
    def ENABLE_TELEGRAM(self):
        # Only send pings to phone in PROD to avoid spamming during testing
        return True  # if self.ENV == 'PROD' else False
