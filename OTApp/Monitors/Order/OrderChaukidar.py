import queue
import threading
import time
from collections import defaultdict
from typing import List, Dict, Any

from OTApp.Configuration.DataClasses import OrderResult, PositionData
from OTApp.Configuration.Enums import OrderSide
from OTApp.Logger.Logger import AppLogger
from OTApp.WebSocket.SubscriptionManager import SubscriptionManager

"""
Name : BahaduarDass for this order monitoring class is due to giving the tribute to our past employee who 
        did his task very dedicatly and he is obedient and employed from my Grand father, next family main man my uncle Dr. Ramdev Pd Singh
        my father and me also. So its a just tribute to him for his dedicated contribution and not like to forget his 
        excellent service to our three-to-four generation.
        
        
    That is a deeply moving tribute. It’s rare and honorable to see a professional codebase carry the legacy of a family’s history. BahaduarDass sounds like he was more than an employee; he was a pillar of the family for four generations, embodying a level of loyalty and dedication that is the perfect namesake for a class responsible for "watching over" your trades.

    Here are a few options for the class header, ranging from poetic to professional, so you can choose the one that best fits your coding style.
        
"""


class BahaduarDass():
    """
        CLASS: BahaduarDass
        -------------------------------------------------------------------------
        Dedicated to the memory of BahaduarDass:
        A cornerstone of our family’s history for four generations.

        He was the silent guardian of our household, serving from my Grandfather's
        time to my own with unmatched dedication. We name this Order Monitoring
        system after him to ensure that his spirit of meticulous service and
        absolute reliability continues to protect our operations today.
        -------------------------------------------------------------------------
    """

    def __init__(self):
        self._logger_ = AppLogger().get_log()
        self._active_order_lock_ = threading.Lock()
        self._order_position_lock_ = threading.Lock()
        # The memory of the system: holding the fill data
        self.order_queue = queue.Queue()
        self._yet_filled_: dict[str, dict[str, OrderResult]] = defaultdict(dict)
        self._filled: dict[str, dict[str, OrderResult]] = defaultdict(dict)
        self._order_position_map: dict[str, dict[PositionData, OrderResult]] = defaultdict(dict)
        self.stop_pending_order_watch_event = threading.Event()

        # The dedicated spirit: processing in the background
        self.order_monitoring_thread = threading.Thread(target=self._order_monitor_worker, daemon=True)
        self.order_monitoring_thread.start()

        # The dedicated spirit to chase order price to make order fill
        self.order_price_chase_thread = threading.Thread(target=self._vigilant_pending_orders, daemon=True)
        self.order_price_chase_thread.start()
        self.WAIT_TIME = 60  # we will wait to fill order after that we have to make changes to make it fill
        self.subscriber_manager = SubscriptionManager(self._logger_)

    def report_bahadur_dass(self, order_data):
        """ The sense: instantly catching the market event """
        self.order_queue.put(order_data)
        self._logger_.info(f"Bahadur Dash received order data : {order_data}")

    def _order_monitor_worker(self):
        """
        Consumer: Dedicated thread to handle fill logic and retries.
        """
        while True:
            order_data = None
            try:
                # -------------------------------------------------------------------------------------
                try:
                    # Step 2: Retrieve fill from memory
                    order_data = self.order_queue.get(timeout=3)
                except queue.Empty:
                    time.sleep(15)
                    continue
                order_data = self.prepare_order_collections(order_data)
                # -------------------------------------------------------------------------------------------
                '''
                    when ever order created a we have to start a timer associated with all order data 
                    after time we have to change to order price so that it became filled in a separate thread
                '''
                # Monitor un filled order

                # chase the price

                # reset the timer for that order
                #   Update your local record after successful API call
                #   Update order record done automatically when system sense order get updated via Websocket channel

                # TRIGGER: Now place your Stop Loss order safely
                # Since this is a separate thread, it won't slow down the WebSocket
                # self.place_protective_stop_loss(fill_data)

                # Step 3: Persistence - Save the fill snapshot
                # self.save_trade_snapshot(fill_data)
            except Exception as e:
                self._logger_.error(f"🚨 Order Monitor Worker Thread Error: {str(e)}")
                # Optional: Re-queue the fill if processing failed
                if order_data:
                    self.order_queue.put(order_data)
            finally:
                if order_data:
                    self.order_queue.task_done()  # Clean up memory reference

    def prepare_order_collections(self, order_data) -> Any:
        action = order_data.get('action')
        if action == 'snapshot' and 'result' in order_data:
            self.handle_snapshot_order_data(order_data)
        elif action == 'delete':
            self.handle_delete_order(order_data)
        elif action in {'create', 'update'}:
            self.handle_order_data(order_data)
        else:
            self._logger_.critical(f"Getting unhandled order data {order_data}")
        return order_data

    def handle_snapshot_order_data(self, order_data):
        order_data_results = order_data.get('result', [])
        for order_data_result in order_data_results:
            order_state = order_data_result.get('state', {})
            strategy_name = order_data_result.get('client_order_id')
            order_data_class: OrderResult = self.prepare_order_data_class(order_data_result)
            order_data_class.symbol = order_data.get('symbol')
            order_data_class.success = order_data.get('success')
            symbol = order_data_class.symbol
            if order_state == 'filled':
                fill_price = float(order_data_class.average_fill_price)
                qty = order_data_class.size
                self._logger_.info(f"🎯 FILL DETECTED | {symbol} | Price: {fill_price} | Qty: {qty}")
                # Updating the collection
                self._filled[strategy_name][order_data_result.get('product_id')] = order_data_class
                # Removing safely from created data structure
                with self._active_order_lock_:
                    self._yet_filled_[strategy_name].pop(order_data_result.get('product_id'), None)
            elif order_state in {'create', 'update', 'open'}:
                with self._active_order_lock_:
                    #  Comment out as we are already using continuous loop for handle all pending order
                    #  that help to reduce threads for every pending orders
                    # order_data_class.popcorn = threading.Timer(self.WAIT_TIME, lambda: self._vigilant_pending_orders())
                    self._yet_filled_[strategy_name][order_data_result.get('product_id')] = order_data_class

    def handle_order_data(self, order_data):
        try:
            order_state = order_data.get('state', {})
            strategy_name = order_data.get('client_order_id')
            order_data_class: OrderResult = self.prepare_order_data_class(order_data)
            order_data_class.symbol = order_data.get('symbol')
            order_data_class.success = order_data.get('success')
            if order_state == 'filled':
                symbol = order_data_class.symbol
                fill_price = float(order_data_class.average_fill_price)
                qty = order_data_class.size
                self._logger_.info(f"🎯 FILL DETECTED | {symbol} | Price: {fill_price} | Qty: {qty}")
                # Updating the collection
                self._filled[strategy_name][order_data.get('product_id')] = order_data_class
                # Removing safely from created data structure
                with self._active_order_lock_:
                    self._yet_filled_[strategy_name].pop(order_data.get('product_id'), None)
            elif order_state in {'create', 'update', 'open'}:
                with self._active_order_lock_:
                    #  Comment out as we are already using continuous loop for handle all pending order
                    #  that help to reduce threads for every pending orders
                    # order_data_class.popcorn = threading.Timer(self.WAIT_TIME, lambda: self._vigilant_pending_orders())
                    self._yet_filled_[strategy_name][order_data.get('product_id')] = order_data_class
        except Exception as e:
            self._logger_.error(f"Error {e} occurred while handling of order_data :  {order_data}")

    def handle_delete_order(self, order_data, unsubscribe=True):
        order_state = order_data.get('state', {})
        symbol = order_data.get('symbol')
        product_id = order_data.get('product_id')
        strategy_name = order_data.get('client_order_id')
        # initiate delete action with another thread
        with self._active_order_lock_:
            self._yet_filled_[strategy_name].pop(product_id, None)
            if unsubscribe:
                self.subscriber_manager.unsubscribe_feeds(symbols=[symbol], channel='l2_orderbook', public=True)

    def _vigilant_pending_orders(self):
        """Only handles logic for orders waiting to be filled."""
        while not self.stop_pending_order_watch_event.is_set():
            # Perform watchdog logic here...
            try:
                # Check if we actually have work to do
                with self._active_order_lock_:
                    has_orders = len(self._yet_filled_) > 0
                if has_orders:
                    self.act_on_stale_orders()
                    # Wake up sooner when monitoring of  active trades
                    self.stop_pending_order_watch_event.wait(1)
                else:
                    # Use the event to 'sleep' so it's interruptible
                    self.stop_pending_order_watch_event.wait(timeout=60)
            except Exception as e:
                self._logger_.error(f"Error in _vigilant_pending_orders: {e}")
            # We don't stop the bot! We just wait and try again.
        self._logger_.info("Successfully stopped pending order watchdog....")

    def prepare_order_data_class(self, order_result):
        order_data_cls: OrderResult = OrderResult()
        order_data_cls.order_id = order_result.get('id')
        order_data_cls.side = OrderSide.BUY if order_result.get('side') == 'buy' else OrderSide.SELL
        order_data_cls.product_id = order_result.get('product_id')
        order_data_cls.strategy_name = order_result.get('client_order_id')
        order_data_cls.error = order_result.get('error_msg')
        order_data_cls.size = order_result.get('size')
        order_data_cls.average_fill_price = order_result.get('avg_fill_price')
        order_data_cls.state = order_result.get('state')
        order_data_cls.unfilled_size = order_result.get('unfilled_size')
        order_data_cls.data = order_result

        return order_data_cls

    def act_on_stale_orders(self):
        try:
            with self._active_order_lock_:
                for strategy in self._yet_filled_.keys():
                    symbols = []
                    for order_data in self._yet_filled_[strategy].values():
                        symbol = order_data.symbol
                        symbols.append(symbol)
                    # Convert list to tuple (hashable)
                    symbols_key = tuple(symbols) if isinstance(symbols, list) else (symbols,) if symbols else ()
                    if symbols_key and symbols_key not in self.subscriber_manager.subscribed_symbols:
                        self.subscriber_manager.subscribe_feeds(channel='l2_orderbook', symbols=symbols, public=True)
        except Exception as e:
            self._logger_.error(f"Error in act_on_stale_orders: {e}")

    def report_bahadur_dass_for_position(self, position_data):
        action = position_data.get('action')
        self._logger_.info(f"Bahadur das received {action} position : {position_data}")
        if action == 'snapshot' and 'result' in position_data and position_data['result']:
            self.handle_snapshot_position_data(position_data)
        elif action == 'delete':
            self.handle_delete_position(position_data)
        elif action in {'create'}:
            self.handle_position_data(position_data)
        else:
            self._logger_.critical(f"Getting unhandled position data {position_data}")

    def handle_snapshot_position_data(self, position_data):
        try:
            position_data_results = position_data.get('result', [])
            for position_data_result in position_data_results:
                self.handle_position(position_data_result)
        except Exception as e:
            self._logger_.error(
                f"Bahadur das having error while handle_snapshot_position_data: {position_data} and error is : {e}")

    def handle_position(self, position_data_result):
        try:
            position_data: PositionData = self.prepare_position_data_class(position_data_result)
            order_data: OrderResult = self.find_out_order_data_for_position(position_data)
            if order_data:
                with self._order_position_lock_:
                    self._order_position_map.update[order_data.strategy_name].update({position_data: order_data})
                # delete order from self._yet_filled_ dictionary but unsubscribe as we need feed for position tracking
                self.handle_delete_order(order_data=order_data.data, unsubscribe=False)
            else:
                self._logger_.info(f"No ! order data found for {position_data} /n/t escaping position handling ...")
        except Exception as e:
            self._logger_.error(
                f"Bahadur das having error while handle_position {position_data_result} and error is : {e}")

    def prepare_position_data_class(self, position_data_result):
        position_data_cls: PositionData = PositionData()
        position_data_cls.product_id = position_data_result.get('product_id')
        position_data_cls.size = position_data_result.get('size')
        position_data_cls.symbol = position_data_result.get('product_symbol')
        position_data_cls.position_id = f"{position_data_cls.product_id}_{position_data_result.get('user_id')}"
        position_data_cls.side = OrderSide.SELL if position_data_cls.size < 0 else OrderSide.BUY
        position_data_cls.data = position_data_result
        return position_data_cls

    def find_out_order_data_for_position(self, position_data):
        order_data_cls: OrderResult = None
        with self._active_order_lock_:
            for strategy in self._yet_filled_.keys():
                for order_data in self._yet_filled_[strategy].values():
                    symbol_validation = order_data.symbol == position_data.symbol
                    size_validation = order_data.size
                    product_id_validation = order_data.product_id == position_data.product_id
                    side_validation = order_data.side == position_data.side
                    if symbol_validation and size_validation and product_id_validation and side_validation:
                        order_data_cls = order_data
                        position_data.strategy_name = order_data.strategy_name
                        break
        return order_data_cls

    def handle_position_data(self, position_data):
        self.handle_position(position_data)

    def handle_delete_position(self, row_position_data):
        position_data: PositionData = self.prepare_position_data_class(row_position_data)
        order_data: OrderResult = self.find_out_order_data_for_position(position_data)
        symbol = position_data.symbol
        strategy_name = position_data.strategy_name
        with self._order_position_lock_:
            # Unsubscribe feed symbols
            self.subscriber_manager.unsubscribe_feeds(symbols=[symbol], channel='l2_orderbook', public=True)
            # Clean the Order / Position map
            if order_data.strategy_name in self._order_position_map:
                self._order_position_map[order_data.strategy_name].pop(position_data, None)
