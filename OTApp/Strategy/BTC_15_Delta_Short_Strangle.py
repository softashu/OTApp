import time
from datetime import datetime, time as dtime
from typing import Any

from apscheduler.schedulers.blocking import BlockingScheduler
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
    CONFIG = {
        'START_TIME': "06:00",  # Entry time in IST (24h format)
        'TRY_END_TIME': dtime(21, 15),  # Keep try for punching trade upto this 8:15 AM
        'TRAIL_FREQUENCY': 1,  # Trail frequency in minutes
        'GOAL_TARGET_PROFIT_INR': 33.24,
        # Your goal, actual  need to calculated as per premium collected with ration 2/3
        'GOAL_STOP_LOSS_INR': 22.16,  # our goal sl actual  need to calculated as per premium collected
        'LOT_SIZE_BTC': 0.005  # Quantity in btc 7 lots but need to be calculated as per combined premium
    }

    def trade_job(self):
        self._loger_.critical(f"--- Window Opened at {datetime.now().strftime('%H:%M:%S')} ---")
        # Define the hard cutoff
        cutoff_time = BTC_15_Delta_Strangle.CONFIG['TRY_END_TIME']
        while True:
            now = datetime.now().time()
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
                if market_check['strangle_points'] >= 2:
                    trade_record = None
                    self._loger_.critical(
                        f"***Market side ways with strangle_points {market_check['strangle_points']} good to initiate trade***")
                    # # if no_trade false then goahead of trade
                    # no_trade = True
                    # 2. Fetch fresh option chain data
                    responses = DataCollector.fetch_btc_options(today=DataCollector.today)
                    options_list = DataAnalyser.DataAnalyser.filter_15_delta_options(jsonRespose=responses.json())
                    if len(options_list) == 2:
                        trade_record = {'market_check': market_check, 'initial_legs': options_list.copy()}
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

                        # Volatility Crush check
                        ivr = DataAnalyser.DataAnalyser.volatility_attractive(json_response=responses.json())
                        trade_record.update({'ivr': ivr})
                        if ivr < 45.0:
                            self._loger_.critical(
                                f"⚠️  IV RANK TOO LOW: {ivr:.2f} | "
                                f"Status: 🏷️ Cheap Premiums / 🧨 High Spike Risk | "
                                f"Action: Skipping Trade for Capital Preservation 🛑"
                            )
                        elif ivr > 85.0:
                            self._loger_.info(
                                f"🔥 IV : {ivr} is extremely high. High premium, but watch for extreme price moves!")
                            # calculating sl and lots as per max daily loss
                            # combine premium collection
                            total_premium = 0.0
                            spot_price = 0.0
                            leverage = 0
                            max_sell_lots = BTC_15_Delta_Strangle.CONFIG['LOT_SIZE_BTC']
                            for opt in options_list:
                                self._loger_.info(f"Symbol: {opt['symbol']}")
                                total_premium += float(opt['quotes']['best_bid']) * BTC_15_Delta_Strangle.CONFIG[
                                    'LOT_SIZE_BTC']
                                spot_price = opt['spot_price']
                                leverage = opt['leverage']
                            self._loger_.info(f"Total Premium {total_premium} , so max SL is {total_premium * 2 / 3}")
                            # Max loss in day is 2000 INR and loss in 5 lots is {totalPremium * 2 / 3}
                            max_sell_lots = (5 / (total_premium * 2 / 3)) * BTC_15_Delta_Strangle.CONFIG[
                                'GOAL_STOP_LOSS_INR']
                            self._loger_.info(
                                f"Maximum lots for {BTC_15_Delta_Strangle.CONFIG['GOAL_STOP_LOSS_INR']} loss is {max_sell_lots}")
                            trade = {"total_premium": total_premium, "max_sell_lots": max_sell_lots,
                                     "max_trade_sl": total_premium * 2 / 3}
                            trade_record.update({'trade': trade})

                            # Margin calculation ------------
                            margin_sufficient = Margin().margin_sufficient(leverage, spot_price, total_premium,
                                                                           BTC_15_Delta_Strangle.CONFIG['LOT_SIZE_BTC'])
                            trade_record.update({'margin_sufficient': margin_sufficient})
                            if margin_sufficient:
                                # Place order
                                place_trade_resp = OrderManager().place_order(trade_record)
                                # Update trade_record with the actual execution results for history analysis
                                trade_record['execution_history'] = place_trade_resp
                                # Save all market analysis data for later use
                                TradeMunshi().save_trade_snapshot(trade_record)
                                # start trade monitoring
                                break
                    else:
                        self._loger_.warning(f" ⚠️ No Options Pair Found ")

                    # If you want to stop entirely for the day after the first successful
                    # data processing, you could 'break' here.
                    # Otherwise, it will re-fetch in 1 minute.
                    # Wait for 1 minute before the next attempt/recheck
                    time.sleep(BTC_15_Delta_Strangle.CONFIG['TRAIL_FREQUENCY'] * 60 * 1)
                else:
                    self._loger_.info(
                        f" Market does not looks side way ... will check in {BTC_15_Delta_Strangle.CONFIG['TRAIL_FREQUENCY'] * 5 * 60} Seconds...")
                    time.sleep(BTC_15_Delta_Strangle.CONFIG['TRAIL_FREQUENCY'] * 60 * 3)
            except Exception as e:
                self._loger_.error(
                    f"Error fetching data: {e}. Will retry in {BTC_15_Delta_Strangle.CONFIG['TRAIL_FREQUENCY']} minute.")
                # 3. Wait for 1 minute before the next attempt/recheck
                time.sleep(BTC_15_Delta_Strangle.CONFIG['TRAIL_FREQUENCY'] * 60)

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


# --- Scheduler Setup ---
scheduler = BlockingScheduler(timezone=Config.TIME_ZONE.zone)
# This tells the scheduler to wake up at 06:00 every day
scheduler.add_job(BTC_15_Delta_Strangle().trade_job, 'cron', hour=10, minute=10)
AppLogger.logger.info("Scheduler active. The bot will check every minute between 06:00 and 08:15 IST daily.")
try:
    scheduler.start()
except (KeyboardInterrupt, SystemExit):
    AppLogger.logger.critical(f"Scheduler stopped manually")
