import time
from datetime import datetime, time as dtime
from typing import Any

from requests import Response

from OTApp.Analyser import DataAnalyser
from OTApp.Analyser.Trend import Market
from OTApp.Configuration.AppConfig import Config
from OTApp.DataCollectors.DeltaExchangeDataCollector import DataCollector
from OTApp.Logger.Logger import AppLogger
from OTApp.Margin.Margin import Margin
from OTApp.Order.OrderManager import OrderManager
from OTApp.Persistence.History.TradeMunshi import TradeMunshi


class BTC_15_Delta_Strangle:
    _loger_ = AppLogger().get_log()
    __data_analyser__ = DataAnalyser
    __strategy_name__ = 'btc_15_delta_strangle'
    CONFIG = {
        'START_TIME': "06:00",  # Entry time in IST (24h format)
        'TRY_END_TIME': dtime(hour=10, minute=15, tzinfo=Config.TIME_ZONE),
        # Keep try for punching trade upto this 8:15 AM
        'TRAIL_FREQUENCY': 1,  # Trail frequency in minutes
        'GOAL_TARGET_PROFIT_INR': 33.24,
        # Your goal, actual  need to calculated as per premium collected with ration 2/3
        'GOAL_STOP_LOSS_INR': 22.16,  # our goal sl actual  need to calculated as per premium collected
        'LOT_SIZE_BTC': .005  # Quantity in btc 7 lots but need to be calculated as per combined premium
    }

    def trade_job(self):
        self._loger_.critical(f"--- Window Opened at {datetime.now().strftime('%H:%M:%S')} ---")
        # Define the hard cutoff
        cutoff_time = BTC_15_Delta_Strangle.CONFIG['TRY_END_TIME']
        while True:
            now = datetime.now(Config.TIME_ZONE).time()
            # 1. Check if we have passed 8:15 AM
            if now > cutoff_time:
                self._loger_.warning(
                    f"Time limit {cutoff_time.strftime('%H:%M')} reached. Closing window for today.")
                break
            # elif trend should be a side way hourly rsi should not over sold below 23 or over bought ( not yet defined)
            self._loger_.info(f"[{datetime.now().strftime('%H:%M')}] Attempting to fetch and process data...")
            try:
                # checking for side way market
                market_check = Market().market_sideways('BTCUSD', '1h', 24)
                # Will go ahead if strangle point > 2 only ...
                if market_check['strangle_points'] >= 3:
                    trade_record = None
                    self._loger_.critical(
                        f"***Market side ways with strangle_points {market_check['strangle_points']} good to initiate trade***")
                    # # if no_trade false then goahead of trade
                    # no_trade = True
                    # 2. Fetch fresh option chain data until len(option_list)==2 upto 5 mins for every 30 sec to 60 sec
                    #  after 5 trial check the whole scenario again
                    responses = None
                    options_list = []
                    options_list, responses, ivr = self.get_option_pair(options_list, responses)
                    ivr_value = ivr['ivr']
                    # Volatility Crush check
                    if ivr_value < 25.0:
                        # 🧊 "Ice" Icon for Consolidation
                        self._loger_.critical(
                            f"🧊  IV RANK TOO LOW: {ivr_value:.2f} | "
                            f"\nStatus: 🏷️ Cheap Premiums / 🧨 High Spike Risk | "
                            f"\nAction: Skipping Trade for Capital Preservation 🛑 "
                            f"\n...Sleep for 15m....."
                        )
                        # wait 15m and continue
                        """
                        The 15-Minute "Pulse" (Recommended)
                            For BTC daily options, 15 minutes is the "sweet spot" for your next iteration.
                            Why? 
                            BTC volatility can "wake up" extremely fast due to sudden liquidations. 
                            A 5-minute wait is often too noisy (just minor bid/ask flickering), 
                            but a 1-hour wait might miss the initial "pop" where premiums are highest.
                        """
                        time.sleep(BTC_15_Delta_Strangle.CONFIG['TRAIL_FREQUENCY'] * 60 * 14)
                        continue
                    elif len(options_list) == 2:
                        trade_record = {'market_check': market_check, 'initial_legs': options_list.copy(), 'ivr': ivr,
                                        'trade_symbol': self.__strategy_name__}
                        # Need to check price matching condition before placing order
                        price_match_response = DataAnalyser.DataAnalyser.option_price_matched(options_list)
                        trade_record.update({'price_match_response': price_match_response})
                        """
                           Suppose if price does not match 
                            # Remaining case 
                            1.1 check the trends in 12 h time frame
                                1.1.1 Case study if trend is bearish on 12 h time frame, lower down the PE leg to match the price similarly for CE side
                       """
                        if not price_match_response['price_matched']:
                            un_matched_leg_handle_resp = self.handle_un_matched_legs(market_check=market_check,
                                                                                     options_list=options_list,
                                                                                     price_match_response=price_match_response,
                                                                                     responses=responses.json())
                            options_list = un_matched_leg_handle_resp['final_legs']
                            trade_record.update({'un_matched_leg_handle_resp': un_matched_leg_handle_resp})

                        if ivr_value > 25.0:
                            self.log_ivr_state(ivr, ivr_value)
                            # calculating sl and lots as per max daily loss
                            # combine premium collection
                            trade = self.calculate_trade(options_list)
                            if trade['max_sell_lots'] <= 0:
                                raise ValueError("Calculated lot size is zero. Check liquidity.")
                            leverage = trade.get('leverage', 0)
                            spot_price = trade.get('spot_price', 0)
                            total_premium = trade.get('total_premium', 0)
                            trade_record.update({'trade': trade})

                            # Margin calculation ------------
                            margin_sufficient = Margin().margin_sufficient(leverage, spot_price, total_premium,
                                                                           BTC_15_Delta_Strangle.CONFIG['LOT_SIZE_BTC'])
                            trade_record.update({'margin_sufficient': margin_sufficient})
                            if margin_sufficient:
                                # Place order
                                place_trade_resp = OrderManager().place_orders(trade_record)
                                # Update trade_record with the actual execution results for history analysis
                                trade_record['execution_history'] = place_trade_resp
                                # Save all market analysis data for later use
                                # TradeMunshi().save_trade_snapshot(trade_record)
                                TradeMunshi().save_trade_snapshot_thread_support(trade_record)
                                # Invoke trade fill monitoring we called it Nigrani

                                # OrderFillChaukidar().order_nigrani(trade_record)
                                # start trade
                                break
                            else:
                                self._loger_.error(
                                    f"🚫 INSUFFICIENT MARGIN | "
                                    f"Required: ? | "
                                    f"Available: ? | "
                                    f"Shortfall: -? 💸 | "
                                    f"Action: Order Aborted"
                                )
                        else:
                            self._loger_.warning(
                                f"⚠️  STRATEGY INHIBITED | IVR: {ivr:.2f} | "
                                f"Target: >=85.0 | "
                                f"Status: Waiting for Volatility Spike... ⏳"
                            )
                    else:
                        self._loger_.warning(f" ⚠️ No Options Pair Found ")
                    # **** Need to envoke monitoring stuff here or integrate trade monitoring logic here ....

                    # If you want to stop entirely for the day after the first successful
                    # data processing, you could 'break' here.
                    # Otherwise, it will re-fetch in 1 minute.
                    # Wait for 1 minute before the next attempt/recheck
                    time.sleep(BTC_15_Delta_Strangle.CONFIG['TRAIL_FREQUENCY'] * 60 * 1)
                else:
                    self._loger_.info(
                        f" Market does not looks side way ... "
                        f" Strangle Points : {market_check['strangle_points']} "
                        f" will check in {BTC_15_Delta_Strangle.CONFIG['TRAIL_FREQUENCY'] * 5 * 60} Seconds...")
                    time.sleep(BTC_15_Delta_Strangle.CONFIG['TRAIL_FREQUENCY'] * 60 * 3)
            except Exception as e:
                self._loger_.error(
                    f"Error fetching data: {e}. Will retry in {BTC_15_Delta_Strangle.CONFIG['TRAIL_FREQUENCY']} minute.")
                # 3. Wait for 1 minute before the next attempt/recheck
                time.sleep(BTC_15_Delta_Strangle.CONFIG['TRAIL_FREQUENCY'] * 60)

    def calculate_trade(self, options_list: list[Any] | bool | None | Any) -> dict[str, float | Any] | None:

        """
        Handles premium calculation, risk-sizing, and order placement
        with multi-layered exception handling.
        """
        try:
            # --- 1. Sizing & Logic (The calculation block) ---
            total_premium = 0.0
            spot_price = 0.0
            leverage = 0
            sell_lots = (BTC_15_Delta_Strangle.CONFIG['LOT_SIZE_BTC'])
            # 2. Premium Calculation with Error Handling
            for opt in options_list:
                symbol = opt.get('symbol', 'Unknown')
                bid = float(opt.get('quotes', {}).get('best_bid', 0))
                if bid <= 0:
                    self._loger_.warning(f"⚠️ Low liquidity for {symbol}. Bid is {bid}")

                total_premium += bid * sell_lots
                spot_price = float(opt.get('spot_price', 0.0))
                leverage = opt.get('leverage', 0)
            # 3. Risk Management Calculations
            # Strategy: SL is 2/3 of collected premium (standard short-vol protection)
            max_trade_sl_premium = total_premium * (2 / 3)
            self._loger_.info(f"Total Premium: {total_premium:.4f} | "
                              f"Max SL (Premium): {max_trade_sl_premium:.4f} | "
                              f"With configured lots {sell_lots}")
            # 4. Dynamic Position Sizing (The "Raavan" Shield)
            # Ensure we don't divide by zero if premium is 0
            if max_trade_sl_premium > 0:
                # Calculate how many lots we can sell to stay within our INR loss limit
                # Formula: (Budget INR / Expected Premium Loss)
                max_sell_lots = BTC_15_Delta_Strangle.CONFIG[
                                    'GOAL_STOP_LOSS_INR'] / max_trade_sl_premium
                #  max_sell_lots for .005 that is 5 lots so converting it to lots size
                max_sell_lots = int(max_sell_lots * (sell_lots * 1000))

                # leg_sl calculation: Points move required to hit the SL
                # Corrected formula to avoid potential sizing errors
                # leg_sl_points = (max_trade_sl_premium / max_sell_lots) * 1000
                # we need to calculate move of 1000 lots price for one leg
                leg_sl_points = (max_trade_sl_premium / (sell_lots * 1000)) * 1000
            else:
                max_sell_lots = 0
                leg_sl_points = 0
                self._loger_.error("❌ Zero premium detected. Halting trade execution.")
            # 5. Final Trade Record
            self._loger_.info(f"Final Max Sizing: {max_sell_lots:.2f} lots | "
                              f"Leg SL Points: {leg_sl_points:.2f} | "
                              f"Currently selling lots: {sell_lots}")

            trade = {
                "total_premium": round(total_premium, 6),
                "max_sell_lots": round(max_sell_lots, 4),
                "sell_lots": sell_lots,
                "max_trade_sl": round(max_trade_sl_premium, 6),
                "leg_sl_points": round(leg_sl_points, 2),
                "spot_price": spot_price,
                "leverage": leverage
            }
            return trade
        except KeyError as e:
            self._loger_.error(f"❌ Configuration Error: Missing key {e}")
        except ValueError as e:
            self._loger_.error(f"❌ Risk Management Halt: {e}")
        except Exception as e:
            self._loger_.critical(f"🔥 Unexpected System Failure: {e}")
            # self.emergency_halt()  # A todo: implement a function to cancel all pending orders

    def log_ivr_state(self, ivr, ivr_value):
        # Map icons to market states for visual clarity
        state_icons = {
            "Normal": "🟢",  # Conservative / Safe
            "High Volatility": "⚡",  # Aggressive / High Edge
            "Extreme Panic": "🚨"  # High Risk / Gamma Warning
        }
        # Determine the icon based on the current market state
        current_state = ivr.get('market_state', 'Normal')
        icon = state_icons.get(current_state, "🔍")
        self._loger_.info(
            f"{icon} [IVR: {ivr_value:.2f}] | State: {current_state} | "
            f"Action: {ivr['action']} | Target Delta: {ivr['target_delta']} Δ"
        )

    def get_option_pair(self, options_list: list[Any], responses: Response | None) -> tuple[
        list[Any] | Any, Response | None | Any, Any]:
        """
        In case of good scenario not need to fetch all data only need to fetch and assure
        we have two option with opposit contact for strangle

        :param options_list:
        :param responses:
        :return:
        """

        for attempt in range(1, 6):
            self._loger_.info(f"🔍 [Attempt {attempt}/5] Searching for option pair...")
            # 2. Fetch data
            responses = DataCollector.fetch_btc_options(today=DataCollector.today)
            # Volatility Crush check to get target delta in based on market situation
            ivr = DataAnalyser.DataAnalyser.volatility_attractive(json_response=responses.json())
            target_delta = ivr['target_delta']
            if target_delta is None:
                break
            else:
                # 3. Analyze/Filter data
                options_list = DataAnalyser.DataAnalyser.filter_15_delta_options(jsonRespose=responses.json(),
                                                                                 target_delta=target_delta)
                # 4. Check if we hit the "Golden Goal" (exactly 2 records)
                if len(options_list) == 2:
                    self._loger_.info("✅ SUCCESS | Found exactly 2 matching legs. Proceeding to trade...")
                    break  # 🏁 Exit the loop immediately
                # 5. Handle the "Not Found" case
                if attempt < 5:
                    self._loger_.warning(
                        f"⚠️ [Attempt {attempt}] Found {len(options_list)} legs with {target_delta} delta. Need exactly 2. "
                        f"Retrying in 10 seconds... ⏳"
                    )
                    time.sleep(10)  # 🛑 Wait for 30 seconds before next iteration
        return options_list, responses, ivr

    def handle_un_matched_legs(self, options_list, market_check,
                               price_match_response,
                               responses):
        try:
            # Is the lager leg protected by Order Block
            ob_protection = DataAnalyser.DataAnalyser.protected_by_ob(leg=price_match_response[
                'larger_leg'], ob=market_check['order_block'])
            swings_sweep_protection = None
            if not ob_protection:
                """
                # Is leg is protected by
                # Condition  (Swings):  Is your Call Strike > last_swing_high?
                #                       Is your Put Strike < last_swing_low?
                #  And liquidity sweep
                #  Check Sweeps: Did the price just "wick" through the Swing High and fail?
                #                If YES, the 0.15 Delta Call is safer because the "Smart Money" 
                                 just flushed out the buyers.
                # 
                """
                swings_sweep_protection = DataAnalyser.DataAnalyser.protected_by_swings_sweep(
                    leg=price_match_response[
                        'larger_leg'], swings_with_sweep=market_check['swings'])
                if not swings_sweep_protection:
                    # Handle larger leg either by lowering down the delta or get the same priced leg
                    self._loger_.warning(
                        f" larger price leg = {price_match_response['larger_leg']['strike_price']}"
                        f" does not have protection ... find the lower leg ...")
                    managed_leg = DataAnalyser.DataAnalyser.filter_options(
                        json_response=responses,
                        leg=price_match_response[
                            'larger_leg'], delta=10)

                    #  if managed leg found then removing the larger leg from the list and adding this leg
                    options_list.remove(price_match_response[
                                            'larger_leg'])
                    options_list.append(managed_leg)
            return {'final_legs': options_list, 'ob_protection': ob_protection,
                    'swings_sweep_protection': swings_sweep_protection}
        except Exception as e:
            self._loger_.error(f"Error while handling ")

# # --- Scheduler Setup ---
# scheduler = BlockingScheduler(timezone=Config.TIME_ZONE.zone)
# # This tells the scheduler to wake up at 06:00 every day
# scheduler.add_job(BTC_15_Delta_Strangle().trade_job, 'cron', hour=5, minute=00)
# AppLogger.logger.info("Scheduler active. The bot will check every minute between 06:00 and 08:15 IST daily.")
# try:
#     scheduler.start()
# except (KeyboardInterrupt, SystemExit):
#     AppLogger.logger.critical(f"Scheduler stopped manually")
