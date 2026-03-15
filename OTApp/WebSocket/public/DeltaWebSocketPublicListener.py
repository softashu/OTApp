import json
import time

import websocket  # pip install websocket-client
from Tools.scripts.nm2def import symbols

from OTApp.Monitors.Order.OrderChaukidar import BahaduarDass
from OTApp.Monitors.Position.Jeri import Jeri
from OTApp.Monitors.system.PublicAnnouncement.Announcements import PublicAnnouncement

"""
Public data listner
"""


class DeltaWebSocketPublicListener:

    def __init__(self, public_announcement_monitor_class: PublicAnnouncement, order_monitor: BahaduarDass,
                 position_monitor: Jeri, logger=None):
        self.public_announcement_monitor = public_announcement_monitor_class  # The PublicAnnouncement instance
        self.order_monitor = order_monitor
        self.position_monitor = position_monitor
        self.ws_url = "wss://socket.india.delta.exchange"
        self._logger_ = logger
        self.ws = None
        self.INTERVAL = 300
        self.PENDING_ORDER_PROCESS_INTERVAL = 10
        self.last_mark_price_processed_time = 0
        self.process_time_map = {}

    def on_open(self, ws):
        self._logger_.info("📡 WS_PUB_OPEN: Connection established.")
        # subscribe tickers of perpetual futures - BTCUSD & ETHUSD, call option C-BTC-95200-200225 and put option - P-BTC-95200-200225
        # _subscribe(ws, "v2/ticker", ["BTCUSD", "ETHUSD", "C-BTC-95200-200225", "P-BTC-95200-200225"])
        # subscribe 1 minute ohlc candlestick of perpetual futures - MARK:BTCUSD(mark price) & ETHUSD(ltp), call option C-BTC-95200-200225(ltp) and put option - P-BTC-95200-200225(ltp).
        # self._subscribe(ws, "candlestick_1m", ["MARK:BTCUSD", "ETHUSD", "C-BTC-95200-200225", "P-BTC-95200-200225"])
        """
        This is a public websocket channel that provides updates on system-wide status events such as 
        scheduled maintenance, maintenance start and finish, degraded mode, and fallback operation. 
        No symbols are required when subscribing to this channel. 
        Below are the types of messages sent for more details:
        """
        self.subscribe(ws, channel="system_status", symbols=None)
        """
        You should also subscribe to product_updates for market disruption events:

        Market disruption (cancel_only mode)
        Auction started/finished
        Trading status changes
        """
        self.subscribe(ws, channel="product_updates", symbols=None)
        # bitcoin mark price update
        self.subscribe(ws, channel="mark_price", symbols=['MARK:BTCUSD'])

    def on_message(self, ws, message):
        try:
            message_json = json.loads(message)
            type = message_json.get('type')
            if type == 'mark_price':
                current_time = time.time()
                # Only process every 5 minutes
                if current_time - self.last_mark_price_processed_time >= self.INTERVAL:
                    self.last_mark_price_processed_time = current_time
                    # Otherwise, ignore the update
                    self.public_announcement_monitor.on_announcement(json.loads(message))
            elif type == 'l2_orderbook':
                # Process at every 15 seconds
                symbol = message_json.get('symbol')
                # Skip processing if symbol is missing
                if not symbol:
                    self._logger_.warning("Received message without symbol field")
                    return
                # Initialize symbol in map if it doesn't exist (first time processing)
                if symbol not in self.process_time_map:
                    self.process_time_map[symbol] = 0
                current_time = time.time()
                # Check if enough time has elapsed since last processing
                if current_time - self.process_time_map[symbol] >= self.PENDING_ORDER_PROCESS_INTERVAL:
                    self._logger_.info(f"L2_ORDERBOOK: {message_json}")
                    self.process_time_map[symbol] = current_time
            elif type in {'announcements', 'system_status', 'product_updates'}:
                self.public_announcement_monitor.on_announcement(message_json)
            elif type == 'subscriptions':
                self._logger_.info(f"Message type: {type} and {message_json}")
            elif type == 'unsubscribed':
                channels = message_json.get('channels', [])
                if channels:
                    for channel in channels:
                        channel_name = channel.get('name')
                        symbols = channel.get('symbols', [])
                        for symbol in symbols:
                            if symbol in self.process_time_map:
                                self.process_time_map.pop(symbol, None)
            else:
                self._logger_.critical(f"Unknown Message type: {type} and {message_json}")
        except Exception as e:
            self._logger_.error(f"WS_PUB: 🚨 MSG_ERROR: {e}")

    def on_error(self, ws, error):
        """Handles connection and protocol errors."""
        self._logger_.error(f"🛠️ WS_PUB_CLOSED: Connection encountered an issue | {error}")

    def on_close(self, ws, close_status_code, close_msg):
        """Handles connection closure."""
        self._logger_.warning(f"🔌 WS_PUB_CLOSED: Connection lost | Code: {close_status_code} | Msg: {close_msg}")

    def run_sentinel(self):
        """
        Starts the WebSocketApp with the 'Vigilant Guard' (reconnect logic).
        """
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        # initializing public ws variable to order and position manager
        self.order_monitor.subscriber_manager.pub_ws = self.ws

        # 🔱 GUARD: Automatic reconnection logic
        # ping_interval/timeout keeps the connection alive via heartbeats
        self.ws.run_forever(
            ping_interval=30,
            ping_timeout=10,
            reconnect=5  # This is the 5-second automatic retry guard
        )

    def subscribe(self, ws, channel, symbols):
        self._logger_.info(f"Public subscribe to {channel} channel ans symbols: {symbols}")
        payload = {}
        try:
            if symbols is None:
                payload = {
                    "type": "subscribe",
                    "payload": {
                        "channels": [
                            {
                                "name": channel
                            }
                        ]
                    }
                }
            else:
                payload = {
                    "type": "subscribe",
                    "payload": {
                        "channels": [
                            {
                                "name": channel,
                                "symbols": symbols
                            }
                        ]
                    }
                }
            ws.send(json.dumps(payload))
        except Exception as e:
            self._logger_.error(
                f"Public announcement subscription fail with {e} for channel : {channel} and symbols : {symbols}")
