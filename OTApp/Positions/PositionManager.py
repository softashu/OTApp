"""
    Given name Jeri , it is my little dog that monitoring our house very efficiently and his sound have very high frequency
    ---------------------------------------------------------
    Jeri's Features 🐕
    Watchdog duty: Monitors your positions 24/7
    Smart alerts: Logs detailed reports every check
    Auto-protection: Closes positions when loss limit hit
    Error resilient: Handles API failures gracefully
    Loyal companion: Named after your dog for good luck!

    WebSocket Approach (Real-time Updates) to monitor positions

    How It Works
        At Startup: Calculates trigger threshold based on position size and slippage estimates
        During Monitoring: Jeri checks MTM loss every 5 seconds
        At 80% of Trigger: Warning logged
        At Trigger Threshold: Positions closed immediately
        Expected Outcome: Final loss after slippage should be ≤ $22

    Safety Features
        Minimum Trigger: Never goes below 50% of max loss
        Dual Limits: Both trigger threshold and max loss checked
        Emergency Closure: If max loss exceeded, immediate closure
        Slippage Buffer: 20% extra margin on slippage estimate

    This ensures Jeri closes your positions with enough buffer to account for slippage, keeping your actual realized loss under $22 USD!
"""
import json
import threading
from typing import List, Optional

from OTApp.APIs.RequestManager import RequestManager
from OTApp.Configuration.DataClasses import PositionData, StrategyConfig
from OTApp.Configuration.Enums import RequestMethod, OrderSide, OrderType
from OTApp.WebSocket.DeltaWebSocketListener import DeltaWebSocketListener
from OTApp.WebSocket.public.DeltaWebSocketPublicListener import DeltaWebSocketPublicListener


class PositionManager:
    """Manages all position-related operations."""

    def __init__(self, logger, ws_listener_pub: DeltaWebSocketPublicListener,
                 ws_listener_private: DeltaWebSocketListener):
        self._logger_ = logger
        self._ws_pub_ = ws_listener_pub
        self.ws_listener_private = ws_listener_private
        self._positions = {}
        self.position_lock = threading.Lock()
        self.request_manager = RequestManager(logger)
        logger.info("📊 PositionManager initialized")

    def get_positions_rest(self, product_ids: List[int] = None) -> List[PositionData]:
        """Get current positions via REST API."""
        try:
            query_params = {}
            if product_ids:
                query_params['product_ids'] = ','.join(map(str, product_ids))

            response = self.request_manager.api_request(api_req_method=RequestMethod.GET,
                                                        api_context_path='/positions/margined',
                                                        query_params=query_params, payload={})
            positions = []
            if response.get('success'):
                for pos in response.get('result', []):
                    position = PositionData(
                        product_id=pos.get('product_id'),
                        symbol=pos.get('product_symbol'),
                        size=pos.get('size'),
                        entry_price=float(pos.get('entry_price')),
                        margin=pos.get('margin'),
                        liquidation_price=pos.get('liquidation_price'),
                        realized_pnl=pos.get('realized_pnl', '0')
                    )
                    positions.append(position)
                    with self.position_lock:
                        self._positions[position.symbol] = position
            return positions
        except Exception as e:
            self._logger_.error(f"Exception in get_positions_rest: {str(e)}", exc_info=True)
            return []

    def manage_position(self, strategy_name, positions):
        self._positions.update({strategy_name: positions})
        # 1. subscribe positions for getting data
        # 2.

    def square_off_positions(self, strategy_name, positions):
        pass

    def calculate_MTM(self, strategy_name, positions):
        pass

    def close_all_positions(self) -> bool:
        """Close all open positions using market orders."""
        try:
            self._logger_.info("Closing all positions...")
            response = self.request_manager.api_request(api_req_method=RequestMethod.POST,
                                                        api_context_path='/positions/close_all',
                                                        payload={})
            if response.get('success'):
                self._logger_.info("All positions closed successfully")
                with self.position_lock:
                    self._positions.clear()
                return True
            else:
                error_msg = response.get('error', {}).get('message', 'Unknown error')
                self._logger_.error(f"Failed to close positions: {error_msg}")
                return False
        except Exception as e:
            self._logger_.error(f"Exception in close_all_positions: {str(e)}", exc_info=True)
            return False

    def close_position_by_product_id(self, product_id: int) -> bool:
        """Close a specific position by placing opposite market order."""
        try:
            self._logger_.info(f"Closing position for product_id {product_id}")
            positions = self.get_positions_rest([product_id])

            if not positions:
                self._logger_.warning(f"No position found for product_id {product_id}")
                return False

            pos = positions[0]
            side = OrderSide.BUY.value if pos.size < 0 else OrderSide.SELL.value
            size = abs(pos.size)

            self._logger_.info(f"Placing {side} market order to close {pos.symbol}: Size={size}")

            payload = {
                "product_id": product_id,
                "size": size,
                "side": side,
                "order_type": OrderType.MARKET.value
            }

            response = self.request_manager.api_request(api_req_method=RequestMethod.POST, api_context_path='/orders',
                                                        payload=payload)
            if response.get('success'):
                self._logger_.info(f"Position close order placed for {pos.symbol}")
                with self.position_lock:
                    if pos.symbol in self._positions:
                        del self._positions[pos.symbol]
                return True
            else:
                error_msg = response.get('error', {}).get('message', 'Unknown error')
                self._logger_.error(f"Failed to close position: {error_msg}")
                return False
        except Exception as e:
            self._logger_.error(f"Exception in close_position_by_product_id: {str(e)}", exc_info=True)
            return False

    def close_strategy_positions(self, strategy: StrategyConfig) -> bool:
        """Close all positions for a specific strategy."""
        try:
            self._logger_.info(f"[{strategy.strategy_id}] Closing all strategy positions...")
            success = True
            for leg in strategy.legs:
                if leg.product_id:
                    if not self.close_position_by_product_id(leg.product_id):
                        success = False
            return success
        except Exception as e:
            self._logger_.error(f"[{strategy.strategy_id}] Exception in close_strategy_positions: {str(e)}",
                                exc_info=True)
            return False

    def update_position(self, symbol: str, position: PositionData):
        """Update position data (thread-safe)."""
        with self.position_lock:
            self._positions[symbol] = position

    def get_position(self, symbol: str) -> Optional[PositionData]:
        """Get position data for a symbol (thread-safe)."""
        with self.position_lock:
            return self._positions.get(symbol)
