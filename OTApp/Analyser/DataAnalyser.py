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
