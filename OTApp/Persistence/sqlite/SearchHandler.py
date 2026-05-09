import json
import sqlite3

from OTApp.Configuration.DataClasses import PositionData
from OTApp.Logger.Logger import AppLogger
from OTApp.Persistence.sqlite.SqliteManager import Chitragupt


class Anveshaka:
    """
    🕉️ ANVESHAKA: The Divine Seeker 🕉️
    Responsible for investigating and retrieving records from the ledger.
    """

    def __init__(self, chitragupt_instance: Chitragupt):
        # We pass the Chitragupt instance to use its thread-safe lock and connection
        self.scribe = chitragupt_instance
        self._logger_ = chitragupt_instance._logger_ if chitragupt_instance._logger_ else AppLogger().get_log()

    def _resurrect_position(self, position_data_json):
        """Internal helper to convert raw JSON dict back to PositionData."""
        # Convert 'side' value to OrderSide Enum if necessary
        # and re-wrap 'orders' into OrderResult objects
        # This is where your 'data class re-generation' logic lives
        """
        Validates, cleans, and reconstructs the PositionData object.
        """
        # 1. Validation Check
        # Ensure it's a dictionary and has the correct __type__
        if not isinstance(position_data_json, dict) or position_data_json.get('__type__') != 'PositionData':
            self._logger_.error(
                f"⚠️ Anveshaka: Skipping invalid record. "
                f"Expected 'PositionData', got '{position_data_json.get('__type__', 'Unknown')}'"
            )
            return None

        # 2. Cleanup
        # Create a copy or pop the metadata to avoid __init__ errors
        clean_data = position_data_json.copy()
        clean_data.pop('__type__', None)

        # 3. Instantiation
        try:
            # Pass the cleaned dictionary to the constructor
            return PositionData(**clean_data)
        except TypeError as e:
            self._logger_.error(f"❌ Anveshaka: Initialization failed for {clean_data.get('position_id')}: {e}")
            return None

    def khoj(self, symbol=None, strategy_name=None, position_id=None):
        """
        Executes a targeted search (Khoj) through the trade_positions.
        """
        query = "SELECT trade_data , strategy_name FROM trade_positions"
        conditions = []
        params = []

        # Filter logic
        if position_id:
            conditions.append("position_id = ?")
            params.append(position_id)

        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol)

        if strategy_name:
            conditions.append("strategy_name = ?")
            params.append(strategy_name)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        results = []

        with self.scribe._lock:
            try:
                # Use local variables here to avoid thread contamination
                conn = self.scribe.connection
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                for (trade_json, strategy_name) in rows:
                    # Deserialize and resurrect
                    data_dict = json.loads(trade_json)
                    db_position = self._resurrect_position(data_dict)
                    db_position.strategy_name = strategy_name
                    results.append(db_position)
                self._logger_.info(f"🔍 Anveshaka: Found {len(results)} matches.")
            except sqlite3.Error as e:
                self._logger_.error(f"❌ Anveshaka Database Error: {e}")
                # You might want to log this to a file here
            except Exception as e:
                self._logger_.error(f"❌ Anveshaka System Error: {e}")
            finally:
                # In SQLite, we don't 'close' the cursor here because it's shared,
                # but we ensure the method returns gracefully.
                pass
        return results
