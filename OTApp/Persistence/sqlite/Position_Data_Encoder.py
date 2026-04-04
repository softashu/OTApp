import json
from decimal import Decimal
from enum import Enum
from dataclasses import asdict, is_dataclass


class PositionDataEncoder(json.JSONEncoder):
    """Translates sacred complex types into the language of JSON."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, Enum):
            return obj.value
        if is_dataclass(obj):
            return asdict(obj)
        return super().default(obj)
