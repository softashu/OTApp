import hashlib
import hmac
import json
import time

from OTApp.Configuration import DeltaExchangeConfiguration


class APIRequestSecurityManager:
    def build_payload_signature(self, PATH: str, req_method: str, req_query_string: str, order_payload) -> tuple[
        str, str]:
        # 1. Generate the Timestamp (Unix seconds)
        timestamp = str(int(time.time()))

        # 2. Create the Signature Payload
        # Format: method + timestamp + path + query_string + body
        method = req_method
        query_string = req_query_string
        payload = method + timestamp + PATH + query_string + json.dumps(order_payload)

        # 3. Sign the payload using HMAC-SHA256
        signature = hmac.new(
            (str(DeltaExchangeConfiguration.API_SECRET())).encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature, timestamp
