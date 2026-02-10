import logging

import requests

from OTApp.Configuration.AppConfig import Config


class TelegramHandler(logging.Handler):
    TG_TOKEN = Config.TG_TOKEN
    CHAT_ID = Config.TG_CHAT_ID

    def __init__(self):
        super().__init__()

    def emit(self, record):
        # Format the log message
        log_entry = self.format(record)
        prefix = "ℹ️ INFO"
        if record.levelno == logging.ERROR:
            prefix = "⚠️ <b>ERROR</b>"
        elif record.levelno == logging.CRITICAL:
            prefix = "💰 <b>CRITICAL | TRADE</b>"
        message = f"{prefix}\n<pre>{log_entry}</pre>"
        # Telegram API URL
        url = f"https://api.telegram.org/bot{self.TG_TOKEN}/sendMessage"

        # Send the message

        payload = {
            "chat_id": int(self.CHAT_ID),
            "text": f"<b>⚠️ *Trading Alert* ⚠️ </b> "
                    f" \n<pre>{message}</pre>",
            "parse_mode": "HTML"  # Switch to HTML from "parse_mode": "Markdown"
        }
        try:
            response = requests.post(url, data=payload, timeout=10)
            if response.status_code != 200:
                print(f"Telegram Error {response.status_code}: {response.text}")
            else:
                print("Telegram message sent successfully!")
        except Exception as e:
            # We don't want the bot to crash just because Telegram failed
            print(f"Connection Error: {e}")

# # --- Setup Integration ---
# def add_telegram_alerts(logger):
#     tg_handler = TelegramHandler()
#
#     # ONLY send Errors and Critical issues to Telegram
#     # You don't want your phone buzzing for every 'INFO' log!
#     tg_handler.setLevel(logging.ERROR)
#
#     formatter = logging.Formatter('%(name)s: %(message)s')
#     tg_handler.setFormatter(formatter)
#
#     logger.addHandler(tg_handler)
