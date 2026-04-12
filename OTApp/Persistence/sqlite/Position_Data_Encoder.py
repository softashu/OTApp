import json
import threading
from decimal import Decimal
from enum import Enum
from dataclasses import asdict, is_dataclass


class PositionDataEncoder(json.JSONEncoder):
    """Translates sacred complex types into the language of JSON."""

    def default(self, obj):
        # 1. Handle Decimals (Common in entry_price, pnl)
        if isinstance(obj, Decimal):
            return float(obj)

        # 2. Handle Enums (Common in OrderSide)
        if isinstance(obj, Enum):
            return obj.value

        # 3. Handle Dataclasses (PositionData, OrderResult)
        if is_dataclass(obj):
            # asdict() is better here IF we handle the conversion
            # of its children in the next pass.
            data = asdict(obj)
            data["__type__"] = obj.__class__.__name__
            return data

        if hasattr(obj, '__dict__'):
            return obj.__dict__

        if isinstance(obj, threading.Timer):
            return "TimerObject"  # JSON can't save active timers

        if hasattr(obj, "__dataclass_fields__"):
            return asdict(obj)

        # 4. Fallback for other types
        return super().default(obj)
