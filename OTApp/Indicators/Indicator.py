from pprint import pprint

import numpy as np
import pandas as pd
import pandas_ta_classic as ta

from OTApp.DataCollectors.DeltaExchangeDataCollector import DataCollector
from OTApp.Logger.Logger import AppLogger


class Indicator:
    _loger_ = AppLogger().get_log()

    def sma_slope(self, symbol, resolution):
        """
        ***The method help to analyse market trend  ***

        Professional Trend Confirmation: The "SMA Slope"
        If you want to be even more precise, don't just look at the start and end price. Check the slope of the 20-period Simple Moving Average (SMA).

        Adding the SMA Slope check is a brilliant move to eliminate "False Positives."
        A market might look sideways because the price is the same as it was 24 hours ago,
        but if the SMA is pointing sharply up or down in between,
        you're in a "V-recovery" or "Inverted V"—both of which are dangerous for Strangles.

        The slope tells you the velocity of the trend.
        For a Strangle, we want a "Flat" slope (near zero).
            1. The SMA Slope Logic We calculate the 20-period SMA for the current candle and the candle from 3-5 periods ago.

                Calculation: Slope = (SMA_current - SMA_past)/n
                Threshold: If the slope is too steep (e.g. > 0.1% change per hour),
                we label it as "Trending."

        Bullish: Current SMA > SMA from 5 hours ago.

        Bearish: Current SMA < SMA from 5 hours ago.

        @:returns @sma_slope_val numeric calculation
                  @sma_slope : "STABLE_SIDEWAYS", "TREND_UP" , "TREND_DOWN" & "VOLATILE_UNKNOWN"
        """
        sma_slope = ''
        sma_slope_val = 0.0
        self._loger_.info(f"*** Checking SMA Slope for TREND UP ▲ /Down ▼ ...***")
        try:
            # 1. Fetch 24 candles for SMA (20) have enough data to "warm up"
            # We need 20 (for SMA) + 5 (for the lookback) = 25 candles
            candles = DataCollector().get_candles(symbol, resolution, 30)
            closes = [float(c['close']) for c in candles]
            # 2. Calculate Current SMA20 and Past SMA20 (5 hours ago)
            current_sma = sum(closes[-20:]) / 20
            past_sma = sum(closes[-25:-5]) / 20
            # 3. Calculate Slope (Percentage change in SMA per hour)
            sma_slope_val = ((current_sma - past_sma) / past_sma) * 100 / 5
            self._loger_.info(f"📊 SMA Slope: {sma_slope_val:.4f}% per hr")
            if abs(sma_slope_val) < 0.05:
                sma_slope = "STABLE_SIDEWAYS"
            elif sma_slope_val > 0.05:
                sma_slope = "TREND_UP"
            elif sma_slope_val < -0.05:
                sma_slope = "TREND_DOWN"
            else:
                sma_slope = "VOLATILE_UNKNOWN"
        except Exception as e:
            self._loger_.error(f"⚠️ Trend (sma_slope) calculation having error: {e}")
        return {
            'sma_slop': sma_slope,
            'sma_slop_val': sma_slope_val
        }

    def calculate_rsi(self, prices, period=14):
        deltas = np.diff(prices)
        seed = deltas[:period + 1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down
        rsi = np.zeros_like(prices)
        rsi[:period] = 100. - 100. / (1. + rs)

        for i in range(period, len(prices)):
            delta = deltas[i - 1]
            if delta > 0:
                up_val = delta
                down_val = 0.
            else:
                up_val = 0.
                down_val = -delta

            up = (up * (period - 1) + up_val) / period
            down = (down * (period - 1) + down_val) / period
            rs = up / down
            rsi[i] = 100. - 100. / (1. + rs)
        return rsi[-1]

    def get_exchange_matching_rsi(self, symbol, resolution, period=14):
        # Fetch 103 candles instead of 40 to allow for 'warm-up' why 103 need to talk
        candles = DataCollector().get_candles(symbol, resolution, 97)
        df = pd.DataFrame(candles)
        df['close'] = df['close'].astype(float)

        # Calculate price changes
        delta = df['close'].diff()

        # Separate gains and losses
        gain = (delta.where(delta > 0, 0))
        loss = (-delta.where(delta < 0, 0))

        # Wilder's Smoothing (RMA) calculation
        # Using 'com' (center of mass) where com = period - 1 is equivalent to alpha = 1/period
        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return {'rsi': rsi.iloc[-1], 'df_100': df}

    def get_synced_rsi(self, df, period=14):
        # Fetch 100 candles instead of 40 to allow for 'warm-up'
        candles = DataCollector().get_candles('BTCUSD', '1h', 97)
        df = pd.DataFrame(candles)
        # 1. Calculate price changes
        delta = df['close'].diff()

        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        # 2. Initialization: TradingView starts with a Simple Moving Average
        avg_gain = [np.nan] * len(df)
        avg_loss = [np.nan] * len(df)

        # The first 'average' is just the mean of the first 14 changes
        avg_gain[period] = gain[1:period + 1].mean()
        avg_loss[period] = loss[1:period + 1].mean()

        # 3. The Smoothing: Recursive Wilder's formula
        # Smoothed = ((Prev * 13) + Current) / 14
        for i in range(period + 1, len(df)):
            avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain.iloc[i]) / period
            avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss.iloc[i]) / period

        rs = np.array(avg_gain) / np.array(avg_loss)
        rsi = 100 - (100 / (1 + rs))

        return rsi[-1]

    def get_supertrend_status(self, df_100, symbol='BTCUSD', resolution='1h', period=10, multiplier=3):

        """
        Adding the SuperTrend indicator to your hourly chart is a masterclass in "Trend Confirmation."
        While the RSI and SMA Slope tell you if the market is quiet, the SuperTrend acts as a definitive Safety Fence.

        :param df_100:
        :param symbol:
        :param resolution:
        :param period:
        :param multiplier:
        :return:

            Market State ----       SuperTrend Signal	----- Action for 0.15 Delta Strangle
            Trending Up	Green for   > 10 candles	        🚫 Skip (Call side will get crushed)
            Trending Down Red for   > 10 candles	        🚫 Skip (Put side will get crushed)
            Choppy Just flipped    (1-3 candles)	        ✅ Ideal (Market is indecisive)

        """

        super_trend = 'UNKNOWN'
        flat = False
        try:
            # candles_direction_cal = DataCollector().get_candles(symbol, resolution, limit=97)
            df_direction = df_100
            df_direction['atr'] = ta.atr(df_direction['high'], df_direction['low'], df_direction['close'],
                                         length=period)
            st_direction = ta.supertrend(df_direction['high'], df_direction['low'], df_direction['close'],
                                         length=period, multiplier=multiplier)
            # SUPERTd column: 1 is Bullish (Green), -1 is Bearish (Red)
            direction_col = f'SUPERTd_{period}_{float(multiplier)}'
            current_direction = st_direction[direction_col].iloc[-1]
            if current_direction == 1:
                super_trend = 'BULLISH'
            elif current_direction == -1:
                super_trend = 'BEARISH'
            else:
                super_trend = 'MIX'

            """
            A "flat" SuperTrend line is a classic sign of a sideways market where volatility has dropped, 
            and the price is oscillating within a tight range without hitting a new High or Low. In your Python bot, 
            you can catch this situation by checking the rate of change of the SuperTrend line over the last few candles. 
            If the value hasn't changed (or has changed by less than 0.01%), you are in a "Flat Zone."
            
            How to use it :
            
            SuperTrend Shape	Market Condition	Strangle Action
            Steep Slope	        Aggressive Trend	🚫 Do Not Trade (High Gamma Risk)
            Stair-stepping	    Slow Trend	        ⚠️ Caution (Possible drift)
            Long Flat Line	    Consolidation	    ✅ Ideal Entry (Selling Volatility)
            
            """
            candles_flateness_cal = DataCollector().get_candles(symbol, resolution, limit=50)
            df_flatness = pd.DataFrame(candles_flateness_cal)
            # Calculate ATR first using Wilder's
            df_flatness['atr'] = ta.atr(df_flatness['high'], df_flatness['low'], df_flatness['close'], length=period)
            st_flatness = ta.supertrend(df_flatness['high'], df_flatness['low'], df_flatness['close'], length=period,
                                        multiplier=multiplier)
            # 2. Extract the 'st_series' (the line values)
            st_series = st_flatness['SUPERT_10_3.0']
            if self.is_supertrend_flat(st_series):
                flat = True
                super_trend = super_trend + '_SIDEWAYS'
            self._loger_.info(f"⏸️ SuperTrend : {super_trend} , Flatness :{flat} on {resolution} time frame ")

            """
            Refining with ADX (The Strength Meter)
               If you want to be 100% sure the "flatness" isn't just a trap before a breakout, traders often use the 
               ADX (Average Directional Index).
                   ADX < 20: The market is weak/sideways (Confirming the Flat SuperTrend).
                   ADX > 25: A trend is starting (Even if the SuperTrend looks flat for a moment, 
                   the ADX warns you to stay out).
                   
                   The "Ultimate Green Light" LogicTo make your bot truly professional, 
                   combine SuperTrend Flatness and ADX Strength. This creates a "double-lock" safety mechanism for your 
                   option entries.
                   
                   SuperTrend       ADX Value       Market Context                  Strangle Entry
                   Flat             < 20            Deep Sleep (Low Vol)            ✅ Perfect Entry
                   Flat             20 - 25         Awakening                       ⚠️ Proceed with Caution
                   Flat             > 25            "The Trap" (Breakout imminent)  🚫 DO NOT ENTER
                   Sloping          Any             Trending                        🚫 DO NOT ENTER
            """
            adx = self.get_adx(df_flatness)
            if adx['is_sideways'] and flat:
                super_trend = super_trend + '_CONFIRM'
                self._loger_.critical(f"⏸️ ⏸️ SuperTrend : {super_trend}  on {resolution} time frame ")
            return {'super_trend': super_trend, 'flat': flat, 'adx': adx}
        except Exception as e:
            self._loger_.error(f"⚠️ SuperTrend Error: {e}")
            return super_trend

    def is_supertrend_flat(self, st_series, threshold=5):
        """
        Checks if the SuperTrend line has been identical for the last 'threshold' candles.
        st_series: The 'SUPERT_10_3.0' column from your dataframe
        """
        # Look at the last 'threshold' values
        recent_values = st_series.iloc[-threshold:]
        # If the maximum value minus the minimum value is 0, it is perfectly flat
        return recent_values.max() == recent_values.min()

    def get_adx(self, df, length=14):

        """
        Integrating ADX (Average Directional Index) is the smartest way to filter your 0.15 Delta Strangle.
        While a flat SuperTrend tells you the market is sideways, the ADX tells you if it has the strength to
        stay that way.

        In a Strangle, your worst enemy is a "Fakey"—a flat period that suddenly explodes into a trend. ADX acts as your early warning system.
        :param length:
        :param df:
        :return:
        """
        # 1. Calculate ADX
        # This returns a DataFrame with columns like 'ADX_14', 'DMP_14', 'DMN_14'
        adx_df = df.ta.adx(length=length)

        # 2. Get the most recent ADX value
        current_adx = adx_df[f'ADX_{length}'].iloc[-1]

        # 3. Determine if it's safe for a Strangle
        # ADX < 20 is the "Golden Zone" for sideways trading
        is_sideways = current_adx < 25

        return {'is_sideways': is_sideways, 'adx': current_adx}

    def get_swings(self, symbol='BTCUSD', resolution='1h', window=2):
        """
        Adding Swing Highs and Swing Lows is a major upgrade for your bot's risk management.
        While the SuperTrend tells you the current "mood," Swing points provide the actual
        "Battle Lines" where the market is likely to reverse or accelerate.
        For a 0.15 Delta Strangle, these points are your Stop Loss anchors. If the market breaks a major Swing High,
        your Call option is in immediate danger.

        What is a "Swing" Point?
        A technical Swing High is a candle whose High is higher than the candles immediately to its left and right.
            Swing High: High[n] > High[n-1] AND High[n] > High[n+1]
            Swing Low: Low[n] < Low[n-1] AND Low[n] < Low[n+1]
        To make it robust for a bot, we usually look for a 3-candle or 5-candle window (also known as a Fractal)
        to ensure it's a meaningful peak.
        Detects Swing Highs and Lows using a window on both sides.
        window=2 means it checks 2 candles before and 2 after (5-candle fractal).
            :param resolution:
            :param symbol:
            :param df:
            :param window:
            :return:
        """

        last_sh = 0.0
        last_sl = 0.0
        try:
            candles = DataCollector().get_candles(symbol, resolution, limit=24)
            df = pd.DataFrame(candles)
            # 1. FORCE numeric conversion on all OHLC columns
            # 'coerce' turns any non-number (like "N/A" or "") into NaN
            cols = ['open', 'high', 'low', 'close']
            for col in cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # Swing High: Highest in the surrounding window
            df['swing_high'] = df['high'][
                (df['high'] == df['high'].rolling(window=window * 2 + 1, center=True).max())
            ]
            # Swing Low: Lowest in the surrounding window
            df['swing_low'] = df['low'][
                (df['low'] == df['low'].rolling(window=window * 2 + 1, center=True).min())
            ]

            # Get the most recent valid points
            last_sh = df['swing_high'].dropna().iloc[-1]
            last_sl = df['swing_low'].dropna().iloc[-1]

            self._loger_.info(f"Latest Resistance : {last_sh}  Latest Support : {last_sl}")
        except Exception as ex:
            self._loger_.error(f"Swing calculation having issue {ex}")

        return {'swing_low': last_sl, 'swing_high': last_sh}

# print(f"Matched RSI {Indicator().get_synced_rsi([])}")
# pprint(Indicator().get_supertrend_status([]))
