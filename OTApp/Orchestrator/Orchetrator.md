Question : suppose i have two strategy running at time i like to maintan the data fetching one time how they share same data and analysis for all 

Response: To run two strategies while fetching data only once, you should adopt a **Centralized Data Hub** architecture. This prevents redundant API calls, saves bandwidth, and ensures that both strategies analyze the exact same candle data simultaneously.

The most efficient way to do this in Python is by using a **Main Orchestrator Loop** that fetches the data and passes it to different strategy "classes" or "functions."

### Architecture: The "Orchestrator" Pattern

### Python Implementation (Multi-Strategy with Single Fetch)

```python
import pandas as pd
import pandas_ta as ta
import time
from datetime import datetime

# --- STRATEGY 1: Your Sell CE Reversal ---
def strategy_sell_ce(df):
    # Calculate indicators only if they don't exist in shared df
    df['RSI'] = ta.rsi(df['close'], length=14)
    st = ta.supertrend(df['high'], df['low'], df['close'], length=10, multiplier=3)
    df['ST_Dir'] = st['SUPERTd_10_3.0']
    
    # Logic: RSI > 70 + ST Flip Red
    if df['ST_Dir'].iloc[-2] == 1 and df['ST_Dir'].iloc[-1] == -1:
        if df['RSI'].iloc[-5:-1].max() > 70:
            return "SIGNAL: SELL CE"
    return None

# --- STRATEGY 2: Example Trend Following (Long) ---
def strategy_trend_long(df):
    # Uses the SAME 'ST_Dir' calculated above
    if df['ST_Dir'].iloc[-1] == 1:
        return "SIGNAL: HOLD LONG"
    return None

# --- MAIN ORCHESTRATOR (The Single Fetcher) ---
def run_trading_system():
    print("System Started...")
    while True:
        # 1. FETCH DATA ONCE
        # df = exchange.fetch_ohlcv('BTC/USDT', timeframe='1h')
        print(f"[{datetime.now()}] Fetching shared data for BTCUSD...")
        
        # Simulated shared Dataframe
        shared_df = pd.DataFrame() # Imagine real OHLC data here

        # 2. RUN ALL STRATEGIES USING THE SAME DATA
        signal_1 = strategy_sell_ce(shared_df)
        signal_2 = strategy_trend_long(shared_df)

        # 3. EXECUTE LOGIC
        if signal_1: print(f"Strategy 1 says: {signal_1}")
        if signal_2: print(f"Strategy 2 says: {signal_2}")

        # Wait for the next 1-hour candle
        time.sleep(3600)

run_trading_system()

```

### Why this is the best approach for you:

1. **Shared Indicators**: In the code above, if Strategy 1 calculates the **SuperTrend**, Strategy 2 can use those same columns without re-calculating them, saving CPU power.
2. **Synchronized Execution**: Both strategies see the "Red Flip" at the exact same millisecond. This prevents one strategy from entering a trade based on old data while the other is already seeing the new candle.
3. **Conflict Management**: Because both signals are handled in the same `run_trading_system` loop, you can easily add a "Kill Switch." For example: `if signal_1 == "SELL" and active_position_2 == "LONG": skip_trade()`.

### Handling Advanced Data Sharing

If your strategies become very complex or you want to run them in parallel (using multiple CPU cores), you can use a **Local Cache** (like **Redis**) or Python's `multiprocessing.Manager`. This allows one script to "write" the latest BTC price to memory, and 10 different strategy scripts to "read" it instantly without hitting the exchange API again.

[Multi-strategy trading system architecture](https://www.youtube.com/watch?v=yZ9BBYzoMbs)

This video provides an excellent project overview on building a framework where data ingestion is separated from strategy execution, which is exactly what you need for a multi-strategy setup.