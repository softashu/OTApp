# agrasandhani.py

# A collection of all tables and their indices
TABLES = [
    {
        "name": "trade_positions",
        "sql": """
               CREATE TABLE IF NOT EXISTS trade_positions (
                                                              id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                              position_id TEXT UNIQUE NOT NULL,
                                                              order_id TEXT NOT NULL,
                                                              strategy_name TEXT NOT NULL,
                                                              symbol TEXT NOT NULL,
                                                              side TEXT NOT NULL,
                                                              is_filled BOOLEAN DEFAULT 0,
                                                              trade_data TEXT NOT NULL,
                                                              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                                              updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
               );
               """,
        "indices": [
            "CREATE INDEX IF NOT EXISTS idx_pos_id ON trade_positions (position_id);",
            "CREATE INDEX IF NOT EXISTS idx_ord_id ON trade_positions (order_id);",
            "CREATE INDEX IF NOT EXISTS idx_strat ON trade_positions (strategy_name);"
        ]
    },
    # You can easily add more tables here (e.g., "trade_history", "audit_logs")
]