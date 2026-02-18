from pprint import pprint

import pandas as pd

from OTApp.DataCollectors.DeltaExchangeDataCollector import DataCollector
from OTApp.Indicators.Indicator import Indicator
from OTApp.Logger.Logger import AppLogger


class Market:
    _loger_ = AppLogger().get_log()

    def check_market_trend(self):
        pass

    def market_sideways(self, symbol, resolution, limit):
        haan = False
        price_trend = ''
        over_xtended = ''
        trend = ''
        strangle_points = 0
        """
        The Correct Workflow
        The best practice is to calculate your technical indicators using the full 150 candles first, 
        and then slice the data for your Order Block function.
        
        1.Fetch: 150 candles.
        2. Calculate Indicators: Use all 150 candles for SuperTrend/ADX / rsi etc ... 
           or slice the fetched data according to indicator's requirements.
        3. Slice for OBs: Pass the last 30 or 50 candles to the Order Block function to find the 
           most recent institutional zones.
        """
        candles = DataCollector().get_candles(symbol, resolution, 150)
        df_for_all = pd.DataFrame(candles)
        indicator = Indicator()

        # 1. Getting price movement within given resolution
        price_change_pct = self.price_movement_pc(df_for_all, symbol, resolution, limit)
        # Filter Logic: If move > 5%, it's too trending for a Strangle
        if price_change_pct > 5.0:
            price_trend = "TREND_UP"
        elif price_change_pct < -5.0:
            price_trend = "TREND_DOWN"
        else:
            haan = True
            price_trend = "SIDEWAYS"
            self._loger_.info("Price Movement : ✅ Market looks sideways. Safe to proceed...")

        # 2. Checking the slope of the 20-period Simple Moving Average (SMA)
        sma_slope = indicator.sma_slope(df_for_all, symbol, resolution)

        # Combined Logic for Strangle Safety
        # Threshold: Slope < 0.05% and Price Change < 5%
        # if abs(sma_slope) < 0.05 and abs(price_change_24h) < 5.0:
        if abs(sma_slope['sma_slop_val']) < 0.05 and abs(price_change_pct) < 5.0:
            trend = "STABLE_SIDEWAYS"
            strangle_points = strangle_points + 1
            self._loger_.info("+SMA Slope: ✅ 💎 Stable conditions. Delta 0.15 Strangle is high probability.")
            haan = True
        elif sma_slope['sma_slop'] == "TREND_UP" and price_trend == 'TREND_UP':
            trend = 'TREND_UP'
            self._loger_.warning(
                "⚠️ Market is too trending & pumping! 🚀. Skipping Strangle to avoid Gamma risk. Consider Bullish "
                "spreads.")
            haan = False
        elif sma_slope['sma_slop'] == "TREND_DOWN" and price_trend == 'TREND_DOWN':
            trend = 'TREND_DOWN'
            self._loger_.warning(
                "⚠️ Market is too trending & dumping! 📉. Skipping Strangle to avoid Gamma risk. Consider Bullish "
                "spreads.")
            haan = False

        # 3. Checking RSI for oversold and overbought level
        rsi_response = indicator.get_exchange_matching_rsi(df_for_all, symbol, resolution)
        rsi = rsi_response['rsi']
        is_rsi_neutral = 40 < rsi < 60

        """
            Why RSI + SMA Slope is the "Gold Standard"
        
            -SMA Slope detects Trending vs. Sideways.
            -RSI detects Exhaustion.
            
            If SMA Slope is flat but RSI is at 75, it means the market has just finished a huge pump and is "resting." 
            Often, a second leg of volatility follows immediately. 
            By checking both, you ensure you only trade when the market is truly "quiet."
        """
        if is_rsi_neutral and trend == "STABLE_SIDEWAYS":
            trend = "PERFECT_SIDEWAYS"
            strangle_points = strangle_points + 1
            self._loger_.info("+RSI : ✅ 💎 💎 Perfect conditions. Delta 0.15 Strangle is high probability.")
            haan = True
        # Good sign for market exhausted,...fall will soon
        elif rsi >= 70 and trend == 'STABLE_SIDEWAYS':
            trend = "OVERBOUGHT_EXHAUSTED"
            over_xtended = 'OVERBOUGHT'
            self._loger_.critical(
                "⚠️ Market is overbought! 🟥 and exhausted. Skipping Strangle as these levels often precede a sharp, "
                "volatile reversal. Consider Bearish spreads or Bearish")
            haan = False
        elif rsi >= 70 and trend == 'TREND_UP':
            trend = "OVERBOUGHT_TRENDING_UP"
            over_xtended = 'OVERBOUGHT'
            self._loger_.warning(
                "⚠️ Market is overbought! 🟥 . Skipping Strangle as these levels often precede a sharp, volatile "
                "reversal. Consider Bearish spreads or Bearish")
            haan = False
        # Good sign for go short
        elif rsi >= 70 and trend == 'TREND_DOWN':
            trend = "OVERBOUGHT_TRENDING_DOWN"
            over_xtended = 'OVERBOUGHT'
            self._loger_.critical(
                "⚠️ Market is overbought! 🟥 . & trending down skipping Strangle good sign for reversal trade the "
                "market Consider Bearish spreads or Bearish")
            haan = False
        elif rsi <= 25 and trend == 'TREND_DOWN':
            trend = "OVERSOLD_TRENDING_DOWN"
            over_xtended = 'OVERSOLD'
            self._loger_.warning(
                "⚠️ Market is oversold! 🟩 . Skipping Strangle as these levels often precede a sharp, volatile "
                "reversal. Consider bull spreads or Bullish ...")
            haan = False
        # Good sign for go long
        elif rsi <= 25 and trend == 'TREND_UP':
            trend = "OVERSOLD_TRENDING_UP"
            over_xtended = 'OVERSOLD'
            self._loger_.critical(
                "⚠️ Market is oversold! 🟩 . Skipping Strangle , goog sign for long trade "
                " Consider bull spreads or Bullish ...")
            haan = False
        #  over sold and exhausted good sign for go long
        elif rsi <= 25 and trend == 'STABLE_SIDEWAYS':
            trend = "OVERSOLD_EXHAUSTED"
            over_xtended = 'OVERSOLD'
            self._loger_.critical(
                "⚠️ Market is oversold! 🟩 and exhausted. Skipping Strangle , goog sign for long trade "
                " Consider bull spreads or Bullish ...")
            haan = False

        # Super_trend
        super_trend = indicator.get_supertrend_status(df_for_all, symbol=symbol, resolution=resolution,
                                                      period=10, multiplier=3)

        if trend == 'PERFECT_SIDEWAYS' and haan and super_trend['flat'] and 'SIDEWAYS' in super_trend['super_trend']:
            strangle_points = strangle_points + 1
            self._loger_.info("Super Trend : ✅ 💎 💎 💎 Super conditions Strangle is high probability.")
            if 'CONFIRM' in super_trend['super_trend']:
                self._loger_.critical(
                    "Super Trend : ✅ 💎 💎 💎 💎 💎 Ultimate Green Light ON Strangle is high probability.")
                strangle_points = strangle_points + 1
        elif trend == 'STABLE_SIDEWAYS' and haan and super_trend['flat'] and 'SIDEWAYS' in super_trend['super_trend']:
            strangle_points = strangle_points + 1
            self._loger_.info("Super Trend :  ✅ 💎 💎 💎 Super conditions Strangle is high probability.")
            if 'CONFIRM' in super_trend['super_trend']:
                strangle_points = strangle_points + 1
                self._loger_.critical("Super Trend : ✅ 💎 💎 💎 💎 Green Light ON Strangle is high probability.")
        elif super_trend['super_trend'] == 'BEARISH_SIDEWAYS_CONFIRM':
            strangle_points = strangle_points + 1

        # Calculating swing high and low
        swings = indicator.get_swings(df_for_all, symbol=symbol, resolution=resolution, window=2)
        self._loger_.info(f"Puts should closed when market crossing or crossed below {swings['swing_low']}"
                          f" And Call should closed when marker crossing or crossed up {swings['swing_high']}")

        # Calculating Order block
        """
        Validated Bearish OB above price	✅ Safe to sell Call. The OB acts as a ceiling for your 0.15 Delta.
        Validated Bullish OB below the proce  ✅ Safe to sell Put. The OB acts as a resistance
        """
        obs = indicator.find_order_blocks(df_for_all)
        if not obs and (trend == 'STABLE_SIDEWAYS' or trend == 'PERFECT_SIDEWAYS'):
            self._loger_.info(
                f"👉 ACTION: OB-Safe to Enter 0.15 Delta Strangle")
            self._loger_.critical("Order Block : ✅ 💎 💎 💎 💎 Green Light ON Strangle is high probability.")
            strangle_points = strangle_points + 1
            if 'CONFIRM' in super_trend['super_trend']:
                self._loger_.critical(
                    "Order Block : ✅ 💎 💎 💎 💎 💎 💎 Ultimate++ Green Light ON Strangle is high probability.")

        return {
            'sideways': haan,
            'price_trend': {
                'trend': price_trend,
                'price_change_pct': abs(price_change_pct)
            },
            'sma_slope': sma_slope,
            'over_xtended': over_xtended,
            'rsi': rsi,
            'market_trend': trend,
            'super_trend': super_trend,
            'strangle_points': strangle_points,
            'order_block': obs,
            'swings': swings
        }

    def price_movement_pc(self, df_for_all, symbol, resolution, limit):
        """

        Adding a Market Trend Filter is a sophisticated upgrade. Selling a strangle is a "Neutral" strategy,
        meaning it performs best when the market is sideways. If Bitcoin is in a Strong Trend (pumping or dumping hard),
        your 0.15 Delta strikes are much more likely to be hit.
            1. The Trend Logic
                A common professional filter for a Strangle is to check the RSI (Relative Strength Index) or the SMA (Simple Moving Average).

                The Rule: If the market is "Overbought" or "Oversold," the risk of a sharp reversal is high. If the trend is too strong, we skip the trade to stay safe.
                        :param symbol:
                        :param resolution:
                        :return: int value in % term

        :param symbol: like 'BTCUDD'
        :param resolution:
        :param limit:
        :return:

        for example call as  : candles = DataCollector().get_candles('BTCUSD', '1h', 24)
        Resolution: Supported intervals include 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 1d

        """
        df_sorted = df_for_all.sort_values('time', ascending=True).copy()
        candles = df_sorted.to_dict(orient='records')[-24:]
        closing_prices = [float(c['close']) for c in candles]
        current_price = closing_prices[-1]
        start_price = closing_prices[0]

        # 2. Calculate % change over the last 24h
        # price_change_pct = abs((current_price - start_price) / start_price) * 100
        price_change_pct = ((current_price - start_price) / start_price) * 100
        self._loger_.info(f"📈 📊 {limit}h Price Movement: {abs(price_change_pct):.2f}%")
        return price_change_pct

# result = Market().market_sideways('BTCUSD', '1h', 24)
# pprint(result)
