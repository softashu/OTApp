import hashlib
import hmac
import json
import time

import websocket  # pip install websocket-client

from OTApp.Logger.Logger import AppLogger
from OTApp.Monitors.Order.OrderChaukidar import BahaduarDass
from OTApp.Monitors.Position.Jeri import Jeri
from OTApp.WebSocket import SubscriptionManager

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

    def __init__(self, api_key, api_secret, order_monitor_class: BahaduarDass, position_monitor_class: Jeri,
                 logger=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.order_monitor = order_monitor_class  # The BahaduarDass instance
        self.position_monitor = position_monitor_class  # Jeri instance
        self.ws_url = "wss://socket.india.delta.exchange"
        self._logger_ = AppLogger().get_log()
        self.ws = None
        # 🔱 Retry configuration
        self.auth_attempts = 0
        self.max_auth_delay = 60  # Max wait of 60 seconds
        self.base_delay = 2  # Start with 2 seconds

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
                    self._logger_.info("✅ AUTH_SUCCESS: Delta India authenticated the BahaduarDass is now authorized.")
                    self.auth_attempts = 0  # Reset counter on success
                    # Subscribe to orders (Private Channel)
                    self._subscribe(ws, "orders")  # Includes position after fill
                    # Primary: WebSocket for real-time updates in positions
                    self._subscribe(ws=ws, channel="positions")
                    # this will give update for order get fill
                    self._subscribe(ws=ws, channel="v2/user_trades")
                else:
                    self._handle_auth_failure(ws, data)
            # Handle Order Fills
            elif msg_type == 'orders':
                action = data.get('action')
                if action == 'snapshot' and 'result' in data and data['result']:
                    # Forward to BahaduarDass Dispatcher
                    self.order_monitor.report_bahadur_dass(data)
                    self._logger_.info(f"Order data received: {data}")
                elif action in {'delete', 'create', 'update'}:
                    # Forward to BahaduarDass Dispatcher
                    self.order_monitor.report_bahadur_dass(data)
                    self._logger_.info(f"Order data received: {data}")
                else:
                    self._logger_.info(f"Order data received: {data} with action : {action}")
            elif msg_type == 'positions':
                action = data.get('action')
                if action == 'snapshot' and 'result' in data and data['result']:
                    self.position_monitor.report_positions(data)
                    self._logger_.info(f"Position data received: {data}")
                elif action in {'delete', 'create', 'update'}:
                    self.position_monitor.report_positions(data)
                    self._logger_.info(f"Position data received: {data}")
                else:
                    self._logger_.info(f"Position data received: {data} and action : {action}")
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
        # initializing private ws variable to order and position manager
        self.order_monitor.subscriber_manager.private_ws = self.ws

        # 🔱 GUARD: Automatic reconnection logic
        # ping_interval/timeout keeps the connection alive via heartbeats
        self.ws.run_forever(
            ping_interval=30,
            ping_timeout=10,
            reconnect=5  # This is the 5-second automatic retry guard
        )

    def _subscribe(self, ws, channel, symbols=None):
        """Subscription helper using the 'all' symbols list."""
        try:
            if symbols is None:
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
            else:
                sub_msg = {
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
            ws.send(json.dumps(sub_msg))
            self._logger_.info(f"📝 SUB_SENT: Channel '{channel}' is now live.")
        except Exception as e:
            self._logger_.critical(
                f"\n{'=' * 40}\n"
                f"🚨 CRITICAL SUBSCRIPTION FAILURE 🚨\n"
                f"{'=' * 40}\n"
                f"📍 Channel : {channel}\n"
                f"🔍 Symbols : {symbols}\n"
                f"❌ Error   : {e}\n"
                f"{'=' * 40}"
            )

    def _handle_auth_failure(self, ws, error_data):
        """
        To implement a persistent authentication loop within the BahaduarDass sentinel,
        we can use an Exponential Backoff strategy. This ensures that if authentication fails
        (due to network jitter or temporary server issues), the system doesn't "spam" the exchange but instead waits
        for increasing intervals before trying again.

        🔱 The Robust "Vigilant" Auth Loop
        We will modify the on_message handler to detect the key-auth failure and trigger a
        re-authentication attempt.

        🔱 The Backoff Guard: Retries authentication with increasing wait times.
        :param ws:
        :param data:
        :return:
        """
        self.auth_attempts += 1

        # Calculate delay: 2, 4, 8, 16... up to 60s
        wait_time = min(self.base_delay * (2 ** (self.auth_attempts - 1)), self.max_auth_delay)
        self._logger_.warning(
            f"⚠️ AUTH_FAILED: {error_data.get('message')} | "
            f"Attempt: {self.auth_attempts} | Retrying in {wait_time}s..."
        )

        # Wait before trying again
        time.sleep(wait_time)
        self.send_authentication(ws)

    def subscribe_from_outer_world(self, channel, symbols=None):
        """Subscription helper method for outer world"""
        try:
            if symbols is None:
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
            else:
                sub_msg = {
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
            self.ws.send(json.dumps(sub_msg))
            self._logger_.info(f"📝 SUB_SENT: Channel '{channel}' is now live.")
        except Exception as e:
            self._logger_.critical(
                f"\n{'=' * 40}\n"
                f"🚨 CRITICAL SUBSCRIPTION FAILURE 🚨\n"
                f"{'=' * 40}\n"
                f"📍 Channel : {channel}\n"
                f"🔍 Symbols : {symbols}\n"
                f"❌ Error   : {e}\n"
                f"{'=' * 40}"
            )

    def un_subscribe_from_outer_world(self, channel, symbols=None):
        """Subscription helper method for outer world"""
        try:
            if symbols is None:
                sub_msg = {
                    "type": "unsubscribe",
                    "payload": {
                        "channels": [
                            {
                                "name": channel,
                                "symbols": ["all"]  # 'all' is required for user account streams
                            }
                        ]
                    }
                }
            else:
                sub_msg = {
                    "type": "unsubscribe",
                    "payload": {
                        "channels": [
                            {
                                "name": channel,
                                "symbols": symbols
                            }
                        ]
                    }
                }
            self.ws.send(json.dumps(sub_msg))
            self._logger_.info(f"📝 UN_SUB_SENT: Channel '{channel}' with symbols '{symbols}' is done successfully.")
        except Exception as e:
            self._logger_.critical(
                f"\n{'=' * 40}\n"
                f"🚨 CRITICAL SUBSCRIPTION FAILURE 🚨\n"
                f"{'=' * 40}\n"
                f"📍 Channel : {channel}\n"
                f"🔍 Symbols : {symbols}\n"
                f"❌ Error   : {e}\n"
                f"{'=' * 40}"
            )
