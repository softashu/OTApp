import json
import queue
import threading

from OTApp.Logger.Logger import AppLogger

"""
Name : BahaduarDass for this order monitoring class is due to giving the tribute to our past employee who 
        did his task very dedicatly and he is obedient and employed from my Grand father, next family main man my uncle Dr. Ramdev Pd Singh
        my father and me also. So its a just tribute to him for his dedicated contribution and not like to forget his 
        excelent service to our three-to-four generation.
        
        
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

        # The memory of the system: holding the fill data
        self.order_fill_queue = queue.Queue()

        # The dedicated spirit: processing in the background
        self.order_fill_monitoring_thread = threading.Thread(target=self._order_monitor_worker, daemon=True)
        self.order_fill_monitoring_thread.start()

    def on_websocket_message(self, message):
        """
        Producer: Senses the fill and pushes to memory.
        """
        data = json.loads(message)
        if data.get('type') == 'user_orders':
            order_content = data['content']
            if order_content.get('state') == 'filled':
                # Push to memory queue immediately
                self.order_fill_queue.put(order_content)

    def report_fill(self, fill_data):
        """ The sense: instantly catching the market event """
        self.order_fill_queue.put(fill_data)

    def _order_monitor_worker(self):
        """
        Consumer: Dedicated thread to handle fill logic and retries.
        """
        while True:
            # Step 2: Retrieve fill from memory
            fill_data = self.order_fill_queue.get()
            try:
                symbol = fill_data.get('symbol')
                fill_price = float(fill_data.get('avg_fill_price', 0))
                qty = fill_data.get('size')

                self._logger_.info(f"🎯 FILL DETECTED | {symbol} | Price: {fill_price} | Qty: {qty}")

                # TRIGGER: Now place your Stop Loss order safely
                # Since this is a separate thread, it won't slow down the WebSocket
                # self.place_protective_stop_loss(fill_data)

                # Step 3: Persistence - Save the fill snapshot
                # self.save_trade_snapshot(fill_data)

            except Exception as e:
                self._logger_.error(f"🚨 Monitor Thread Error: {str(e)}")
                # Optional: Re-queue the fill if processing failed
                self.order_fill_queue.put(fill_data)
            finally:
                self.fill_queue.task_done()  # Clean up memory reference

    def _vigilant_watch(self):
        """ The service: processing with the dedication of BahaduarDass """
        while True:
            fill = self.vigilance_queue.get()
            try:
                # Logic for monitoring fill, calculating slippage, and verifying SL
                self._logger_.info(f"🔱 BahaduarDass is processing fill: {fill.get('symbol')}")
            finally:
                self.vigilance_queue.task_done()
