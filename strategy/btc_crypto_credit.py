# %%
# ==========================================================================
# CRYPTO CREDIT STRATEGY - PRODUCTION READY WITH PHASE 2 (MODULAR & CONFIG)
# ==========================================================================

import requests
import pandas as pd
import time
import schedule
import logging
from datetime import datetime, timedelta
import pytz
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import json
import os

# --- Delta API Client Import (dummy for simulation) ---
from delta_rest_client import DeltaRestClient


# ==========================================================================
# CONFIGURATION CLASS (All parameters are configurable here)
# ==========================================================================
@dataclass
class StrategyConfig:
    api_key: str = os.getenv('delta_shivam_api_key')
    api_secret: str = os.getenv('delta_shivam_api_secret')
    base_url: str = 'https://api.india.delta.exchange'
    underlying_asset: str = "BTC"
    expiry_days_ahead: int = 1
    low_price_threshold: float = 50.0
    high_price_threshold: float = 100.0
    call_sell_lots: int = 3
    call_buy_next_lots: int = 2
    call_buy_prev_lots: int = 1
    put_sell_lots: int = 3
    put_buy_next_lots: int = 1
    put_buy_prev_lots: int = 2
    call_sell_next_strike_lots: int = 3
    put_sell_next_strike_lots: int = 3
    call_buy_next_strike_lots: int = 3
    put_buy_next_strike_lots: int = 3
    profit_threshold: float = 0.01  # 20% profit
    sl_threshold: float = 0.01  # 10% SL for 1/3 buy option
    price_monitoring_interval: int = 30  # seconds
    next_strike_buy_ratio: float = 1 / 3
    entry_time: str = "17:45"  # 5:45 PM
    square_off_time: str = "13:00"  # 1:00 PM next day
    log_level: str = "INFO"
    log_file: str = "crypto_strategy.log"
    timezone: str = 'Asia/Kolkata'


config = StrategyConfig()


# ==========================================================================
# LOGGING SETUP
# ==========================================================================
def setup_logging():
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.log_file, encoding='utf-8'),  # <-- Add encoding here
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


# ==========================================================================
# DELTA CLIENT INITIALIZATION (dummy for simulation)
# ==========================================================================
delta_client = DeltaRestClient(
    base_url=config.base_url,
    api_key=config.api_key,
    api_secret=config.api_secret,
)

IST = pytz.timezone(config.timezone)


# ==========================================================================
# POSITION TRACKING CLASSES
# ==========================================================================
@dataclass
class Position:
    symbol: str
    strike: int
    side: str  # 'buy' or 'sell'
    lots: int
    entry_price: float
    current_price: float = 0.0
    pnl: float = 0.0
    is_active: bool = True
    entry_time: datetime = field(default_factory=lambda: datetime.now(IST))
    sl_price: Optional[float] = None
    target_price: Optional[float] = None
    roll_count: int = 0


@dataclass
class StrategyState:
    is_initialized: bool = False
    phase: int = 1
    no_trade_call: bool = False
    no_trade_put: bool = False
    call_positions: Dict[str, Position] = field(default_factory=dict)
    put_positions: Dict[str, Position] = field(default_factory=dict)
    total_pnl: float = 0.0
    is_monitoring: bool = False
    current_call_main_symbol: str = ""
    current_put_main_symbol: str = ""
    monitoring_thread: Optional[threading.Thread] = None
    stop_monitoring: bool = False


strategy_state = StrategyState()


# %%
# ==========================================================================
# UTILITY FUNCTIONS
# ==========================================================================
def get_mark_price(symbol: str) -> float:
    """Get current mark price for a symbol (simulated API call)"""
    try:
        ticker = delta_client.get_ticker(symbol)
        return float(ticker['mark_price'])
    except Exception as e:
        logger.error(f"❌ Error getting mark price for {symbol}: {e}")
        return 0.0


def get_expiry_date(days_ahead: int = None) -> str:
    """Get expiry date string in DD-MM-YYYY format"""
    if days_ahead is None:
        days_ahead = config.expiry_days_ahead
    expiry_date = datetime.now() + timedelta(days=days_ahead)
    return expiry_date.date().strftime("%d-%m-%Y")


def extract_strike(symbol: str) -> int:
    """Extract strike price from symbol string"""
    return int(symbol.split('-')[2])


def make_symbol(option_type: str, strike: int, expiry_date: str = None) -> str:
    """Create symbol from option type, strike, and expiry"""
    if expiry_date is None:
        expiry_date = get_expiry_date()
    date_parts = expiry_date.split('-')
    expiry_suffix = date_parts[0] + date_parts[1] + date_parts[2][-2:]
    return f"{option_type}-{config.underlying_asset}-{strike}-{expiry_suffix}"


def get_all_strikes_and_products():
    """
    Fetch all available options for the asset and expiry.
    Returns: (products_df, sorted_strikes)
    """
    expiry_date = get_expiry_date()
    headers = {'Accept': 'application/json'}
    r = requests.get(
        f'https://api.india.delta.exchange/v2/tickers?contract_types=call_options,put_options&underlying_asset_symbols={config.underlying_asset}&expiry_date={expiry_date}',
        headers=headers
    )
    data = r.json()['result']
    products_df = pd.DataFrame(data)
    strikes = sorted(set(int(float(s)) for s in products_df['strike_price'].unique()))
    return products_df, strikes


def get_adjacent_strikes(strikes_list, current_strike):
    """Return (prev_strike, next_strike) given the current_strike"""
    idx = strikes_list.index(current_strike)
    prev_strike = strikes_list[idx - 1] if idx > 0 else None
    next_strike = strikes_list[idx + 1] if idx < len(strikes_list) - 1 else None
    return prev_strike, next_strike


# %%
# only for testing no physical significance
def test_utilities():
    print("========= 🔧 Testing Utility Functions =========\n")

    # 1. get_mark_price
    try:
        mark_price = get_mark_price("C-BTC-104000-240625")
        print(f"✅ Mark Price: {mark_price}")
    except Exception as e:
        print(f"❌ get_mark_price error: {e}")

    # 2. get_expiry_date
    try:
        expiry_default = get_expiry_date()
        expiry_plus3 = get_expiry_date(3)
        print(f"✅ Expiry Date (default): {expiry_default}")
        print(f"✅ Expiry Date (+3 days): {expiry_plus3}")
    except Exception as e:
        print(f"❌ get_expiry_date error: {e}")

    # 3. extract_strike
    try:
        strike = extract_strike("C-BTC-104000-240625")
        print(f"✅ Extracted Strike: {strike}")
    except Exception as e:
        print(f"❌ extract_strike error: {e}")

    # 4. make_symbol
    try:
        call_symbol = make_symbol("C", 104000)
        put_symbol = make_symbol("P", 104000)
        print(f"✅ Call Symbol: {call_symbol}")
        print(f"✅ Put Symbol (custom date): {put_symbol}")
    except Exception as e:
        print(f"❌ make_symbol error: {e}")

    # 5. get_all_strikes_and_products
    try:
        products_df, strikes = get_all_strikes_and_products()
        print(f"✅ Got {len(products_df)} products")
        print(f"✅ Strikes: {strikes[:]}")
    except Exception as e:
        print(f"❌ get_all_strikes_and_products error: {e}")
        products_df, strikes = None, []

    # 6. get_adjacent_strikes
    try:
        current_strike = 104000
        if strikes and current_strike in strikes:
            prev_strike, next_strike = get_adjacent_strikes(strikes, current_strike)
            print(f"✅ Adjacent to {current_strike} → Prev: {prev_strike}, Next: {next_strike}")
        else:
            print(f"❌ Strike {current_strike} not in list or strikes not fetched")
    except Exception as e:
        print(f"❌ get_adjacent_strikes error: {e}")

    print("\n========= ✅ All Function Tests Complete =========")


# Call the test function
test_utilities()


# %%
# ==========================================================================
# STRATEGY PHASE 1: ENTRY LOGIC
# ==========================================================================
# phase 1 code of credit strategy for initial hedge 1 3 2 and 2 1 3 for both call and put respectively
def phase1_entry():
    """
    Phase 1: Entry logic for initial hedge formation.
    - Filters options by price and OI.
    - Selects main strikes and adjacent strikes.
    - Simulates entry trades and logs/prints actions.
    """
    logger.info("[PHASE 1] Starting entry logic...")
    products_df, strikes = get_all_strikes_and_products()

    # Filter options by price
    filtered_options1 = [o for o in products_df.to_dict('records') if
                         int(float(o['mark_price'])) < config.low_price_threshold]
    filtered_options2 = [o for o in products_df.to_dict('records') if
                         int(float(o['mark_price'])) > config.high_price_threshold]

    calls1 = [o for o in filtered_options1 if o['contract_type'] == 'call_options']
    puts1 = [o for o in filtered_options1 if o['contract_type'] == 'put_options']
    calls2 = [o for o in filtered_options2 if o['contract_type'] == 'call_options']
    puts2 = [o for o in filtered_options2 if o['contract_type'] == 'put_options']

    # Find max OI contracts and set no_trade flags
    no_trade_call = no_trade_put = False
    max_oi_call1 = max_oi_call2 = None
    if calls1:
        max_oi_call1 = max(calls1, key=lambda x: int(float(x['oi_contracts'])))
    if calls2:
        max_oi_call2 = max(calls2, key=lambda x: int(float(x['oi_contracts'])))
    if max_oi_call1 and max_oi_call2:
        if int(float(max_oi_call1['oi_contracts'])) > int(float(max_oi_call2['oi_contracts'])):
            no_trade_call = True
            logger.info("[PHASE 1] Call side trade skipped due to higher OI in low price bucket.")

    max_oi_put1 = max_oi_put2 = None
    if puts1:
        max_oi_put1 = max(puts1, key=lambda x: int(float(x['oi_contracts'])))
        print(max_oi_put1['symbol'])
    if puts2:
        max_oi_put2 = max(puts2, key=lambda x: int(float(x['oi_contracts'])))
        print(max_oi_put2['symbol'])
    if max_oi_put1 and max_oi_put2:
        if int(float(max_oi_put1['oi_contracts'])) > int(float(max_oi_put2['oi_contracts'])):
            no_trade_put = True
            logger.info("[PHASE 1] Put side trade skipped due to higher OI in low price bucket.")

    strategy_state.no_trade_call = no_trade_call
    strategy_state.no_trade_put = no_trade_put

    logger.info(f"no_trade_call: {no_trade_call}, no_trade_put: {no_trade_put}")

    # Select main symbols and simulate trades
    if not no_trade_call and calls2:
        call_symbol = max(calls2, key=lambda x: int(float(x['oi_contracts'])))['symbol']
        call_strike = extract_strike(call_symbol)
        if call_strike not in strikes[2:-2]:
            logger.warning(f"[PHASE 1] Skipping call trade: {call_strike} is near edge")
            strategy_state.no_trade_call = True
        else:
            call_prev, call_next = get_adjacent_strikes(strikes, call_strike)
            expiry = call_symbol.split('-')[3]
            call_next_symbol = make_symbol('C', call_next)
            call_prev_symbol = make_symbol('C', call_prev)
            # strategy_state.call_positions = {
            #     'call_sell': Position(call_symbol, call_strike, 'sell', config.call_sell_lots, get_mark_price(call_symbol)),
            #     'call_next': Position(call_next_symbol, call_next, 'buy', config.call_buy_next_lots, get_mark_price(call_next_symbol)),
            #     'call_prev': Position(call_prev_symbol, call_prev, 'buy', config.call_buy_prev_lots, get_mark_price(call_prev_symbol)),
            # }
            call_sell = Position(call_symbol, call_strike, 'sell', config.call_sell_lots, get_mark_price(call_symbol))
            call_sell.is_initial = True  # <-- Set is_initial True for main call leg
            call_next = Position(call_next_symbol, call_next, 'buy', config.call_buy_next_lots,
                                 get_mark_price(call_next_symbol))
            call_prev = Position(call_prev_symbol, call_prev, 'buy', config.call_buy_prev_lots,
                                 get_mark_price(call_prev_symbol))
            strategy_state.call_positions = {
                'call_sell': call_sell,
                'call_next': call_next,
                'call_prev': call_prev,
            }

            strategy_state.current_call_main_symbol = call_symbol
            logger.info(
                f"[PHASE 1] Call side: Sell {config.call_sell_lots} {call_symbol}, Buy {config.call_buy_next_lots} {call_next_symbol}, Buy {config.call_buy_prev_lots} {call_prev_symbol}")

    if not no_trade_put and puts2:
        put_symbol = max(puts2, key=lambda x: int(float(x['oi_contracts'])))['symbol']
        put_strike = extract_strike(put_symbol)
        if put_strike not in strikes[2:-2]:
            logger.warning(f"[PHASE 1] Skipping put trade: {put_strike} is near edge")
            strategy_state.no_trade_put = True
        else:
            put_prev, put_next = get_adjacent_strikes(strikes, put_strike)
            expiry = put_symbol.split('-')[3]
            put_next_symbol = make_symbol('P', put_next)
            put_prev_symbol = make_symbol('P', put_prev)
            # strategy_state.put_positions = {
            #     'put_sell': Position(put_symbol, put_strike, 'sell', config.put_sell_lots, get_mark_price(put_symbol)),
            #     'put_next': Position(put_next_symbol, put_next, 'buy', config.put_buy_next_lots, get_mark_price(put_next_symbol)),
            #     'put_prev': Position(put_prev_symbol, put_prev, 'buy', config.put_buy_prev_lots, get_mark_price(put_prev_symbol)),
            # }
            put_sell = Position(put_symbol, put_strike, 'sell', config.put_sell_lots, get_mark_price(put_symbol))
            put_sell.is_initial = True  # <-- Set is_initial True for main put leg
            put_next = Position(put_next_symbol, put_next, 'buy', config.put_buy_next_lots,
                                get_mark_price(put_next_symbol))
            put_prev = Position(put_prev_symbol, put_prev, 'buy', config.put_buy_prev_lots,
                                get_mark_price(put_prev_symbol))
            strategy_state.put_positions = {
                'put_sell': put_sell,
                'put_next': put_next,
                'put_prev': put_prev,
            }
            strategy_state.current_put_main_symbol = put_symbol
            logger.info(
                f"[PHASE 1] Put side: Sell {config.put_sell_lots} {put_symbol}, Buy {config.put_buy_next_lots} {put_next_symbol}, Buy {config.put_buy_prev_lots} {put_prev_symbol}")

    strategy_state.is_initialized = True
    strategy_state.phase = 1
    logger.info("[PHASE 1] Entry complete.")
    for k, v in strategy_state.call_positions.items():
        logger.info(f"  CALL {k}: {v.lots} @ {v.entry_price:.2f} ({v.symbol})")
    for k, v in strategy_state.put_positions.items():
        logger.info(f"  PUT  {k}: {v.lots} @ {v.entry_price:.2f} ({v.symbol})")


# %%
# Just for testing
# def phase1_entry():
#     """
#     Phase 1: Demo entry logic for initial hedge formation.
#     Always sets up positions at 108000 with prev/next strikes (gap of 200) for both call and put,
#     using get_mark_price for all prices.
#     """
#     logger.info("[PHASE 1] DEMO ENTRY: Forcing trades at 108000 with adjacent strikes (gap 200).")

#     # Set up dummy strikes with a gap of 200
#     strikes = [106000,106200,106400,106600,106800,107000,107200, 107400, 107600, 107800, 108000, 108200, 108400, 108600, 108800, 109000,109200,109400,109600,109800,110000]

#     # Set up positions using get_mark_price
#     def make_symbol(opt_type, strike):
#         return f"{opt_type}-BTC-{strike}-260625"

#     # Set up positions using get_mark_price with new symbol format
#     call_sell = Position(make_symbol('C', 108000), 108000, 'sell', 3, get_mark_price(make_symbol('C', 108000)))
#     call_sell.is_initial = True  # <-- Set is_initial True for main call leg
#     call_prev = Position(make_symbol('C', 107800), 107800, 'buy', 1, get_mark_price(make_symbol('C', 107800)))
#     call_next = Position(make_symbol('C', 108200), 108200, 'buy', 2, get_mark_price(make_symbol('C', 108200)))

#     put_sell = Position(make_symbol('P', 108000), 108000, 'sell', 3, get_mark_price(make_symbol('P', 108000)))
#     put_sell.is_initial = True  # <-- Set is_initial True for main put leg
#     put_prev = Position(make_symbol('P', 107800), 107800, 'buy', 2, get_mark_price(make_symbol('P', 107800)))
#     put_next = Position(make_symbol('P', 108200), 108200, 'buy', 1, get_mark_price(make_symbol('P', 108200)))

#     strategy_state.call_positions = {
#         'call_sell': call_sell,
#         'call_prev': call_prev,
#         'call_next': call_next,
#     }
#     strategy_state.put_positions = {
#         'put_sell': put_sell,
#         'put_prev': put_prev,
#         'put_next': put_next,
#     }
#     strategy_state.current_call_main_symbol = make_symbol('C', 108000)
#     strategy_state.current_put_main_symbol = make_symbol('P', 108000)
#     strategy_state.is_initialized = True
#     strategy_state.phase = 1
#     strategy_state.no_trade_call = False
#     strategy_state.no_trade_put = False

#     logger.info("[PHASE 1] DEMO ENTRY complete.")
#     for k, v in strategy_state.call_positions.items():
#         logger.info(f"  CALL {k}: {v.lots} @ {v.entry_price:.2f} ({v.symbol})")
#     for k, v in strategy_state.put_positions.items():
#         logger.info(f"  PUT  {k}: {v.lots} @ {v.entry_price:.2f} ({v.symbol})")

# %%
# logger = setup_logging()
# phase1_entry()


# %%
# === 1. Run Phase 1 ===
logger = setup_logging()
phase1_entry()

# === 5. Run Phase 2 to observe rolling logic ===

# %%
print(vars(strategy_state))

# %%
print(strategy_state.call_positions.items())


# %%
# phase 2 code for monitoring and adjusting
def monitor_and_adjust():
    """
    Monitor prices and perform dynamic adjustment as per phase 2 logic.
    - Rolls main leg if profit threshold is hit, sets SL to cost, and simulates new trades.
    - For calls: first roll to next-to-next, then to next; for puts: first roll to prev-to-prev, then to prev.
    - Buys nearest above/below at <= 1/3 price.
    - Repeats for all sold legs.
    """
    logger.info("[PHASE 2] Monitoring started...")
    strategy_state.phase = 2

    def get_next(strikes, current_strike):
        idx = strikes.index(current_strike)
        return strikes[idx + 1] if idx + 1 < len(strikes) else None

    def get_next_to_next(strikes, current_strike):
        idx = strikes.index(current_strike)
        return strikes[idx + 2] if idx + 2 < len(strikes) else None

    def get_prev(strikes, current_strike):
        idx = strikes.index(current_strike)
        return strikes[idx - 1] if idx - 1 >= 0 else None

    def get_prev_to_prev(strikes, current_strike):
        idx = strikes.index(current_strike)
        return strikes[idx - 2] if idx - 2 >= 0 else None

    def find_nearest_option(strikes, products_df, base_strike, direction, price_limit, expiry, option_type):
        idx = strikes.index(base_strike)
        search_range = range(idx + 1, len(strikes)) if direction == 1 else range(idx - 1, -1, -1)
        for i in search_range:
            strike = strikes[i]
            symbol = make_symbol(option_type, strike)
            price = get_mark_price(symbol)
            if price <= price_limit:
                return symbol, strike, price
        return None, None, None

    while not strategy_state.stop_monitoring:
        now = datetime.now(IST)
        square_off_hour, square_off_minute = map(int, config.square_off_time.split(":"))
        square_off_dt = now.replace(hour=square_off_hour, minute=square_off_minute, second=0, microsecond=0)
        if now >= square_off_dt:
            square_off_dt += timedelta(days=1)
        if now >= square_off_dt:
            logger.info("[PHASE 2] Square-off time reached. Stopping monitoring.")
            break

        products_df, strikes = get_all_strikes_and_products()

        # --- Monitor all call sell legs ---
        for k, main in list(strategy_state.call_positions.items()):
            if main.side == 'sell' and main.is_active:
                if not hasattr(main, 'is_initial'):
                    main.is_initial = False
                main.current_price = get_mark_price(main.symbol)
                profit = (main.entry_price - main.current_price) / main.entry_price
                print(
                    f"CALL main.symbol: {main.symbol}, main.current_price: {main.current_price}, main.entry_price: {main.entry_price}, profit: {profit}")

                # 1. If profit threshold hit and SL not already set, roll and set SL
                if profit >= config.profit_threshold and main.sl_price is None:
                    logger.info(
                        f"[PHASE 2] Call leg {main.symbol} hit {config.profit_threshold * 100:.0f}% profit. Rolling...")
                    main.sl_price = main.entry_price  # SL to cost for main leg
                    print(f"main.sl_price: {main.sl_price}")

                    # Use next-to-next for initial, next for subsequent rolls
                    if main.is_initial:
                        next_strike = get_next_to_next(strikes, main.strike)
                    else:
                        next_strike = get_next(strikes, main.strike)
                    print(f"next_strike: {next_strike}")

                    if next_strike is not None:
                        expiry = main.symbol.split('-')[3]
                        next_symbol = make_symbol('C', next_strike)
                        next_price = get_mark_price(next_symbol)
                        price_limit = next_price * config.next_strike_buy_ratio
                        buy_symbol, buy_strike, buy_price = find_nearest_option(
                            strikes, products_df, next_strike, direction=1, price_limit=price_limit, expiry=expiry,
                            option_type='C'
                        )
                        new_main_key = f'call_sell_{next_strike}'
                        if new_main_key not in strategy_state.call_positions:
                            new_main_leg = Position(next_symbol, next_strike, 'sell', config.call_sell_next_strike_lots,
                                                    next_price)
                            new_main_leg.is_initial = False
                            strategy_state.call_positions[new_main_key] = new_main_leg

                        if buy_symbol:
                            buy_key = f'call_buy_{main.strike}_to_{buy_strike}_1_3'
                            buy_pos = Position(buy_symbol, buy_strike, 'buy', config.call_buy_next_strike_lots,
                                               buy_price)
                            strategy_state.call_positions[buy_key] = buy_pos
                            logger.info(
                                f"[PHASE 2] Sold 3 {next_symbol} @ {next_price:.2f}, bought 3 {buy_symbol} @ {buy_price:.2f}")
                        else:
                            logger.warning(
                                f"[PHASE 2] No suitable call option found to buy at <= 1/3 price for {next_symbol}")

                    else:
                        logger.info("[PHASE 2] No further strikes to roll to.")

                # 2. Check if SL is hit (only if SL was set after profit)
                elif main.sl_price is not None and main.current_price >= main.sl_price:
                    logger.info(f"[PHASE 2] SL hit for main leg {main.symbol}. Exiting main leg positions only.")
                    for kk, pp in list(strategy_state.call_positions.items()):
                        if pp.strike == main.strike:  # Only positions with same strike
                            pp.is_active = False
                            logger.info(f"[PHASE 2] Exited position: {pp.symbol}")
                    main.is_active = False

                    # Set SL for the corresponding 1/3 buy position for this main leg only
                    # for k2, pos in list(strategy_state.call_positions.items()):
                    #     if k2.startswith(f'call_buy_{main.strike}_to_') and pos.is_active and pos.sl_price is None:
                    #         pos.sl_price = pos.entry_price * 0.90  # 10% SL for buy position
                    #         logger.info(f"[PHASE 2] Set SL for buy position {pos.symbol}: {pos.sl_price:.2f}")
                    for k2, pos in list(strategy_state.call_positions.items()):
                        if k2.startswith(f'call_buy_{main.strike}_to_') and pos.is_active and pos.sl_price is None:
                            pos.sl_price = pos.entry_price * (1 - config.sl_threshold)  # 10% SL for buy position
                            logger.info(
                                f"[PHASE 2] Set SL for buy position {pos.symbol} (buy_key: {k2}, main_leg: {main.symbol}, main_strike: {main.strike}) at {pos.sl_price:.2f}"
                            )
                    break  # Stop processing this main leg in this cycle

        # 3. Check SL for buy 1/3 positions (independent of main leg, only if SL is set)
        for k2, pos in list(strategy_state.call_positions.items()):
            if pos.side == 'buy' and pos.is_active and pos.sl_price is not None:
                pos.current_price = get_mark_price(pos.symbol)
                if pos.current_price <= pos.sl_price:
                    logger.info(
                        f"[PHASE 2] SL hit for buy position {pos.symbol} (buy_key: {k2}) at price {pos.current_price:.2f} (SL: {pos.sl_price:.2f}). Exiting position."
                    )
                    pos.is_active = False
                    # Optionally, remove from dict if you want:
                    del strategy_state.call_positions[k2]

        # --- Monitor all put sell legs ---
        for k, main in list(strategy_state.put_positions.items()):
            if main.side == 'sell' and main.is_active:
                if not hasattr(main, 'is_initial'):
                    main.is_initial = False
                main.current_price = get_mark_price(main.symbol)
                profit = (main.entry_price - main.current_price) / main.entry_price
                print(
                    f"PUT main.symbol: {main.symbol}, main.current_price: {main.current_price}, main.entry_price: {main.entry_price}, profit: {profit}")

                # 1. If profit threshold hit and SL not already set, roll and set SL
                if profit >= config.profit_threshold and main.sl_price is None:
                    logger.info(
                        f"[PHASE 2] Put leg {main.symbol} hit {config.profit_threshold * 100:.0f}% profit. Rolling...")
                    main.sl_price = main.entry_price  # SL to cost for main leg
                    print(f"main.sl_price: {main.sl_price}")

                    # Use prev-to-prev for initial, prev for subsequent rolls
                    if main.is_initial:
                        prev_strike = get_prev_to_prev(strikes, main.strike)
                    else:
                        prev_strike = get_prev(strikes, main.strike)
                    print(f"prev_strike: {prev_strike}")

                    if prev_strike is not None:
                        expiry = main.symbol.split('-')[3]
                        prev_symbol = make_symbol('P', prev_strike)
                        prev_price = get_mark_price(prev_symbol)
                        price_limit = prev_price * config.next_strike_buy_ratio
                        buy_symbol, buy_strike, buy_price = find_nearest_option(
                            strikes, products_df, prev_strike, direction=-1, price_limit=price_limit, expiry=expiry,
                            option_type='P'
                        )
                        new_main_key = f'put_sell_{prev_strike}'
                        if new_main_key not in strategy_state.put_positions:
                            new_main_leg = Position(prev_symbol, prev_strike, 'sell', config.put_sell_next_strike_lots,
                                                    prev_price)
                            new_main_leg.is_initial = False
                            strategy_state.put_positions[new_main_key] = new_main_leg

                        if buy_symbol:
                            buy_key = f'put_buy_{main.strike}_to_{buy_strike}_1_3'
                            buy_pos = Position(buy_symbol, buy_strike, 'buy', config.put_buy_next_strike_lots,
                                               buy_price)
                            strategy_state.put_positions[buy_key] = buy_pos
                            logger.info(
                                f"[PHASE 2] Sold 3 {prev_symbol} @ {prev_price:.2f}, bought 3 {buy_symbol} @ {buy_price:.2f}")
                        else:
                            logger.warning(
                                f"[PHASE 2] No suitable put option found to buy at <= 1/3 price for {prev_symbol}")

                    else:
                        logger.info("[PHASE 2] No further strikes to roll to.")

                # 2. Check if SL is hit (only if SL was set after profit)
                elif main.sl_price is not None and main.current_price >= main.sl_price:
                    logger.info(f"[PHASE 2] SL hit for main leg {main.symbol}. Exiting main leg positions only.")
                    for kk, pp in list(strategy_state.put_positions.items()):
                        if pp.strike == main.strike:  # Only positions with same strike
                            pp.is_active = False
                            logger.info(f"[PHASE 2] Exited position: {pp.symbol}")
                    main.is_active = False

                    # Set SL for the corresponding 1/3 buy position for this main leg only
                    # for k2, pos in list(strategy_state.put_positions.items()):
                    #     if k2.startswith(f'put_buy_{main.strike}_to_') and pos.is_active and pos.sl_price is None:
                    #         pos.sl_price = pos.entry_price * 0.90  # 10% SL for buy position
                    #         logger.info(f"[PHASE 2] Set SL for buy position {pos.symbol}: {pos.sl_price:.2f}")
                    for k2, pos in list(strategy_state.put_positions.items()):
                        if k2.startswith(f'put_buy_{main.strike}_to_') and pos.is_active and pos.sl_price is None:
                            pos.sl_price = pos.entry_price * (1 - config.sl_threshold)  # 10% SL for buy position
                            logger.info(
                                f"[PHASE 2] Set SL for buy position {pos.symbol} (buy_key: {k2}, main_leg: {main.symbol}, main_strike: {main.strike}) at {pos.sl_price:.2f}"
                            )
                    break  # Stop processing this main leg in this cycle

        # 3. Check SL for buy 1/3 positions (independent of main leg, only if SL is set)
        for k2, pos in list(strategy_state.put_positions.items()):
            if pos.side == 'buy' and pos.is_active and pos.sl_price is not None:
                pos.current_price = get_mark_price(pos.symbol)
                if pos.current_price <= pos.sl_price:
                    logger.info(
                        f"[PHASE 2] SL hit for buy position {pos.symbol} (buy_key: {k2}) at price {pos.current_price:.2f} (SL: {pos.sl_price:.2f}). Exiting position."
                    )
                    pos.is_active = False
                    # Optionally, remove from dict if you want:
                    del strategy_state.put_positions[k2]

        # Sleep for monitoring interval
        time.sleep(config.price_monitoring_interval)
    logger.info("[PHASE 2] Monitoring stopped.")


# %%
print(vars(strategy_state))

# %%
monitor_and_adjust()


# %%
# ==========================================================================
# SQUARE-OFF & PNL CALCULATION
# ==========================================================================

def square_off_and_calculate_pnl():
    """
    Square off all positions and calculate PnL.
    - Fetches current prices for all open positions.
    - Calculates and prints/logs PnL for each position and total.
    - Stops the monitoring/event-listener loop.
    """
    logger.info("[SQUARE-OFF] Squaring off all positions and calculating PnL...")
    total_pnl = 0.0
    for pos in list(strategy_state.call_positions.values()) + list(strategy_state.put_positions.values()):
        pos.current_price = get_mark_price(pos.symbol)
        if pos.side == 'sell':
            pos.pnl = (pos.entry_price - pos.current_price) * pos.lots
        else:
            pos.pnl = (pos.current_price - pos.entry_price) * pos.lots
        total_pnl += pos.pnl
        print(
            f"[SQUARE-OFF] {pos.side.upper()} {pos.symbol} | Entry: {pos.entry_price:.2f} | Exit: {pos.current_price:.2f} | Lots: {pos.lots} | PnL: {pos.pnl:.2f}")
    strategy_state.total_pnl = total_pnl
    print(f"\n💰 Total Dummy PnL: ₹{total_pnl:.2f}\n")
    logger.info(f"[SQUARE-OFF] Total Dummy PnL: INR{total_pnl:.2f}")
    # Stop monitoring
    strategy_state.stop_monitoring = True


# %%
# ==========================================================================
# SCHEDULER SETUP
# ==========================================================================

def start_strategy():
    """
    Schedules entry, monitoring, and square-off.
    - Entry and monitoring start at config.entry_time.
    - Monitoring runs in a background thread (event-listener style).
    - Square-off and PnL calculation at config.square_off_time.
    """
    # Schedule entry
    schedule.every().day.at(config.entry_time).do(phase1_entry)

    # Schedule monitoring (event-listener like)
    def start_monitoring_thread():
        if not strategy_state.is_monitoring:
            strategy_state.is_monitoring = True
            strategy_state.stop_monitoring = False
            t = threading.Thread(target=monitor_and_adjust)
            t.daemon = True
            strategy_state.monitoring_thread = t
            t.start()

    schedule.every().day.at(config.entry_time).do(start_monitoring_thread)

    # Schedule square-off
    schedule.every().day.at(config.square_off_time).do(square_off_and_calculate_pnl)

    print("⏳ Scheduler started for production-ready forward testing (dummy mode)...")
    while True:
        schedule.run_pending()
        time.sleep(5)


# ==========================================================================
# MAIN ENTRY POINT
# ==========================================================================

if __name__ == "__main__":
    start_strategy()

# %%
# this code is completed rest part will show how to use delta exchange api

# %%
# res = delta_client.get_product('')
# symdf = pd.DataFrame(res)
# symdf
#
# # %%
# symdf.iloc[0]
#
# # %%
# symdf['settlement_time'] = pd.to_datetime(symdf['settlement_time'], utc=True)
# symdf['expiry'] = symdf['settlement_time'].dt.date
#
# # %%
# import datetime
# from datetime import datetime, timedelta
#
# expirydate = datetime.now() + timedelta(days=1)
# expiry_date = expirydate.date().strftime("%d-%m-%Y")
# # symdf[(symdf.expiry==expirydate.date()) & (symdf.contract_unit_currency=='BTC')]
#
#
# print(expiry_date)
#
# # %%
# import requests
#
# headers = {
#     'Accept': 'application/json'
# }
#
# r = requests.get(
#     f'https://api.india.delta.exchange/v2/tickers?contract_types=call_options,put_options&underlying_asset_symbols=BTC&expiry_date={expiry_date}',
#     params={
#
#     }, headers=headers)
#
# print(r.json())
# data = r.json()
# print(data.keys())
#
# # %%
#
# filtered_options1 = [option for option in data['result'] if int(float(option['mark_price'])) < 50]
# filtered_options2 = [option for option in data['result'] if int(float(option['mark_price'])) > 100]
# print(filtered_options2)
#
# calls1 = [option for option in filtered_options2 if option['contract_type'] == 'call_options']
# puts1 = [option for option in filtered_options2 if option['contract_type'] == 'put_options']
# calls2 = [option for option in filtered_options2 if option['contract_type'] == 'call_options']
# puts2 = [option for option in filtered_options2 if option['contract_type'] == 'put_options']
#
# # Find maximum OI contracts for calls and puts
# if calls1:
#     max_oi_call1 = max(calls1, key=lambda x: int(float(x['oi_contracts'])))
#     print(f"Call with highest OI contracts (price > $50):")
#     print(f"Symbol: {max_oi_call1['symbol']}")
#     print(f"Strike: {max_oi_call1['strike_price']}")
#     print(f"Mark Price: ${max_oi_call1['mark_price']}")
#     print(f"OI Contracts: {max_oi_call1['oi_contracts']}")
#     print()
#
# if puts1:
#     max_oi_put1 = max(puts1, key=lambda x: int(float(x['oi_contracts'])))
#     print(f"Put with highest OI contracts (price > $50):")
#     print(f"Symbol: {max_oi_put1['symbol']}")
#     print(f"Strike: {max_oi_put1['strike_price']}")
#     print(f"Mark Price: ${max_oi_put1['mark_price']}")
#     print(f"OI Contracts: {max_oi_put1['oi_contracts']}")
#     print()
# # Find maximum OI contracts for calls and puts
# if calls2:
#     max_oi_call2 = max(calls2, key=lambda x: int(float(x['oi_contracts'])))
#     print(f"Call with highest OI contracts (price > $100):")
#     print(f"Symbol: {max_oi_call2['symbol']}")
#     print(f"Strike: {max_oi_call2['strike_price']}")
#     print(f"Mark Price: ${max_oi_call2['mark_price']}")
#     print(f"OI Contracts: {max_oi_call2['oi_contracts']}")
#     print()
#
# if puts2:
#     max_oi_put2 = max(puts2, key=lambda x: int(float(x['oi_contracts'])))
#     print(f"Put with highest OI contracts (price > $100):")
#     print(f"Symbol: {max_oi_put2['symbol']}")
#     print(f"Strike: {max_oi_put2['strike_price']}")
#     print(f"Mark Price: ${max_oi_put2['mark_price']}")
#     print(f"OI Contracts: {max_oi_put2['oi_contracts']}")
#     print()
#
# no_trade_call, no_trade_put = False, False
#
# if max_oi_call1['symbol'] != max_oi_call2['symbol']:
#     no_trade_call = True
# if max_oi_put1['symbol'] != max_oi_put2['symbol']:
#     no_trade_put = True
#
# # %%
# call_symbol = max_oi_call2['symbol']
# put_symbol = max_oi_put2['symbol']
#
# # %%
# import requests
#
# headers = {
#     'Accept': 'application/json'
# }
#
# r = requests.get('https://api.india.delta.exchange/v2/tickers', params={
#     'contract_types': 'call_options,put_options',
#     'underlying_asset_symbols': 'BTC'
# }, headers=headers)
#
# products = r.json()['result']
# products_df = pd.DataFrame(products)
# print(sorted(products_df['strike_price'].unique()))
#
#
# # %%
# def extract_strike(symbol):
#     # Assumes symbol format like 'C-BTC-103000-070625'
#     return int(symbol.split('-')[2])
#
#
# import numpy as np
#
# # Convert all strike prices to integers and sort
# strikes = sorted(set(int(float(s)) for s in products_df['strike_price'].unique()))
#
#
# def get_adjacent_strikes(strikes_list, current_strike):
#     """Return (prev_strike, next_strike) given the current_strike"""
#     idx = strikes_list.index(current_strike)
#     prev_strike = strikes_list[idx - 1] if idx > 0 else None
#     next_strike = strikes_list[idx + 1] if idx < len(strikes_list) - 1 else None
#     return prev_strike, next_strike
#
#
# call_strike = extract_strike(call_symbol)  # e.g. 103000
# put_strike = extract_strike(put_symbol)  # e.g. 101200
#
# call_prev, call_next = get_adjacent_strikes(strikes, call_strike)
# put_prev, put_next = get_adjacent_strikes(strikes, put_strike)
#
# print("Call Strike:", call_strike)
# print("  ↳ Previous Strike:", call_prev)
# print("  ↳ Next Strike:", call_next)
#
# print("Put Strike:", put_strike)
# print("  ↳ Previous Strike:", put_prev)
# print("  ↳ Next Strike:", put_next)
#
#
# def make_symbol(option_type, base_symbol, new_strike):
#     expiry = base_symbol.split('-')[3]
#     return f"{option_type}-BTC-{new_strike}-{expiry}"
#
#
# call_next_symbol = make_symbol('C', call_symbol, call_next)
# call_prev_symbol = make_symbol('C', call_symbol, call_prev)
#
# put_next_symbol = make_symbol('P', put_symbol, put_next)
# put_prev_symbol = make_symbol('P', put_symbol, put_prev)
#
# print("Call Next Symbol:", call_next_symbol)
# print("Call Previous Symbol:", call_prev_symbol)
# print("Put Next Symbol:", put_next_symbol)
# print("Put Previous Symbol:", put_prev_symbol)
#
# # %%
# call_product = delta_client.get_ticker(call_next_symbol)
# r = call_product['mark_price']
# print(r)
#
#
# def get_mark_price(symbol):
#     return float(delta_client.get_ticker(symbol)['mark_price'])
#
#
# print(get_mark_price(call_next_symbol))
#
# # %%
# import schedule
# import time
# from datetime import datetime
# import pytz
#
# IST = pytz.timezone('Asia/Kolkata')
#
#
# # Dummy Delta API client call
# def get_mark_price(symbol):
#     return float(delta_client.get_ticker(symbol)['mark_price'])
#
#
# # Dummy state containers
# entry_prices = {}
# pnl_tracker = {}
# place_trade_call = False
# place_trade_put = False
#
#
# # --- Scheduler Job: Entry ---
# def place_initial_orders():
#     global entry_prices, pnl_tracker, place_trade_call, place_trade_put
#     print(f"[{datetime.now(IST)}] 🚀 Simulating entry orders...")
#
#     # Clear previous state
#     entry_prices.clear()
#     pnl_tracker.clear()
#     place_trade_call = False
#     place_trade_put = False
#
#     # Entry logic for call side
#     if not no_trade_call:
#         place_trade_call = True
#         entry_prices['call_next'] = get_mark_price(call_next_symbol)
#         entry_prices['call_prev'] = get_mark_price(call_prev_symbol)
#         entry_prices['call_sell'] = get_mark_price(call_symbol)
#
#     # Entry logic for put side
#     if not no_trade_put:
#         place_trade_put = True
#         entry_prices['put_next'] = get_mark_price(put_next_symbol)
#         entry_prices['put_prev'] = get_mark_price(put_prev_symbol)
#         entry_prices['put_sell'] = get_mark_price(put_symbol)
#
#     for k, v in entry_prices.items():
#         print(f"📈 Entry {k}: {v:.2f}")
#
#
# # --- Scheduler Job: Square-Off ---
# def square_off_orders():
#     global pnl_tracker, place_trade_call, place_trade_put
#     print(f"[{datetime.now(IST)}] 🧾 Simulating square-off and calculating PnL...")
#
#     exit_prices = {}
#
#     # Only square-off call side if trade was placed
#     if place_trade_call:
#         exit_prices['call_next'] = get_mark_price(call_next_symbol)
#         exit_prices['call_prev'] = get_mark_price(call_prev_symbol)
#         exit_prices['call_sell'] = get_mark_price(call_symbol)
#
#         pnl_tracker['call_next'] = 2 * (exit_prices['call_next'] - entry_prices['call_next'])
#         pnl_tracker['call_prev'] = 1 * (exit_prices['call_prev'] - entry_prices['call_prev'])
#         pnl_tracker['call_sell'] = 3 * (entry_prices['call_sell'] - exit_prices['call_sell'])
#
#     # Only square-off put side if trade was placed
#     if place_trade_put:
#         exit_prices['put_next'] = get_mark_price(put_next_symbol)
#         exit_prices['put_prev'] = get_mark_price(put_prev_symbol)
#         exit_prices['put_sell'] = get_mark_price(put_symbol)
#
#         pnl_tracker['put_next'] = 1 * (exit_prices['put_next'] - entry_prices['put_next'])
#         pnl_tracker['put_prev'] = 2 * (exit_prices['put_prev'] - entry_prices['put_prev'])
#         pnl_tracker['put_sell'] = 3 * (entry_prices['put_sell'] - exit_prices['put_sell'])
#
#     for k, v in exit_prices.items():
#         print(f"📉 Exit {k}: {v:.2f}")
#
#     for k, v in pnl_tracker.items():
#         print(f"💹 {k} PnL: {v:.2f}")
#
#     total_pnl = sum(pnl_tracker.values())
#     print(f"\n💰 Total Dummy PnL: ₹{total_pnl:.2f}\n")
#
#
# # --- Schedule ---
# schedule.every().day.at("20:03").do(place_initial_orders)
# schedule.every().day.at("20:05").do(square_off_orders)
#
# print("⏳ Scheduler started for forward testing (dummy mode)...")
#
# while True:
#     schedule.run_pending()
#     time.sleep(10)

# %%


# %%
# call_product          = delta_client.get_product(call_symbol)
# call_next_product     = delta_client.get_product(call_next_symbol)
# call_prev_product     = delta_client.get_product(call_prev_symbol)
# put_product           = delta_client.get_product(put_symbol)
# put_next_product      = delta_client.get_product(put_next_symbol)
# put_prev_product      = delta_client.get_product(put_prev_symbol)


# import schedule
# import time
# from datetime import datetime, timedelta
# import pytz

# IST = pytz.timezone('Asia/Kolkata')

# # --- Your order placing logic (copy your existing code here) ---
# def place_initial_orders():
#     print(f"[{datetime.now(IST)}] Placing initial strategy orders...")

#     delta_client.place_order({
#         "product_id": call_next_product['id'],
#         "size": 1,
#         "side": "buy",
#         "order_type": "market"
#     })
#     delta_client.place_order({
#         "product_id": call_prev_product['id'],
#         "size": 1,
#         "side": "buy",
#         "order_type": "market"
#     })
#     delta_client.place_order({
#         "product_id": put_next_product['id'],
#         "size": 1,
#         "side": "buy",
#         "order_type": "market"
#     })
#     delta_client.place_order({
#         "product_id": put_prev_product['id'],
#         "size": 1,
#         "side": "buy",
#         "order_type": "market"
#     })
#     delta_client.place_order({
#         "product_id": call_product['id'],
#         "size": 1,
#         "side": "sell",
#         "order_type": "market"
#     })
#     delta_client.place_order({
#         "product_id": put_product['id'],
#         "size": 1,
#         "side": "sell",
#         "order_type": "market"
#     })

# def square_off_orders():
#     print(f"[{datetime.now(IST)}] Squaring off all positions...")

#     delta_client.place_order({
#         "product_id": call_product['id'],
#         "size": 1,
#         "side": "buy",
#         "order_type": "market"
#     })
#     delta_client.place_order({
#         "product_id": put_product['id'],
#         "size": 1,
#         "side": "buy",
#         "order_type": "market"
#     })


#     delta_client.place_order({
#         "product_id": call_next_product['id'],
#         "size": 1,
#         "side": "sell",
#         "order_type": "market"
#     })
#     delta_client.place_order({
#         "product_id": call_prev_product['id'],
#         "size": 1,
#         "side": "sell",
#         "order_type": "market"
#     })
#     delta_client.place_order({
#         "product_id": put_next_product['id'],
#         "size": 1,
#         "side": "sell",
#         "order_type": "market"
#     })
#     delta_client.place_order({
#         "product_id": put_prev_product['id'],
#         "size": 1,
#         "side": "sell",
#         "order_type": "market"
#     })


# # --- Schedule tasks ---
# schedule.every().day.at("17:45").do(place_initial_orders)
# schedule.every().day.at("14:00").do(square_off_orders)

# print("⏳ Scheduler started...")

# while True:
#     schedule.run_pending()
#     time.sleep(10)
