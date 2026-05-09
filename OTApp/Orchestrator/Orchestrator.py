import threading

from apscheduler.schedulers.blocking import BlockingScheduler

from OTApp.Configuration.AppConfig import Config
from OTApp.Configuration.DeltaExchangeConfiguration import DeltaExchangeConfiguration
from OTApp.Logger.Logger import AppLogger
from OTApp.Monitors.Order.OrderChaukidar import BahaduarDass
from OTApp.Monitors.Position.Jeri import Jeri
from OTApp.Monitors.system.PublicAnnouncement.Announcements import PublicAnnouncement
from OTApp.Persistence.sqlite.SqliteManager import Chitragupt
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
        # jeri_instance to monitor position data
        jeri_instance = Jeri()
        # initiating Sqlite as with Chitragupt Ji Maharaj.
        chitragupta_instance = Chitragupt(logger=self._logger_)

        # initiating TradeMunshi

        # Launching the Vigilant Sentinel for private data
        listener = DeltaWebSocketListener(api_key=key,
                                          api_secret=secret,
                                          order_monitor_class=bahaduar_dass_instance,
                                          position_monitor_class=jeri_instance,
                                          logger=self._logger_)
        ws_thread = threading.Thread(target=listener.run_sentinel, daemon=True)
        ws_thread.start()
        self._websocket_listener = listener

        # Launching the Vigilant Sentinel for Public data in separate trade
        public_announcements = PublicAnnouncement(logger=self._logger_)
        public_data_listener = DeltaWebSocketPublicListener(logger=self._logger_,
                                                            order_monitor=bahaduar_dass_instance,
                                                            position_monitor=jeri_instance,
                                                            public_announcement_monitor_class=public_announcements)
        ws_public_announcements_thread = threading.Thread(target=public_data_listener.run_sentinel, daemon=True)
        ws_public_announcements_thread.start()
        self._public_websocket_listener = public_data_listener

        # --- Scheduler Setup ---
        scheduler = BlockingScheduler(timezone=Config.TIME_ZONE.zone)

        # This tells the scheduler to wake up  15_Delta strategy at 06:00 every day
        scheduler.add_job(BTC_15_Delta_Strangle().trade_job, 'cron', hour=15, minute=24)
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
