import logging
import os
from logging.handlers import TimedRotatingFileHandler

from OTApp.Configuration.AppConfig import Config
from OTApp.Notifications.Telegram.TelegramHandler import TelegramHandler


class AppLogger:
    # Basic configuration
    logging.basicConfig(
        level=Config().LOG_LEVEL,
        format='%(asctime)s - %(levelname)s - %(message)s',
        # formating date to be appeared as 07-02-2026 ( dd-mm-yyyy)
        datefmt='%d-%m-%Y %H:%M:%S'
    )
    logger = logging

    def setup_logger(self, strategy_name):
        # Create a unique logger for the strategy
        logger = logging.getLogger(strategy_name)
        logger.setLevel(Config().LOG_LEVEL)

        # Prevent logs from bubbling up to the main/root logger
        # (This prevents double-printing in the console)
        logger.propagate = False

        # 2. Ensure a 'logs' folder exists
        if not os.path.exists('logs'):
            os.makedirs('logs')

        # 3. Set up the Timed Handler
        # filename: logs/scalper.log
        # when='midnight': creates a new file every day at 00:00
        # backupCount=30: keeps the last 30 days of logs
        log_path = os.path.join('..//logs', f"{strategy_name}.log")

        handler = TimedRotatingFileHandler(
            log_path,
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )

        # 4. Set the suffix for the old files (e.g., scalper.log.2026-02-07)
        handler.suffix = "%Y-%m-%d"

        # 5. Apply your preferred date format
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%d-%m-%Y %H:%M:%S'
        )
        handler.setFormatter(formatter)

        # 6. Add handler (clear existing handlers first to avoid duplicates)
        if logger.hasHandlers():
            logger.handlers.clear()

        logger.addHandler(handler)
        # 2. Console Handler (Conditional based on Config)
        if Config().SHOW_CONSOLE:
            console_handler = logging.StreamHandler()
            # You can add your ColorFormatter here too!
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        # 3. Telegram Handler (Conditional based on Config)
        if Config().ENABLE_TELEGRAM:
            # Import the handler we built
            tg_handler = TelegramHandler()
            tg_handler.setLevel(logging.ERROR)
            formatter = logging.Formatter('%(name)s: %(message)s')
            tg_handler.setFormatter(formatter)
            logger.addHandler(tg_handler)
        return logger

    def get_log(cls):
        global logger
        # Set up your strategy logger
        logger = AppLogger().setup_logger(Config.STRATEGIES[0])
        # # # add_telegram_alerts(scalp_logger)
        # #
        # # # # THIS stays in the local file only:
        # logger.info("Checked price, no signal.")
        # # THIS goes to the file AND your phone instantly:
        # logger.error("Insufficient USD Balance to place order!")
        # logger.critical("Insufficient USD Balance to place order!")
        return logger

# AppLogger().get_log()
