import json
import os
import queue
import threading
from datetime import datetime
import time

from queue import Empty

from OTApp.Logger.Logger import AppLogger

"""
🔱 The "Ghost-Writer" Architecture
        Main Thread (Producer): Simply "tosses" the trade record into a memory queue and immediately moves on to the next trade.
        
        Background Thread (Consumer): Sits in the background, waits for items in the queue, and handles the saving and retrying.
        
        Memory Management: Data exists in the queue only until it is successfully written to the disk.
        
        
        🔱 Why this is the "Ultimate Hack" for your Bot
                Zero Latency: Your execute_trade method no longer waits for the hard drive. It "shoots" the data to the queue and continues scanning the market.
                
                Retry Shield: If your hard drive is busy or a file is locked, the background thread will wait and try again without crashing your main trading logic.
                
                Automatic Memory Cleanup: Once self.trade_queue.get() finishes a loop, the local trade_data variable is overwritten or garbage collected, keeping your RAM lean.
                
"""


class TradeMunshi():
    def __init__(self, logger=None):
        self._logger_ = logger if logger else AppLogger().get_log()
        # 1. Initialize the Thread-Safe Memory Queue
        self.trade_queue = queue.Queue()
        self.position_order_queue = queue.Queue()
        # 2. Start the Background Dedicated Thread
        self.munshi_ji_thread = threading.Thread(target=self._minshi_worker, daemon=True)
        self.munshi_ji_thread.start()

    def save_trade_snapshot_thread_support(self, trade_record):
        """
        Main Task: Just puts data in memory and returns instantly.
        """
        self.trade_queue.put(trade_record)
        # Main program is now free!

    def save_position_snapshot(self, position_order_map_record):
        """
        Main Task: Just puts data in memory and returns instantly.
        """
        self.position_order_queue.put(position_order_map_record)
        # Main program is now free!

    def _minshi_worker(self):
        """
        Background Task: Dedicated to saving data with retry logic.
        """
        while True:
            try:
                self.process_market_analysis()
            except Exception as e:
                self._logger_.error(f"Error while persisting Market Analysis: {str(e)}")
            try:
                self.process_position_order()
            except Exception as e:
                self._logger_.error(f"Error while persisting Position Order: {str(e)}")

    def process_market_analysis(self):
        # Step 2: Retrieve from memory (blocks until data is available)
        trade_data = None
        try:
            trade_data = self.trade_queue.get(block=False)
        except Empty as e:
            # data not available to persist so skipping the rest code
            return
        success = False
        retries = 0
        while not success and retries < 5:
            try:
                self.save_trade_snapshot(trade_data)
                success = True
                # Step 3: Success! Data is now cleared from the 'trade_data' variable
                # and the queue automatically as we move to the next item.
            except Exception as e:
                retries += 1
                time.sleep(2)  # Wait before retry
        # Mark the task as done in the queue
        self.trade_queue.task_done()

    def save_trade_snapshot(self, trade_record):
        try:
            # Create a unique filename using timestamp and symbol
            # 1. Prepare unique metadata
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # filename = f"OTApp/Persistence/History/trade/trade_{timestamp}_{trade_record['trade_symbol']}.json"

            # 2. Define path and ensure the ACTUAL directory exists
            # 1. Get the Absolute Root of your Project
            # This points to the directory where THIS script lives
            base_path = os.path.dirname(os.path.abspath(__file__)) + "/trade"
            filename = f"{base_path}/trade_{timestamp}_{trade_record['trade_symbol']}.json"

            # os.path.dirname gets the folder path from the filename string
            os.makedirs(os.path.dirname(filename), exist_ok=True)

            # 3. Save with pretty-printing
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(trade_record, f, indent=4, default=str)  # default=str handles datetime objects
                f.flush()  # Pushes data from Python to the OS
                os.fsync(f.fileno())  # Pushes data from the OS to the actual disk

            # 4. Success Log
            self._logger_.info(
                f"📜 SNAPSHOT ARCHIVED | "
                f"Path: {filename} 📂 | "
                f"Status: Analysis Persisted ✅"
            )
        except Exception as e:
            self._logger_.error(
                f"🚨 CRITICAL ERROR: Trade snapshot failed! | "
                f"Symbol: {trade_record.get('trade_symbol')} | Error: {str(e)}"
            )

    def prepare_trade_record(self, market_check, price_match_response, ivr, legs):
        """
        Builds the 'Black Box' record for a single trade initiation.
        """
        # 1. Capture the 'Why' (Analysis Points)
        # We extract specific keys from your market_check logic
        # analysis_summary = {
        #     "protection_status": market_check.get('protected', False),
        #     "iv_rank": ivr,
        #     "gap_threshold": market_check.get('threshold_price', 0),
        #     "logic_path": "fallback_12_delta" if market_check.get('delta_lowered') else "standard_15_delta"
        # }

        # 2. Build the Final Collection (The Best Practice Structure)
        # trade_record = {
        #     "metadata": {
        #         "trade_id": f"BTC-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        #         "timestamp": datetime.now().isoformat(),
        #         "strategy_version": 'strategy_version'
        #     },
        #     "market_context": {
        #         "underlying_price": market_check.get('btc_price'),
        #         "market_condition": market_check.get('type')  # e.g., BULLISH/BEARISH
        #     },
        #     "analysis_points": analysis_summary,
        #     "traded_legs": legs  # This is your list of matched pairs
        # }

        # return trade_record

    def process_position_order(self):
        # Step 2: Retrieve from memory (blocks until data is available)
        position_order_map_data = None
        try:
            position_order_map_data = self.position_order_queue.get(block=False)
        except Empty as e:
            # data not available to persist so skipping the rest code
            return
        success = False
        retries = 0
        while not success and retries < 5:
            try:
                self.save_position_order_snapshot(position_order_map_data)
                success = True
                # Step 3: Success! Data is now cleared from the 'trade_data' variable
                # and the queue automatically as we move to the next item.
            except Exception as e:
                retries += 1
                time.sleep(2)  # Wait before retry
        # Mark the task as done in the queue
        self.position_order_queue.task_done()

    def save_position_order_snapshot(self, position_order_map_data):
        try:
            self.persist_as_json(position_order_map_data)
            # we need to persist in Sqlite also
        except Exception as e:
            self._logger_.error(
                f"🚨 CRITICAL ERROR: Position - Order  snapshot failed! | "
            )

    def persist_as_json(self, position_order_map_data):
        # Create a unique filename using timestamp and symbol
        # 1. Prepare unique metadata
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # filename = f"OTApp/Persistence/History/trade/trade_{timestamp}_{trade_record['trade_symbol']}.json"

        # 2. Define path and ensure the ACTUAL directory exists
        # 1. Get the Absolute Root of your Project
        # This points to the directory where THIS script lives
        base_path = os.path.dirname(os.path.abspath(__file__)) + "/position_orders"
        filename = f"{base_path}/position_order_{timestamp}.json"

        # os.path.dirname gets the folder path from the filename string
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        # 3. Save with pretty-printing
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(position_order_map_data, f, indent=4, default=str)  # default=str handles datetime objects
            f.flush()  # Pushes data from Python to the OS
            os.fsync(f.fileno())  # Pushes data from the OS to the actual disk

        # 4. Success Log
        self._logger_.info(
            f"📜 Position order SNAPSHOT ARCHIVED | "
            f"Path: {filename} 📂 | "
            f"Status: Analysis Persisted ✅"
        )
