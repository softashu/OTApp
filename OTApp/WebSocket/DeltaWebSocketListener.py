import logging
import time
import hmac
import hashlib
import json
import websocket  # pip install websocket-client

from OTApp.Logger.Logger import AppLogger

"""
To truly honor the name BahaduarDass with a "vigilant sentinel" class, we must ensure the "Sense" (the WebSocket) is actually set up to listen. You are correct—the report_fill method is only the "receiver." We still need the "ear" to hear Delta Exchange.

For private order updates (like "Filled" notifications), Delta requires an Authenticated WebSocket connection. Without this, your BahaduarDass class will sit in silence.

🔱 The "Vigilant Ear": WebSocket Setup
This setup belongs in your main engine or a dedicated connection manager. It connects, authenticates using your API Key/Secret, and then funnels messages to BahaduarDass.

🔱 Why BahaduarDass needs this "Ear"
Private Data: The user_orders channel is private. If you don't send the auth payload, Delta will ignore your subscription.

Real-Time Reaction: This setup ensures that the very millisecond a trade happens on the exchange, the data travels:

Delta → WebSocket → report_fill → BahaduarDass Queue.

Independence: Because BahaduarDass has his own thread, even if the WebSocket receives 100 price updates per second, your fill processing won't be delayed.
"""


class DeltaWebSocketListener:
    """
    Dedicated WebSocket Listener for Delta Exchange.
    Acts as the 'Vigilant Ear' for the BahaduarDass monitoring class.

    Features:
    - Authenticated private channel access.
    - Automatic heartbeat (Ping/Pong) management.
    - Robust error handling and structured logging.
    """

    def __init__(self, api_key, api_secret, monitor_class, logger=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.monitor = monitor_class  # The BahaduarDass instance
        self.ws_url = "wss://socket.india.delta.exchange"
        self._logger_ = AppLogger().get_log()
        self.ws = None

    def _generate_auth_payload(self):
        """Generates the signature required for private channel authentication."""
        try:
            timestamp = str(int(time.time()))
            signature_data = "GET" + timestamp + "/auth"
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                signature_data.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            return {
                "type": "auth",
                "payload": {
                    "api_key": self.api_key,
                    "timestamp": timestamp,
                    "signature": signature
                }
            }
        except Exception as e:
            self._logger_.error(f"❌ AUTH_GEN_ERROR: Failed to create signature | {e}")
            return None

    def on_open(self, ws):
        """Callback triggered when the connection is established."""
        self._logger_.info("📡 WS_CONNECTED: Connection established to Delta Exchange.")

        # 1. Authenticate
        auth_msg = self._generate_auth_payload()
        if auth_msg:
            ws.send(json.dumps(auth_msg))
            self._logger_.info("🔐 AUTH_SENT: Authentication payload dispatched.")

        # 2. Subscribe to Private Order Updates
        sub_msg = {
            "type": "subscribe",
            "payload": {"channels": [{"name": "user_orders"}]}
            # Can we have strategy based channel like 15-delta, up_strategy, down_strategy etc ..
        }
        ws.send(json.dumps(sub_msg))
        self._logger_.info("📝 SUB_SENT: Subscribed to 'user_orders' channel.")

    def on_message(self, ws, message):
        """Callback triggered when a new message arrives."""
        try:
            data = json.loads(message)

            # Route fill events to BahaduarDass
            if data.get('type') == 'user_orders':
                content = data.get('content', {})
                if content.get('state') == 'filled':
                    self._logger_.info(
                        f"🎯 FILL_EVENT: {content.get('symbol')} filled at {content.get('avg_fill_price')}")
                    self.monitor.report_fill(content)

        except json.JSONDecodeError:
            self._logger_.warning(f"⚠️ MALFORMED_DATA: Received invalid JSON | {message}")
        except Exception as e:
            self._logger_.error(f"🚨 MSG_PROCESS_ERROR: Unexpected error in on_message | {e}")

    def on_error(self, ws, error):
        """Handles connection and protocol errors."""
        self._logger_.error(f"🛠️ WS_ERROR: Connection encountered an issue | {error}")

    def on_close(self, ws, close_status_code, close_msg):
        """Handles connection closure."""
        self._logger_.warning(f"🔌 WS_CLOSED: Connection lost | Code: {close_status_code} | Msg: {close_msg}")

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
