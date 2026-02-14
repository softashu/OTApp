import time
from datetime import datetime, time as dtime

from apscheduler.schedulers.blocking import BlockingScheduler

from OTApp.Analyser import DataAnalyser
from OTApp.Analyser.Trend import Market
from OTApp.Configuration.AppConfig import Config
from OTApp.DataCollectors.DeltaExchangeDataCollector import DataCollector
from OTApp.Logger.Logger import AppLogger
from OTApp.Margin.Margin import Margin


class BTC_15_Delta_Strangle:
    _loger_ = AppLogger().get_log()
    __data_analyser__ = DataAnalyser
    CONFIG = {
        'START_TIME': "06:00",  # Entry time in IST (24h format)
        'TRY_END_TIME': dtime(12, 15),  # Keep try for punching trade upto this 8:15 AM
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
                if market_check['strangle_points'] >= 0:
                    self._loger_.critical(f"***Market side ways good to initiate trade***")
                    no_trade = True
                    # 2. Fetch fresh option chain data
                    responses = DataCollector.fetch_btc_options(today=DataCollector.today)
                    options_list = DataAnalyser.DataAnalyser.filter_15_delta_options(jsonRespose=responses.json())
                    if len(options_list) == 2:
                        # Process the data ## calculating sl and lots as per max daily loss ------------
                        # combine premium collection

                        # Need to check price matching condition before placing order
                        price_match_response = DataAnalyser.DataAnalyser.option_price_matched(options_list)
                        if not price_match_response['price_matched']:
                            # Is the lager leg protected by Order Block
                            ob_protection = DataAnalyser.DataAnalyser.protected_by_ob(leg=price_match_response[
                                'larger_leg'], ob=market_check['order_block'])
                            if not ob_protection['protected']:
                                liquidity_sweep_protection = DataAnalyser.DataAnalyser.protected_by_liquidity_sweep(
                                    leg=price_match_response[
                                        'larger_leg'], liq_sweep=market_check['swings'])
                                # Handle larger leg either by lowering down the delta or get the same priced leg
                                managed_leg = DataAnalyser.DataAnalyser.filter_options(json_response=responses.json(),
                                                                                       leg=price_match_response[
                                                                                           'larger_leg'], delta=10)

                        """
                        Suppose if price does not match 
                        1. get the lower delta of that leg ---------recommendation for initial stage before going to
                         lower delta check the trends in 12 h time frame
                         1.1 Case study if trend is bearish on 12 h time frame lower down the PE leg to match the price similarly for CE side
                         1.2 case just matched price in lower delta PE or CE accordingly which is higher
                        
                        2. second back test scenario keep stick with leg and trade with lower delta of opposite side 
                        that have matched price -------when program became stable then try 
                        
                        """

                        # is_price_matching(options_list)
                        totalPremium = 0.0
                        spot_price = 0.0
                        leverage = 0
                        max_sell_lots = BTC_15_Delta_Strangle.CONFIG['LOT_SIZE_BTC']
                        for opt in options_list:
                            self._loger_.info(f"Symbol: {opt['symbol']}")
                            totalPremium += float(opt['quotes']['best_bid']) * BTC_15_Delta_Strangle.CONFIG[
                                'LOT_SIZE_BTC']
                            spot_price = opt['spot_price']
                            leverage = opt['leverage']
                        self._loger_.info(f"Total Premium {totalPremium} , so max SL is {totalPremium * 2 / 3}")
                        # Max loss in day is 2000 INR and loss in 5 lots is {totalPremium * 2 / 3}
                        max_sell_lots = (5 / (totalPremium * 2 / 3)) * BTC_15_Delta_Strangle.CONFIG[
                            'GOAL_STOP_LOSS_INR']
                        self._loger_.info(
                            f"Maximum lots for {BTC_15_Delta_Strangle.CONFIG['GOAL_STOP_LOSS_INR']} loss is {max_sell_lots}")

                        # Volatility Crush check
                        ivr = DataAnalyser.DataAnalyser.volatility_attractive(json_response=responses.json())
                        if ivr < 45.0:
                            self._loger_.warning(f"⚠️ IV : {ivr} is too low. Premiums are cheap; risk of IV spike is "
                                                 f"high. Skipping.")
                        if ivr > 85.0:
                            self._loger_.info(
                                f"🔥 IV : {ivr} is extremely high. High premium, but watch for extreme price moves!")
                            no_trade = False

                        # Margin calculation ------------
                        margin_sufficient = Margin().margin_sufficient(leverage, spot_price, totalPremium,
                                                                       BTC_15_Delta_Strangle.CONFIG['LOT_SIZE_BTC'])
                        # # Volatility Crush check
                        # ivr = DataAnalyser.DataAnalyser.volatility_attractive(jsonRespose=responses.json())
                        if margin_sufficient and not no_trade:
                            # Save all market analysis data for later use
                            # Place order
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


# --- Scheduler Setup ---
scheduler = BlockingScheduler(timezone=Config.TIME_ZONE.zone)
# This tells the scheduler to wake up at 06:00 every day
scheduler.add_job(BTC_15_Delta_Strangle().trade_job, 'cron', hour=10, minute=51)
AppLogger.logger.info("Scheduler active. The bot will check every minute between 06:00 and 08:15 IST daily.")
try:
    scheduler.start()
except (KeyboardInterrupt, SystemExit):
    AppLogger.logger.critical(f"Scheduler stopped manually")
