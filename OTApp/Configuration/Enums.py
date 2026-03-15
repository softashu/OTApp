# ============================================================================
# ENUMS
# ============================================================================
from enum import Enum


class OrderSide(Enum):
    BUY = 'buy'
    SELL = 'sell'


class OrderType(Enum):
    MARKET = 'market_order'
    LIMIT = 'limit_order'


class OrderState(Enum):
    OPEN = 'open'
    PENDING = 'pending'
    CLOSED = 'closed'
    CANCELLED = 'cancelled'


class StrategyState(Enum):
    IDLE = 'idle'
    PLACING_ORDERS = 'placing_orders'
    ACTIVE = 'active'
    CLOSING = 'closing'
    CLOSED = 'closed'
    ERROR = 'error'


class RequestMethod(Enum):
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    PATCH = 'PATCH'
    DELETE = 'DELETE'
    HEAD = 'HEAD'
    TRACE = 'TRACE'
    CONNECT = 'CONNECT'
    OPTIONS = 'OPTIONS'
