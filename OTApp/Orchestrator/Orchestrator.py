import threading

from apscheduler.schedulers.blocking import BlockingScheduler

from OTApp.Configuration.AppConfig import Config
from OTApp.Configuration.DeltaExchangeConfiguration import DeltaExchangeConfiguration
from OTApp.Logger.Logger import AppLogger
from OTApp.Monitors.Order.OrderFillChaukidar import BahaduarDass
from OTApp.Monitors.system.PublicAnnouncement.Announcements import PublicAnnouncement
from OTApp.Strategy.BTC_15_Delta_Short_Strangle import BTC_15_Delta_Strangle
from OTApp.WebSocket.DeltaWebSocketListener import DeltaWebSocketListener
from OTApp.WebSocket.public.DeltaWebSocketPublicListener import DeltaWebSocketPublicListener


class Orchestrator:
    def __init__(self):
        self._logger_ = AppLogger().get_log()
        key = DeltaExchangeConfiguration.API_KEY
        secret = DeltaExchangeConfiguration.API_SECRET
        # Starting private cannel to monitor order related data
        bahaduar_dass_instance = BahaduarDass()
        # Launching the Vigilant Sentinel for private data
        listener = DeltaWebSocketListener(key, secret, bahaduar_dass_instance, self._logger_)
        ws_thread = threading.Thread(target=listener.run_sentinel, daemon=True)
        ws_thread.start()
        self._websocket_listener = listener

        # Launching the Vigilant Sentinel for Public data in separate trade
        public_announcements = PublicAnnouncement(logger=self._logger_)
        public_data_listener = DeltaWebSocketPublicListener(logger=self._logger_, monitor_class=public_announcements)
        ws_public_announcements_thread = threading.Thread(target=public_data_listener.run_sentinel, daemon=True)
        ws_public_announcements_thread.start()
        self._public_websocket_listener = public_data_listener


        # --- Scheduler Setup ---
        scheduler = BlockingScheduler(timezone=Config.TIME_ZONE.zone)

        # This tells the scheduler to wake up  15_Delta strategy at 06:00 every day
        scheduler.add_job(BTC_15_Delta_Strangle().trade_job, 'cron', hour=21, minute=12)
        self._logger_.info("Scheduler active. The bot will check every minute between 06:00 and 08:15 IST daily.")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self._logger_.critical(f"Scheduler stopped manually")

        # # Register the "Guard" for Ctrl+C (SIGINT)
        # signal.signal(signal.signal.SIGINT, self.graceful_exit)

    # def graceful_exit(sig, frame):
    #     print("\n🔱 Raavan Engine: Initiating shutdown sequence...")
    #     # Close the WebSocket explicitly
    #     if 'listener' in globals() and listener.ws:
    #         listener.ws.close()
    #     print("👋 BahaduarDass: Vigilant watch ended. Exiting safely.")
    #     sys.exit(0)


# Starting ... every thing
Orchestrator()
