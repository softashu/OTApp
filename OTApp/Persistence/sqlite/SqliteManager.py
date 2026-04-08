"""
    🕉️ CHITRAGUPT: The Celestial Registrar 🕉️
    -----------------------------------------
    "Kshane Kshane Yanmaya Jagat, Tasya Lekhakah Chitraguptah."
    (He who records every moment of the world as it unfolds.)

    Named after the divine scribe who maintains the 'Agrashandhani'—the
    universal ledger of every action, thought, and deed.

    This class serves as the digital 'Kalam' (pen) and 'Patra' (ledger)
    for this application, ensuring that no data is lost, every entry is
    just, and the integrity of the record remains absolute.

    May this implementation be as precise, tireless, and eternal as
    the Great Accountant of the Universe.
"""
import json
import os
import sqlite3
import threading
from datetime import datetime
from enum import Enum

from OTApp.Logger.Logger import AppLogger
# Import the blueprint
from OTApp.Persistence.sqlite.Agrasandhani import TABLES
from OTApp.Persistence.sqlite.Position_Data_Encoder import PositionDataEncoder


class Chitragupt:
    """
    🕉️ THE SINGULAR CHITRAGUPT 🕉️
    Thread-safe Singleton: One Divine Registrar for the entire application.
    """
    _instance = None  # The singular presence
    _lock = threading.Lock()  # The divine barrier to ensure order
    _thread_local = threading.local()  # The key to multi-threaded SQLite

    def __new__(cls, *args, **kwargs):
        # Double-checked locking for efficiency and absolute safety
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    # Create the one and only instance
                    cls._instance = super(Chitragupt, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path=None, logger=None):
        # Ensure initialization only happens once
        if self._initialized:
            return

        # If no path is provided, default to this script's directory
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(base_dir, "universal_trade_ledger.db")

        with self._lock:
            if not self._initialized:
                self.db_path = db_path
                self._logger_ = logger if logger else AppLogger().get_log()
                # self.conn = None
                # self.cursor = None
                self._init_database()
                self._initialized = True

    def _init_database(self):
        # Connect to the database (The 'Sannidhi' or Presence)
        # self.conn = sqlite3.connect(self.db_path)
        # self.conn.row_factory = sqlite3.Row
        # self.cursor = self.conn.cursor()
        # Create universal_trade_ledger.db table
        # Automatically manifest the ledger on startup
        self.sthapana()

    @property
    def connection(self):
        """The 'Sannidhi': Returns a connection unique to the calling thread."""
        if not hasattr(self._thread_local, "conn"):
            # Each thread (e.g., 7256 or 27480) creates its own local connection
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            self._thread_local.conn = conn
        return self._thread_local.conn

    @property
    def cursor(self):
        """Returns a cursor unique to the calling thread."""
        return self.connection.cursor()

    def sthapana(self):
        """Manifests the tables defined in Agrasandhani."""
        # Use local variables here to avoid thread contamination
        conn = self.connection
        cursor = conn.cursor()
        try:
            for schema in TABLES:
                cursor.execute(schema['sql'])
                for index_sql in schema.get('indices', []):
                    cursor.execute(index_sql)
            conn.commit()
            self._logger_.info("🔱 Agrasandhani has been inscribed into the database.")
        except Exception as e:
            conn.rollback()
            self._logger_.error(f"Error during Sthapana: {e}")

    def position_lekhana(self, position_order_map_record):
        """
        CREATE (Lekhana - Writing): Records a new deed into the ledger.

        Thread-safe Write (Lekhana)
        LEKHANA (Bulk Inscription):
        Processes 'position_order_map_record' which is a list of dictionaries.
        Each record is inscribed into the eternal 'trade_positions' ledger.
        """
        if not position_order_map_record:
            return

        # Prepare the list of tuples for SQL execution
        # We use INSERT OR REPLACE to handle records that already exist (Updates them)
        sql = """
                INSERT OR REPLACE INTO trade_positions 
                (position_id, order_id, strategy_name, symbol, side, is_filled, trade_data, updated_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data_to_inscribe = []

        # Iterating through strategies (e.g., 'SEIUSD_strategy')
        for strategy_name, positions in position_order_map_record.items():
            for symbol, pos_obj in positions.items():
                # Extracting the truth from the map
                # 1. Extract the Primary Identifier
                # We use the position_id from the dataclass; fallback to symbol if empty
                p_id = pos_obj.position_id if pos_obj.position_id else f"{symbol}_{strategy_name}"

                # 2. Extract the Order Identifier
                # We take the ID of the last order in the list as the 'active' order
                o_id = str(pos_obj.orders[-1].order_id) if pos_obj.orders else "N/A"

                # Extracting the "Truth Columns" for the database
                side_val = pos_obj.side.value if isinstance(pos_obj.side, Enum) else str(pos_obj.side)
                is_filled_val = 1 if pos_obj.filled else 0

                # 3. Serialize the Whole Being (JSON)
                # This captures all nested orders and filled_orders in one blob.
                t_data = json.dumps(pos_obj.data, cls=PositionDataEncoder)

                data_to_inscribe.append((p_id, o_id, strategy_name, symbol,
                                         side_val, is_filled_val, t_data, now))
        # IMPORTANT: Use the local connection and cursor
        conn = self.connection
        cur = conn.cursor()

        with self._lock:
            # executemany is the high-performance way to write multiple entries
            try:
                cur.executemany(sql, data_to_inscribe)
                conn.commit()
                self._logger_.info(f"🔱 {len(data_to_inscribe)} records have been inscribed/updated in the ledger.")
            except Exception as e:
                conn.rollback()
                self._logger_.error(f"❌ Lekhana failed. The records remain in the void: {e}")

    def darshana(self, table, criteria=None):
        """
        READ (Darshana - Vision): Observes the existing records.
        """
        with self._lock:
            sql = f"SELECT * FROM {table}"
            if criteria:
                sql += f" WHERE {criteria}"

            self.cursor.execute(sql)
            return self.cursor.fetchall()

    def parivartana(self, table, update_dict, criteria):
        """
        UPDATE (Parivartana - Transformation): Amends a record when the truth changes.
        """
        with self._lock:
            updates = ', '.join([f"{k} = ?" for k in update_dict.keys()])
            sql = f"UPDATE {table} SET {updates} WHERE {criteria}"

            try:
                self.cursor.execute(sql, tuple(update_dict.values()))
                self.connection.commit()
                print("The record has been transformed as per the new truth.")
            except Exception as e:
                print(f"Error during Parivartana: {e}")

    def vilaya(self, table, criteria):
        """
        DELETE (Vilaya - Dissolution): Removes a record from the active ledger.
        """
        with self._lock:
            sql = f"DELETE FROM {table} WHERE {criteria}"
            try:
                self.cursor.execute(sql)
                self.connection.commit()
                print("The entry has returned to the void (dissolved).")
            except Exception as e:
                print(f"Error during Vilaya: {e}")

    def visarjana(self):
        """
        CLOSE (Visarjana - Formal Departure): Safely closes the ledger.
        """
        self.connection.close()
        print("The Kalam (pen) is rested. The ledger is sealed.")
