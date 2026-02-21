import hashlib
import hmac
import json
import time

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

    def _generate_signature(self, secret, message):
        """Standard HMAC-SHA256 signature generation."""
        message_bytes = bytes(message, 'utf-8')
        secret_bytes = bytes(secret, 'utf-8')
        return hmac.new(secret_bytes, message_bytes, hashlib.sha256).hexdigest()

    def send_authentication(self, ws):
        """Sends the 'key-auth' payload as per working demo."""
        try:
            method = 'GET'
            timestamp = str(int(time.time()))
            path = '/live'  # Specific path required for WS auth
            signature_data = method + timestamp + path
            signature = self._generate_signature(self.api_secret, signature_data)

            auth_payload = {
                "type": "key-auth",
                "payload": {
                    "api-key": self.api_key,
                    "signature": signature,
                    "timestamp": timestamp
                }
            }
            ws.send(json.dumps(auth_payload))
            self._logger_.info("🔐 AUTH_SENT: Key-auth payload dispatched.")
        except Exception as e:
            self._logger_.error(f"❌ AUTH_PREP_ERROR: {e}")

    def on_open(self, ws):
        self._logger_.info("📡 WS_OPEN: Connection established.")
        self.send_authentication(ws)

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            msg_type = data.get('type')

            # Handle Auth Response
            if msg_type == 'key-auth':
                if data.get('success'):
                    self._logger_.info("✅ AUTH_SUCCESS: Delta India authenticated.")
                    # Subscribe to orders (Private Channel)
                    self._subscribe(ws, "orders")
                else:
                    self._logger_.error(f"❌ AUTH_FAILED: {data.get('message')}")

            # Handle Order Fills
            elif msg_type == 'orders':
                data_state = data.get('state', {})
                if data_state == 'filled':
                    # Forward to BahaduarDass Dispatcher
                    self.monitor.report_fill(data)
                # else:
                #     pprint(data)
                #     self.monitor.report_fill(data)


        except Exception as e:
            self._logger_.error(f"🚨 MSG_ERROR: {e}")

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

    def _subscribe(self, ws, channel):
        """Subscription helper using the 'all' symbols list."""
        sub_msg = {
            "type": "subscribe",
            "payload": {
                "channels": [
                    {
                        "name": channel,
                        "symbols": ["all"]  # 'all' is required for user account streams
                    }
                ]
            }
        }
        ws.send(json.dumps(sub_msg))
        self._logger_.info(f"📝 SUB_SENT: Channel '{channel}' is now live.")
