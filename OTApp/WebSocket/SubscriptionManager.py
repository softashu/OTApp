import json

from websocket import WebSocketApp


class SubscriptionManager():
    def __init__(self, logger, pub_ws: WebSocketApp = None,
                 private_ws: WebSocketApp = None):
        self.logger = logger
        self.pub_ws = pub_ws
        self.private_ws = private_ws
        self.subscribed_symbols = set()

    def subscribe_feeds(self, channel: str, symbols: list, public: bool = False) -> None:
        if public:
            try:
                # Convert list to tuple (hashable)
                symbols_key = tuple(symbols)
                if symbols_key not in self.subscribed_symbols:
                    self.public_channel_subscription(channel, symbols)
                    self.subscribed_symbols.add(symbols_key)
                    self.logger.info(f"Subscribed for {channel} channel and symbols {symbols}")
            except Exception as e:
                self.logger.error(f"failed to subscribe to {channel} channel and symbols {symbols} with error : {e}")
        else:
            self.private_channel_subscription(channel, symbols)

    def public_channel_subscription(self, channel: str, symbols: list):
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
            self.pub_ws.send(json.dumps(payload))
        except Exception as e:
            self.logger.error(
                f"Public subscription fail with {e} for channel : {channel} and symbols : {symbols}")

    def private_channel_subscription(self, channel: str, symbols: list):
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
            self.private_ws.send(json.dumps(sub_msg))
            self.logger.info(f"📝 UN_SUB_SENT: Channel '{channel}' with symbols '{symbols}' is done successfully.")
        except Exception as e:
            self.logger.critical(
                f"\n{'=' * 40}\n"
                f"🚨 CRITICAL SUBSCRIPTION FAILURE 🚨\n"
                f"{'=' * 40}\n"
                f"📍 Channel : {channel}\n"
                f"🔍 Symbols : {symbols}\n"
                f"❌ Error   : {e}\n"
                f"{'=' * 40}"
            )

    def unsubscribe_feeds(self, channel: str, symbols: list, public: bool = False):
        if public:
            try:
                # Convert list to tuple (hashable)
                symbols_key = tuple(symbols)
                if symbols_key in self.subscribed_symbols:
                    self.public_channel_un_subscription(channel, symbols)
                    self.subscribed_symbols.remove(symbols_key)
                    self.logger.info(f"Un-Subscribed for {channel} channel and symbols {symbols}")
            except Exception as e:
                self.logger.error(
                    f"failed to un - subscribe to {channel} channel and symbols {symbols} with error : {e}")

    def public_channel_un_subscription(self, channel: str, symbols: list):
        try:
            if symbols is None:
                payload = {
                    "type": "unsubscribe",
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
            self.pub_ws.send(json.dumps(payload))
            self.logger.info(f"unsubscribe to public {channel} channel and symbols: {symbols}")
        except Exception as e:
            self.logger.error(
                f"Public unsubscribe fail with {e} for channel : {channel} and symbols : {symbols}")
