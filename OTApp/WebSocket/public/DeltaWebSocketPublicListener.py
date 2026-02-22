import hashlib
import hmac
import json
import time
from pprint import pprint

import websocket  # pip install websocket-client

from OTApp.Logger.Logger import AppLogger

"""
Public data listner
"""


class DeltaWebSocketPublicListener:

    def __init__(self, monitor_class, logger=None):
        self.monitor = monitor_class  # The PublicAnnouncement instance
        self.ws_url = "wss://socket.india.delta.exchange"
        self._logger_ = logger
        self.ws = None

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
        self.subscribe(ws, channel="mark_price", symbols=['BTCUSD'])

    def on_message(self, ws, message):
        try:
            self.monitor.on_announcement(json.loads(message))
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
