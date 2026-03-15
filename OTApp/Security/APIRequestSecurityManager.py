import hashlib
import hmac
import json
import time
from typing import Any

from OTApp.Configuration import DeltaExchangeConfiguration


class APIRequestSecurityManager:
    def build_payload_signature(self, PATH: str, req_method: str, req_query_string: str, req_payload: dict[str, Any]) -> \
    tuple[
        str, str]:
        # 1. Generate the Timestamp (Unix seconds)
        timestamp = str(int(time.time()))

        # 2. Create the Signature Payload
        # Format: method + timestamp + path + query_string + body
        method = req_method
        query_string = req_query_string
        signature_data_payload = method + timestamp + PATH + query_string + json.dumps(req_payload)

        # 3. Sign the payload using HMAC-SHA256
        signature = hmac.new(
            (str(DeltaExchangeConfiguration.API_SECRET())).encode('utf-8'),
            signature_data_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature, timestamp
