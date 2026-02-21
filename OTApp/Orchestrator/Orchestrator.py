import threading

from apscheduler.schedulers.blocking import BlockingScheduler

from OTApp.Configuration.AppConfig import Config
from OTApp.Configuration.DeltaExchangeConfiguration import DeltaExchangeConfiguration
from OTApp.Logger.Logger import AppLogger
from OTApp.Monitors.Order.OrderFillChaukidar import BahaduarDass
from OTApp.Strategy.BTC_15_Delta_Short_Strangle import BTC_15_Delta_Strangle
from OTApp.WebSocket.DeltaWebSocketListener import DeltaWebSocketListener


class Orchestrator:
    def __init__(self):
        self._logger_ = AppLogger().get_log()
        key = DeltaExchangeConfiguration.API_KEY
        secret = DeltaExchangeConfiguration.API_SECRET
        bahaduar_dass_instance = BahaduarDass()
        # Launching the Vigilant Sentinel
        listener = DeltaWebSocketListener(key, secret, bahaduar_dass_instance, self._logger_)
        ws_thread = threading.Thread(target=listener.run_sentinel, daemon=True)
        ws_thread.start()
        self._websocket_listener = listener

        # --- Scheduler Setup ---
        scheduler = BlockingScheduler(timezone=Config.TIME_ZONE.zone)

        # This tells the scheduler to wake up  15_Delta strategy at 06:00 every day
        scheduler.add_job(BTC_15_Delta_Strangle().trade_job, 'cron', hour=12, minute=59)
        self._logger_.info("Scheduler active. The bot will check every minute between 06:00 and 08:15 IST daily.")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self._logger_.critical(f"Scheduler stopped manually")


# Starting ... every thing
Orchestrator()
