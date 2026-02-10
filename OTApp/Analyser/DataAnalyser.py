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
