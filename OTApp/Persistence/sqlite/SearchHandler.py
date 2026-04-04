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

    def __init__(self, chitragupt_instance: Chitragupt, logger=None):
        # We pass the Chitragupt instance to use its thread-safe lock and connection
        self.scribe = chitragupt_instance
        self._logger_ = logger if logger else AppLogger().get_log()

    def _resurrect_position(self, position_data_json):
        """Internal helper to convert raw JSON dict back to PositionData."""
        # Convert 'side' value to OrderSide Enum if necessary
        # and re-wrap 'orders' into OrderResult objects
        # This is where your 'data class re-generation' logic lives
        return PositionData(**position_data_json)

    def khoj(self, symbol=None, strategy_name=None):
        """
        Executes a targeted search (Khoj) through the trade_positions.
        """
        query = "SELECT trade_data FROM trade_positions"
        conditions = []
        params = []

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
                self.scribe.cursor.execute(query, params)
                rows = self.scribe.cursor.fetchall()
                for (trade_json,) in rows:
                    # Deserialize and resurrect
                    data_dict = json.loads(trade_json)
                    results.append(self._resurrect_position(data_dict))
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
