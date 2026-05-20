import queue
import threading
import time
from collections import defaultdict
from typing import Any

from OTApp.Configuration.DataClasses import OrderResult, PositionData, FilledOrderResult, ConditionalOrderDetails
from OTApp.Configuration.Enums import OrderSide
from OTApp.Logger.Logger import AppLogger
from OTApp.Order.OrderManager import OrderManager
from OTApp.Persistence.History.TradeMunshi import TradeMunshi
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
        self.filled_order_queue = queue.Queue()
        self._yet_filled_: dict[str, dict[str, OrderResult]] = defaultdict(dict)
        self._filled: dict[str, dict[str, OrderResult]] = defaultdict(dict)
        self._positions: dict[str, dict[str, PositionData]] = defaultdict(dict)
        # Keeping aside of modified position from _positions
        self._positions_modified: dict[str, dict[str, PositionData]] = defaultdict(dict)
        self.stop_pending_order_watch_event = threading.Event()

        # The dedicated spirit: processing in the background
        self.order_monitoring_thread = threading.Thread(target=self._order_monitor_worker, daemon=True)
        self.order_monitoring_thread.start()

        # The dedicated spirit to chase order price to make order fill
        self.order_price_chase_thread = threading.Thread(target=self._vigilant_pending_orders, daemon=True)
        self.order_price_chase_thread.start()
        self.WAIT_TIME = 60  # we will wait to fill order after that we have to make changes to make it fill
        self.subscriber_manager = SubscriptionManager(self._logger_)
        self.trade_munshi = TradeMunshi(self._logger_)
        self.fill_order_processing_done = threading.Event()
        self.fill_order_processing_done.set()

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
                self._logger_.error(f"🚨 Order Monitor Worker Thread Error: {str(e)}", exc_info=True)
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
        elif action is None and order_data.get('type') == 'v2/user_trades':
            try:
                # Locking processing of position
                self.fill_order_processing_done.clear()
                self._logger_.info(f"Order with id = {order_data.get('o')} has been filled ")
                self.handle_order_fill_data(order_data)
            except Exception as e:
                self._logger_.error(
                    f"Error happened while processing of v2/user_trades with Id:  {order_data.get('o')}")
            finally:
                # Unlocking to start processioning of position handling.
                self._logger_.info(f"Releasing lock for position processing ...")
                self.fill_order_processing_done.set()
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
                    self._yet_filled_[strategy_name][order_data_result.get('product_id')] = order_data_class
            elif order_state == "pending":
                bracket_order: bool = order_data_result.get('bracket_order')
                if bracket_order:
                    # know parent
                    bracket_meta = order_data_result.get('meta_data')
                    parent_type = bracket_meta.get('parent_type')
                    if parent_type == 'position':
                        # search existing position or order in the system.
                        if order_data_result.get('stop_order_type') == 'take_profit_order':
                            self.adjust_position_bracket(order_data_result, tp=True)
                        if order_data_result.get('stop_order_type') == 'stop_loss_order':
                            self.adjust_position_bracket(order_data_result, sl=True)
                        # search_position = self.search_parent(child_order=order_data_result)
                    elif parent_type == 'order':
                        # TODO : need to check how to associate with existing order
                        self._logger_.warning(
                            f"***Unhandled Bracket Order : {order_data_result} "
                            f"\n\t\t\t\t\t"
                            f" Of  Parent Type : {parent_type}")
                    else:
                        # handling SL and Target for option contracts
                        order_source = bracket_meta.get('order_source')
                        if order_source == 'positions_TP_SL_order':
                            if order_data_result.get('stop_order_type') == 'take_profit_order':
                                self.adjust_position_bracket(order_data_result, tp=True)
                            elif order_data_result.get('stop_order_type') == 'stop_loss_order':
                                self.adjust_position_bracket(order_data_result, sl=True)
                            else:
                                self._logger_.warning(
                                    f"***Unhandled Bracket Order : {order_data_result} "
                                    f"\n\t\t\t\t\t"
                                    f" Of  Parent Type : {parent_type}")
                        else:
                            self._logger_.warning(
                                f"***Unhandled Bracket Order : {order_data_result} "
                                f"\n\t\t\t\t\t"
                                f" Of  Parent Type : {parent_type}")
            else:
                self._logger_.warning(
                    f"***Unhandled Order State: {order_state} \n\t\t\t\t\t Order data : {order_data_result}")

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
            elif order_state in {'create', 'update', 'open', 'pending'}:
                with self._active_order_lock_:
                    if order_state not in {'pending'}:
                        self._yet_filled_[strategy_name][order_data.get('product_id')] = order_data_class
                        OrderManager(self._logger_).adjust_brackets(order_data, order_data_class)
                    elif order_state == 'pending':
                        # TODO for >
                        # Clean the Order / Position map and update in persistence layers
                        bracket_order: bool = order_data.get('bracket_order')
                        if bracket_order:
                            # know parent
                            bracket_meta = order_data.get('meta_data')
                            parent_type = bracket_meta.get('parent_type')
                            if parent_type == 'position':
                                if order_data.get('stop_order_type') == 'take_profit_order':
                                    self.adjust_position_bracket(order_data, tp=True)
                                if order_data.get('stop_order_type') == 'stop_loss_order':
                                    self.adjust_position_bracket(order_data, sl=True)
                            elif parent_type == 'order':
                                # TODO : need to check how to associate with existing order
                                self._logger_.warning(
                                    f"***Unhandled Bracket Order : {order_data} "
                                    f"\n\t\t\t\t\t"
                                    f" Of  Parent Type : {parent_type}")
                            else:
                                self._logger_.warning(
                                    f"***Unhandled Bracket Order : {order_data} "
                                    f"\n\t\t\t\t\t"
                                    f" Of  Parent Type : {parent_type}")
            else:
                self._logger_.critical(f"Getting unhandled order :  {order_data}")
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
        order_data_cls.limit_price = order_result.get('limit_price')
        order_data_cls.order_type = order_result.get('order_type')
        order_data_cls.state = order_result.get('state')
        order_data_cls.unfilled_size = order_result.get('unfilled_size')
        # adding blank SL and TP for future use of bracket order
        order_data_cls.stop_loss = ConditionalOrderDetails()
        order_data_cls.take_profit = ConditionalOrderDetails()
        sl = order_data_cls.stop_loss
        sl.trigger_price = order_result.get('bracket_stop_loss_price')
        sl.limit_price = order_result.get('bracket_stop_loss_limit_price')
        tp = order_data_cls.take_profit
        tp.trigger_price = order_result.get('bracket_take_profit_price')
        tp.limit_price = order_result.get('bracket_take_profit_limit_price')

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
        # This blocks the thread until set() is called
        self.fill_order_processing_done.wait()
        action = position_data.get('action')
        self._logger_.info(f"Bahadur das received {action} position : {position_data}")
        if action == 'snapshot' and 'result' in position_data and position_data['result']:
            self.handle_snapshot_position_data(position_data)
        elif action == 'delete':
            self.handle_delete_position(position_data)
        elif action in {'create', 'update'}:
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
                    strategy_name = order_data.strategy_name if order_data.strategy_name else f"{order_data.symbol}_strategy"
                    # Access the dictionary for the specific strategy, then call .update()
                    self._positions[strategy_name].update({
                        position_data.symbol: position_data
                    })
                    position_data.strategy_name = strategy_name
                    # add position order map to trade munshi position_order_queue for persist
                    self.trade_munshi.save_position_snapshot(self._positions)
                    # delete order from self._yet_filled_ dictionary but unsubscribe as we need feed for position tracking
                    self.handle_delete_order(order_data=order_data.data, unsubscribe=True)
            else:
                # TODO refactor code , create one method so that can be re-use
                # Order does not present in memory check in database
                db_position_datas = self.trade_munshi.search_position_history(
                    position_id=position_data.position_id)
                if db_position_datas and len(db_position_datas) > 0:
                    # re-setting memory
                    db_position_data = db_position_datas[0]
                    strategy_name = db_position_data.strategy_name
                    # syncing the older data with current one
                    db_position_data.data = position_data.data

                    self._positions[strategy_name].update({
                        position_data.symbol: db_position_data
                    })
                else:
                    # **** Critical Case : Persisting of position did not happen in past ****
                    # Is position presents in memory?
                    strategy_name = position_data.strategy_name if position_data.strategy_name else f"{position_data.symbol}_strategy"
                    # Access the dictionary for the specific strategy, then call .update()
                    self._positions[strategy_name].update({
                        position_data.symbol: position_data
                    })
                    # add position order map to trade munshi position_order_queue for persist
                    self.trade_munshi.save_position_snapshot(self._positions)
                    self._logger_.info(
                        f" Neither! order nor db Position found for : "
                        f" \n\t\t\t\t\t\t\t "
                        f"{position_data}"
                        f" \n\t\t\t\t\t\t\t "
                        f"*** Persisting Position in System ***!")
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
        position_data_cls.entry_price = position_data_result.get('entry_price')
        position_data_cls.data = position_data_result
        return position_data_cls

    def find_out_order_data_for_position(self, position_data):
        order_data_cls: OrderResult = None
        with self._active_order_lock_:
            # TODO : why we are searching in _yet_filled list it should be _filled list
            for strategy in self._yet_filled_.keys():
                for order_data in self._yet_filled_[strategy].values():
                    symbol_validation = order_data.symbol == position_data.symbol
                    size_validation = order_data.size
                    product_id_validation = order_data.product_id == position_data.product_id
                    side_validation = order_data.side == position_data.side
                    if symbol_validation and size_validation and product_id_validation and side_validation:
                        order_data_cls = order_data
                        position_data.strategy_name = order_data.strategy_name
                        position_data.orders.append(order_data_cls)
                        position_data.stop_loss = order_data.stop_loss
                        position_data.take_profit = order_data.take_profit
                        break
        return order_data_cls

    def handle_position_data(self, position_data):
        self.handle_position(position_data)

    def handle_delete_position(self, row_position_data):
        position_data: PositionData = self.prepare_position_data_class(row_position_data)
        order_data: OrderResult = self.find_out_order_data_for_position(position_data)
        symbol = position_data.symbol
        with self._order_position_lock_:
            # Unsubscribe feed symbols
            self.subscriber_manager.unsubscribe_feeds(symbols=[symbol], channel='l2_orderbook', public=True)
            # Clean the Order / Position map
            if order_data.strategy_name in self._positions:
                self._positions[order_data.strategy_name].pop(position_data.symbol, None)

    def handle_order_fill_data(self, filled_order_data):
        filled_order: FilledOrderResult = self.prepare_filled_order_data_class(filled_order_data)
        # search order in _yet_filled_ and update existing order
        order_data_cls: OrderResult = self.deal_order_with_fill_order(filled_order)

    def deal_order_with_fill_order(self, filled_order: FilledOrderResult) -> OrderResult:
        order_data_cls: OrderResult = None
        handle_delete_order = False
        with (self._active_order_lock_):
            for strategy in self._yet_filled_.keys():
                for order_data in self._yet_filled_[strategy].values():
                    order_validation = order_data.order_id == filled_order.order_id
                    size_validation = order_data.size == int(filled_order.fill_size)
                    if order_validation:
                        self._logger_.info(
                            f"Appending filled order with id {filled_order.fill_id} \n\t\t\t\t\t\t\t "
                            f" of Order  {filled_order.order_id} to existing order {order_data.order_id}")
                        order_data.filled_orders.append(filled_order)
                        order_data.unfilled_size = order_data.unfilled_size - int(filled_order.fill_size)
                        order_data_cls = order_data
                        if size_validation or order_data.unfilled_size == 0:
                            # move order to  self._filled
                            assert order_data.symbol is not None, "Symbol must be set for filled orders"
                            self._filled[order_data.strategy_name][order_data.symbol] = order_data_cls
                            handle_delete_order = True
                        break

        if handle_delete_order:
            # delete order from outside of same lock (self._active_order_lock_) from self._yet_filled_ dictionary but unsubscribe as we need feed for position tracking
            self.handle_delete_order(order_data=order_data.data, unsubscribe=True)
        return order_data_cls

    def prepare_filled_order_data_class(self, filled_order_data):
        filled_order: FilledOrderResult = FilledOrderResult()
        filled_order.order_id = filled_order_data.get('o')
        filled_order.symbol = filled_order_data.get('sy')
        filled_order.strategy_name = filled_order_data.get('c')
        filled_order.fill_size = filled_order_data.get('s')
        filled_order.product_id = filled_order_data.get('i')
        filled_order.side = OrderSide.SELL if filled_order_data.get('S') == 'sell' else OrderSide.BUY
        filled_order.fill_id = filled_order_data.get('f')
        filled_order.reason = filled_order_data.get('R')
        filled_order.fill_price = filled_order_data.get('p')
        filled_order.data = filled_order_data
        return filled_order

    def adjust_position_bracket(self, order_data, tp: bool = False, sl: bool = False):
        parent_id = order_data.get('meta_data').get('parent_id')
        symbol = order_data.get('product_symbol')
        strategy_name = order_data.get('client_order_id') if order_data.get(
            'client_order_id') else f"{symbol}_strategy"
        searched_position: PositionData | None = self.find_position(symbol=symbol, strategy_name=strategy_name,
                                                                    parent_id=parent_id)
        if tp:
            take_profit: ConditionalOrderDetails | None = searched_position.take_profit
            if not take_profit:
                take_profit = ConditionalOrderDetails()
            take_profit.conditional_order_id = order_data.get('id')
            take_profit.trigger_price = order_data.get('stop_price')
            take_profit.limit_price = order_data.get('limit_price')
            take_profit.data = order_data
        elif sl:
            stop_loss: ConditionalOrderDetails | None = searched_position.stop_loss
            if not stop_loss:
                stop_loss = ConditionalOrderDetails()
            stop_loss.conditional_order_id = order_data.get('id')
            stop_loss.trigger_price = order_data.get('stop_price')
            stop_loss.limit_price = order_data.get('limit_price')
            stop_loss.data = order_data

    def find_position(self, symbol, strategy_name=None, parent_id=None):
        """
        Finds a position based on symbol and optionally strategy_name or parent_id.
        """
        # Scenario 1: strategy_name is provided (Efficient lookup)
        if strategy_name and strategy_name in self._positions:
            strategy_positions = self._positions[strategy_name]
            if symbol in strategy_positions:
                pos: PositionData = strategy_positions[symbol]
                # If parent_id is also provided, verify it matches
                if parent_id:
                    # Assuming PositionData has a parent_id attribute or key
                    # able to matched
                    if self.same_position(position_id=pos.position_id, parent_id=parent_id):
                        return pos
                else:
                    return pos
            return None
        # Scenario 2: strategy_name is NOT provided (Iterate through all strategies)
        for strat_name, symbols_dict in self._positions.items():
            if symbol in symbols_dict:
                pos = symbols_dict[symbol]
                # If parent_id is provided, check for a specific match
                # able to matched
                if parent_id:
                    if self.same_position(position_id=pos.position_id, parent_id=parent_id):
                        return pos
                else:
                    # If no parent_id provided, return the first match for this symbol
                    return pos
        return None

    def same_position(self, parent_id: str, position_id: str | None) -> bool:
        """
        Validates if a parent_id and position_id refer to the same entity.

        Args:
            parent_id: e.g., '73986761_BTCUSD'
            position_id: e.g., '27_73986761'
            symbol: The symbol string (e.g., 'BTCUSD')
            product_id: The numeric ID for the product (e.g., 27)
        """
        try:
            # 1. Extract Order ID from parent_id (Format: {order_id}_{symbol})
            # We split by underscore and take the first part
            order_id_from_parent = parent_id.split('_')[0]

            # 2. Extract Order ID from position_id (Format: {product_id}_{order_id})
            # We split by underscore and take the second part
            order_id_from_pos = position_id.split('_')[1]

            # 3. Compare the extracted Order IDs
            return order_id_from_parent == order_id_from_pos
        except Exception:
            return False

    # Extra method may be removed after while

    def search_parent(self, child_order):
        searched_position: PositionData | None = None
        meta = child_order.get('meta_data')
        parent_id = meta.get('parent_id')
        parent_type = meta.get('parent_type')
        symbol = child_order.get('product_symbol')
        strategy_name = child_order.get('client_order_id') if child_order.get(
            'client_order_id') else f"{symbol}_strategy"
        if parent_type:
            searched_position = self.find_position(symbol=symbol, strategy_name=strategy_name,
                                                   parent_id=parent_id)
        return searched_position
