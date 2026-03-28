# ============================================================================
# DATA CLASSES
# ============================================================================
import threading
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, List, Dict

from OTApp.Configuration.Enums import OrderSide, StrategyState


@dataclass
class FilledOrderResult:
    strategy_name: str = None
    order_id: Optional[int] = None
    product_id: Optional[int] = None
    symbol: Optional[str] = None
    side: Optional[OrderSide] = None
    fill_size: int = 0
    fill_id = None
    reason: Optional[str] = None
    fill_price: Optional[float] = None
    position_size: Optional[float] = None
    fill_at: Optional[float] = None
    data: Dict = None


@dataclass
class OrderResult:
    strategy_name: str = None
    success: bool = False
    order_id: Optional[int] = None
    product_id: Optional[int] = None
    symbol: Optional[str] = None
    side: Optional[OrderSide] = None
    size: int = 0
    unfilled_size: int = 0
    state: Optional[str] = None
    average_fill_price: Optional[str] = None
    error: Optional[str] = None
    filled_orders: List[FilledOrderResult] = field(default_factory=list)
    data = None
    created_at: float = time.time()  # Timestamp in seconds
    popcorn: threading.Timer = None


@dataclass
class PositionData:
    symbol: str = None
    side: OrderSide = OrderSide.BUY
    product_id: int = 0
    # Optional fields with defaults
    strategy_name: str = None
    size: int = 0
    entry_price: Optional[float] = None
    margin: Optional[Decimal] = None
    position_id: Optional[str] = None
    filled: bool = False
    liquidation_price: Optional[Decimal] = None
    realized_pnl: Optional[Decimal] = None
    unrealized_pnl: Optional[float] = None
    current_price: Optional[float] = None
    orders: List[OrderResult] = field(default_factory=list)
    data = None  # row position data


@dataclass
class LegConfig:
    """Configuration for a single leg of a strategy."""
    strategy_name: str
    symbol: str
    side: OrderSide
    size: int
    limit_price: str
    sl_percentage: float
    product_id: Optional[int] = None
    order_id: Optional[int] = None
    filled: bool = False
    entry_price: Optional[float] = None


@dataclass
class StrategyConfig:
    """Configuration for a complete strategy."""
    strategy_id: str
    strategy_name: str
    legs: List[LegConfig]
    mtm_trigger_threshold: float
    slippage_percentage_per_leg: float = 8.0
    slippage_buffer_multiplier: float = 1.2
    state: StrategyState = StrategyState.IDLE

    def __init__(self, logger):
        self.logger = logger

    def __post_init__(self):
        """Calculate adjusted trigger threshold accounting for slippage."""
        total_position_value = sum(
            float(leg.limit_price) * leg.size for leg in self.legs
        )

        total_slippage = sum(
            float(leg.limit_price) * leg.size * (self.slippage_percentage_per_leg / 100)
            for leg in self.legs
        )
        total_expected_slippage = total_slippage * self.slippage_buffer_multiplier

        self.adjusted_trigger = self.mtm_trigger_threshold - total_expected_slippage

        # Ensure minimum trigger is 50% of original
        min_trigger = self.mtm_trigger_threshold * 0.5
        if self.adjusted_trigger < min_trigger:
            self.logger.warning(
                f"[{self.strategy_id}] Calculated trigger ${self.adjusted_trigger:.2f} "
                f"is too low, using minimum ${min_trigger:.2f}"
            )
            self.adjusted_trigger = min_trigger

        self.info(f"[{self.strategy_id}] Slippage Calculation:")
        self.info(f"   Total Position Value: ${total_position_value:.2f}")
        self.info(f"   Expected Slippage: ${total_expected_slippage:.2f}")
        self.info(f"   Original Threshold: ${self.mtm_trigger_threshold:.2f}")
        self.info(f"   🎯 Adjusted Trigger: ${self.adjusted_trigger:.2f}")
        self.info(f"   📊 Safety Margin: ${self.mtm_trigger_threshold - self.adjusted_trigger:.2f}")

    def get_symbols(self) -> List[str]:
        """Get all symbols in this strategy."""
        return [leg.symbol for leg in self.legs]

    def get_product_ids(self) -> List[int]:
        """Get all product IDs in this strategy."""
        return [leg.product_id for leg in self.legs if leg.product_id]
