import math

from OTApp.Logger.Logger import AppLogger


class DataAnalyser:
    TARGET_DELTA = 0.15
    _logger_ = AppLogger().get_log()

    @classmethod
    def filter_15_delta_options(cls, jsonRespose):
        # Filter for Delta 0.15 option
        btc_options = [p for p in jsonRespose['result'] if
                       math.isclose(abs(float(p['greeks']['delta'])), DataAnalyser.TARGET_DELTA, abs_tol=0.01)]
        # print(f"Total BTC options: {len(btc_options)}")
        if (len(btc_options)) < 2:
            # Logger.AppLogger.logger.warning(f"System not able to get pair of {DataAnalyser.TARGET_DELTA} delta")
            return []
        else:
            # filter out the  nearest CE PE records
            # Separate the records into CE and PE lists 'contract_type': 'put_options' 'contract_type': 'call_options'
            ce_options = []
            pe_options = []
            for opt in btc_options:
                if opt['contract_type'] == 'put_options':
                    pe_options.append(opt)
                elif opt['contract_type'] == 'call_options':
                    ce_options.append(opt)
            btc_options.clear()
            if len(ce_options) == 1:
                btc_options.append(ce_options.pop(0))
            elif len(ce_options) > 1:
                btc_options.append(DataAnalyser.get_nearest_one(ce_options))
            # put side
            if len(pe_options) == 1:
                btc_options.append(pe_options.pop(0))
            elif len(pe_options) > 1:
                btc_options.append(DataAnalyser.get_nearest_one(pe_options))
        return btc_options

    @classmethod
    def get_nearest_one(cls, options):
        # Sort by the absolute difference between actual delta and target
        nearest = min(options, key=lambda x: abs(abs(float(x['greeks']['delta'])) - DataAnalyser.TARGET_DELTA))
        return nearest

    @classmethod
    def volatility_attractive(cls, json_response):
        # Filter for ATM option
        mark_iv = 0.0
        for option in json_response.get("result", []):
            try:
                # Extract and convert prices to float
                strike = float(option.get("strike_price", 0))
                spot = float(option.get("spot_price", 0))
                symbol = option.get("symbol", "N/A")
                # Check if the prices are within the specified interval
                if abs(strike - spot) <= 200:
                    mark_iv = option['quotes']['mark_iv']
                    # below commented code is for testing purpose
                    # matched_list.append({
                    #     "symbol": symbol,
                    #     "strike_price": strike,
                    #     "spot_price": spot,
                    #     "mark_iv": mark_iv,
                    #     "difference": round(abs(strike - spot), 2)
                    # })
            except (ValueError, TypeError):
                cls._logger_.error(f"Got error while analysing the IV crash...")
        return mark_iv * 100

    def evaluate_strangle_entry(self, validated_ob, current_price, call_strike, put_strike):
        """
        your bot should check if these strikes are outside the protection of the Order Block. In a 0.15 Delta Strangle, the Order Block should sit between the current price and your strike, acting as a "shield."
        1. The "Shield" Logic for Strikes
        For a professional bot, you don't just want to know if an OB exists; you want to know if your strike is safely "hidden" behind it.
        Call Strike Safety: The call_strike should be higher than the bearish_ob_top.
        Put Strike Safety: The put_strike should be lower than the bullish_ob_bottom.

        :param validated_ob:
        :param current_price:
        :param call_strike:
        :param put_strike:
        :return:
        """
        # 2. Logic for decision-making
        if not validated_ob:
            self._logger_.info("⚪ RESULT: No Validated OB found. Proceeding with Normal Entry.")
            self._logger_.info(
                f"👉 ACTION: OB-Safe to Enter 0.15 Delta Strangle (C: {call_strike}, P: {put_strike})")
            return True
        ob_type = validated_ob['type']
        ob_top = validated_ob['top']
        ob_bottom = validated_ob['bottom']

        # 🔴 CASE: Bearish OB Detected (Potential Ceiling)
        if ob_type == 'BEARISH':
            if ob_bottom > current_price and call_strike > ob_top:
                self._logger_.info(f"✅ RESULT: Validated Bearish OB detected at {ob_bottom}-{ob_top} (Above Price).")
                self._logger_.info(f"🛡️ ACTION: Safe to sell Call {call_strike}. The OB acts as a structural ceiling.")
                return True
            else:
                self._logger_.warning(f"⚠️ ALERT: Price is currently INSIDE or ABOVE a Bearish OB. Risk of breakout!")
                return False

        # 🟢 CASE: Bullish OB Detected (Potential Floor)
        if ob_type == 'BULLISH':
            # Check if price is approaching or "hitting" the Bullish OB
            if current_price <= ob_top and current_price >= ob_bottom:
                self._logger_.error(f"🚫 RESULT: Price has HIT a Bullish OB zone ({ob_bottom}-{ob_top}).")
                self._logger_.error(
                    "⛔ ACTION: DO NOT sell Call/Strangle. Massive bounce expected from institutional buy zone.")
                return False
            elif current_price > ob_top and put_strike < ob_bottom:
                self._logger_.info(f"🛡️ RESULT: Validated Bullish OB exists below price at {ob_bottom}.")
                self._logger_.info(
                    f"✅ ACTION: Safe to sell Put {put_strike}. The OB acts as a structural floor. is protected by Bullish OB {ob_bottom}.")
                return True
        return False

    def check_liquidity_sweep(self, df, last_sh, last_sl):
        """
        Liquidity Sweeps: The "Fake-Out" Detection
        A Liquidity Sweep happens when the price briefly pierces a major Swing High or Low to
        trigger stop-loss orders, then immediately reverses.

        A sweep is confirmed when:

            The Piercing: The current candle's wick goes above a recent Swing High (Buyside Liquidity)
                          or below a Swing Low (Sellside Liquidity).
            The Rejection: The candle closes back inside the previous range.
            The Confirmation: The following candle moves strongly in the opposite direction.

        By combining these, your bot can avoid the "Breakout Trap.

        Scenario                    Market Action                       Bot Decision
        Price hits Swing High       Just a level touch.                 ⚠️ Wait for more data.
        Liquidity Sweep at High     Price wicks out and rejects.        ✅ Sell Calls. (The "Fake-out" is over).
        Price returns to Bullish OB Pullback to institutional buy zone. 🚫 Don't Sell Calls. (Expect a bounce).

        How to use it :
        --------------
            # Condition  (Swings):  Is your Call Strike > last_swing_high?
            #                       Is your Put Strike < last_swing_low?
            #  And liquidity sweep
            #  Check Sweeps: Did the price just "wick" through the Swing High and fail?
            #                If YES, the 0.15 Delta Call is safer because the "Smart Money"
                             just flushed out the buyers.

            in simple term : Sell call if you found BEARISH_SWEEP,
            #                Sell put if you found BULLISH_SWEEP,
            #
        """
        # df_sorted = df_for_all.sort_values('time', ascending=True).copy()
        # df = df_sorted
        # Get current candle data
        curr_high, curr_low, curr_close = df['high'].iloc[-1], df['low'].iloc[-1], df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]

        # 🔴 Bearish Sweep (Buy side Liquidity Grab)
        # Perfect time to sell the 0.15 Delta Call
        if curr_high > last_sh and curr_close < last_sh:
            return "BEARISH_SWEEP"

        # 🟢 Bullish Sweep (Sell side Liquidity Grab)
        # Perfect time to sell the 0.15 Delta Put
        if curr_low < last_sl and curr_close > last_sl:
            return "BULLISH_SWEEP"
        return None

    @classmethod
    def option_price_matched(cls, options_list, threshold_price=5.00):
        match_response = False
        larger_leg = ''
        leg_0_price_bid = float(options_list[0]['quotes']['best_bid'])
        leg_1_price_bid = float(options_list[1]['quotes']['best_bid'])
        leg_0_price_ask = float(options_list[0]['quotes']['best_ask'])
        leg_1_price_ask = float(options_list[1]['quotes']['best_ask'])
        bid_price_gap = abs(leg_1_price_bid - leg_0_price_bid)
        ask_price_gap = abs(leg_1_price_bid - leg_0_price_bid)
        if (bid_price_gap > threshold_price) or (ask_price_gap > threshold_price):
            cls._logger_.warning(
                f"⚠️  Price Gap Breach! Threshold: {threshold_price} | "
                f"Current Gaps -> [Bid: {bid_price_gap} 🔻] [Ask: {ask_price_gap} 🔺]"
            )
            #   finding leg to be taken care
            if (leg_0_price_ask > leg_1_price_ask) or (leg_0_price_bid > leg_1_price_bid):
                larger_leg = options_list[0]
            else:
                larger_leg = options_list[1]
            cls._logger_.info(
                f"⚖️  Leg Price Mismatch! | Action Required on: {larger_leg['symbol']} | "
                f"Initiating leg management protocols..."
            )
        else:
            match_response = True
            cls._logger_.info(
                f"🎯 Price Gap Matched! | Threshold: {threshold_price} | "
                f" Gaps -> [Bid: {bid_price_gap} 🔻] [Ask: {ask_price_gap} 🔺] | "
                f"🚀 Proceeding..."
            )
        return {"price_matched": match_response,
                "gaps": {'ask': {ask_price_gap}, 'bid': {bid_price_gap}},
                "larger_leg": larger_leg}

    @classmethod
    def filter_options(cls, json_response, delta=12, leg=None):
        # Assumption :   To find lower leg we should try to get same price leg first then lower delta

        """
        Finds a leg on the specified leg side that is almost matched the target_price,
        starting from 15 delta and moving further OTM.
        """
        # Filter legs for the correct side, sorted by delta descending (starting at 15)
        potential_legs = [p for p in json_response if
                          p['contract_type'] == leg['contract_type'] and
                          float(p['greeks']['delta']) < 0.15]
        potential_legs.sort(key=lambda x: float(x['greeks']['delta']), reverse=True)

        for leg in potential_legs:
            leg_price = float(leg.get('mark_price', 0))
            if math.isclose(leg_price, leg['mark_price'], abs_tol=5.0):
                cls._logger_.info(
                    f"🎯 Selected Lower-Price Leg: {leg['symbol']} | "
                    f"Δ: {leg['greeks']['delta']} 📉 | Price: {leg_price} 💰"
                )
                return leg  # Found the price-matched lower-delta leg
        return potential_legs[-1]  # Fallback to the furthest OTM if no match

    @classmethod
    def protected_by_ob(cls, leg, ob):
        protected = False
        leg_contract = leg['contract_type']
        # OB structure as {'type': 'BEARISH', 'top': df['high'].iloc[i], 'bottom': df['low'].iloc[i]}
        if not ob:
            cls._logger_.info(f"Leg {leg['symbol']} not protected by OB")
        elif leg_contract == 'put_options' and ob[
            'type'] == 'BULLISH' and ob[
            'bottom'] >= float(leg['strike_price']):

            """
            # Validated Bullish OB below the Strike price  ✅ Safe to sell Put. The OB acts as a resistance
            """
            protected = True
            cls._logger_.info(
                f"🛡️  LEG PROTECTED | {leg['symbol']} | "
                f"Bullish OB Found at {ob['bottom']} 🧱 "
                f"acting as support below Strike {leg['strike_price']} ✅"
            )
        elif leg_contract == 'call_options' and ob['type'] == 'BEARISH' and ob['top'] <= float(leg['strike_price']):
            """
            Validated Bearish OB above price	✅ Safe to sell Call. The OB acts as a ceiling for your 0.15 Delta.
            """
            protected = True
            cls._logger_.info(
                f"🏰 LEG FORTIFIED | {leg['symbol']} | "
                f"Bearish OB Found at {ob['top']} 🧱 "
                f"acting as resistance above Strike {leg['strike_price']} ✅"
            )
        return protected

    @classmethod
    def protected_by_swings_sweep(cls, leg, swings_with_sweep):
        """
        # Is leg is protected by
        # Condition  (Swings):  Is your Call Strike > last_swing_high?
        #                       Is your Put Strike < last_swing_low?
        #  And liquidity sweep
        #  Check Sweeps: Did the price just "wick" through the Swing High and fail?
        #                If YES, the 0.15 Delta Call is safer because the "Smart Money"
                         just flushed out the buyers.

        # swings structure with liquidity sweeps
            {'swing_low': last_sl, 'swing_high': last_sh, 'liquidity_sweep': liquidity_sweep}
        """
        protected = False
        leg_contract = leg['contract_type']
        if not swings_with_sweep:
            # No structural data found at all
            cls._logger_.info(f"🔍 Leg {leg['symbol']} | No swing structure detected. Scanning further... 💨")
        elif leg_contract == 'put_options' and swings_with_sweep['liquidity_sweep'] == 'BULLISH_SWEEP':
            # Found a liquidity sweep, which is a strong reversal signal
            cls._logger_.info(
                f"🌊 BULLISH SWEEP DETECTED | Side: {leg_contract} | "
                f"Market cleared liquidity. Checking swing protection... 🔍"
            )
            if float(leg['strike_price']) <= swings_with_sweep['swing_low']:
                # The leg is safely tucked below the swing low
                protected = True
                cls._logger_.info(
                    f"🛡️  PUT PROTECTED | {leg['symbol']} | "
                    f"Strike {leg['strike_price']} is below Swing Low {swings_with_sweep['swing_low']} ✅"
                )
        elif leg_contract == 'call_options' and swings_with_sweep['liquidity_sweep'] == 'BEARISH_SWEEP':
            # Found a liquidity sweep, which is a strong reversal signal
            cls._logger_.info(
                f"🌊 BEARISH SWEEP DETECTED | Side: {leg_contract} | "
                f"Market cleared liquidity. Checking swing protection... 🔍"
            )
            if float(leg['strike_price']) >= swings_with_sweep['swing_high']:
                protected = True
                cls._logger_.info(
                    f"🛡️  CALL PROTECTED | {leg['symbol']} | "
                    f"Strike {leg['strike_price']} is above Swing high {swings_with_sweep['swing_high']} ✅"
                )
        return protected
