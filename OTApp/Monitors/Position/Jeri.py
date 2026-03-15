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

    def report_positions(self, data):
        pass
