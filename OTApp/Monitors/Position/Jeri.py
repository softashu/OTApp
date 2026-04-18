import queue
import threading
from collections import defaultdict

from OTApp.Configuration.DataClasses import PositionData
from OTApp.Logger.Logger import AppLogger

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


class Jeri():
    def __init__(self):
        self._logger_ = AppLogger().get_log()
        self._active_order_lock_ = threading.Lock()
        # The memory of the system: holding the fill data
        self.position_queue = queue.Queue()
        self._positions_: dict[str, dict[str, PositionData]] = defaultdict(dict)

    def report_jeri_for_positions(self, position_data):
        action = position_data.get('action')
        symbol = position_data.get('product_symbol')
        self._logger_.info(f"Jeri received {action} position for {symbol} with data : {position_data}")
        self.position_queue.put(position_data)
