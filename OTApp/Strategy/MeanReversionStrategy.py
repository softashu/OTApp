from OTApp.Analyser import DataAnalyser
from OTApp.Logger.Logger import AppLogger
from datetime import datetime, time as dtime


class BlowOffTop:
    """
    you are looking to build a mean-reversion strategy that targets overextended uptrend's.
    Effectively, you are looking for a "blow-off top" where momentum exhausts and the trend flips.

    Strategy: Bearish Reversal (Sell CE / Short Call)
              This strategy seeks to identify a "hidden" top where the price is technically overbought
              but the trend indicator (SuperTrend) hasn't yet caught up

    1. The Setup (Pre-Conditions)

        Trend Confirmation: There must be a visible uptrend characterized by higher highs and higher lows
                            leading into the trade zone.
        Momentum Overextension: The RSI must be above 70, indicating the asset is in "overbought" territory.
        Baseline Trend: The SuperTrend must currently be Green (indicating a bullish state) while we wait for the reversal.

    2. The Trigger (Order Execution)
        Step A: Identify the Order Block (OB): Look for the last bullish candle at the peak before the RSI starts to dip
                                                or price consolidates. This is your "top" zone.
        Step B: The Confirmation: Wait for the SuperTrend to flip from Green to Red.
                                  This confirms that the immediate momentum has shifted downward.
        Step C: Entry: Once the SuperTrend turns Red, place a Sell CE (Call Option) order.
        Entry Price: Ideally, enter (choose strike ) at or slightly above the Order Block (OB) high to get a better
                              premium and a safer margin of error.

    3. Trade Management (Risk/Reward)
        Element                                             Description
            Strike                                          Choose an Out-of-the-Money (OTM) or slightly Above-the-OB strike to.
            Selection                                       benefit from time decay ($\theta$)

            Stop Loss (SL)                                  Place the SL a few points above the highest wick of the identified Order Block.
            Take Profit (TP)                                Target the next major support level or wait for RSI to hit the 40-30 range.

    """

    _logger_ = AppLogger().get_log()
    __data_analyser__ = DataAnalyser

    CONFIG = {
        'START_TIME': "06:00",  # Entry time in IST (24h format)
        'TRY_END_TIME': dtime(21, 15),  # Keep try for punching trade upto this 8:15 AM
        'TRAIL_FREQUENCY': 1,  # Trail frequency in minutes
        'GOAL_TARGET_PROFIT_INR': 33.24,
        'GOAL_STOP_LOSS_INR': 22.16,  # our goal sl actual  need to calculated as per premium collected
        'LOT_SIZE_BTC': 0.005  # Quantity in btc 7 lots but need to be calculated as per combined premium
    }

    def trade_job(self, market_):
        pass
