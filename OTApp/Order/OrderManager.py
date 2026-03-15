import math
from typing import Any

import requests

from OTApp.Configuration import DeltaExchangeConfiguration
from OTApp.Logger.Logger import AppLogger
from OTApp.Security.APIRequestSecurityManager import APIRequestSecurityManager


class OrderManager:
    """
    Scenario	                    Endpoint	            Method	    Order ID	        Use Case
    1. New order + bracket	        /v2/orders	            POST	    Not needed	        Place order with SL/TP from start
    2. Add bracket to order	        /v2/orders/bracket	    PUT	        Required	        Add/modify SL/TP on existing order
    3. Bracket for position	        /v2/orders/bracket	    POST	    Not used	        Add SL/TP to existing position
    4. Edit order basics	        /v2/orders	            PUT     	Required	        Change price/size (not bracket)

    Use Scenario 1 (POST /v2/orders with bracket params):
        You want SL/TP attached immediately when placing the order
        One API call, simpler

    """
    _logger_ = AppLogger().get_log()

    def __init__(self, logger):
        self._logger_ = logger
        # self._ws_pub_ = ws_pub
        # self._ws_private_ = ws_private
        # self.orders = {}

    def place_orders(self, trade_record):
        # Create new order along with bracket or plan
        new_order_path = DeltaExchangeConfiguration.API_VERSION() + '/orders'
        # Create a bracket order for an existing open position using the
        update_bracket_path = DeltaExchangeConfiguration.API_VERSION() + '/orders/bracket'

        req_method = 'POST'
        # 1. Determine which legs to execute
        legs = self.find_legs(trade_record)
        if not legs:
            self._logger_.error("❌ EXECUTION ABORTED | No valid legs found in trade_record.")
            return []
        req_query_string = ''  # Empty for this request
        # preparing the request body and placing order at time
        executed_orders = []
        try:
            for leg in legs:
                symbol = leg.get('symbol', 'Unknown')
                # 2. Prepare the specific order dictionary (including SL and Trigger Method)
                # Use Scenario 1 (POST /v2/orders with bracket params):
                order_payload = self.prepare_order(leg, trade_record)
                # 3. Regenerate signature/timestamp for each request (best practice for high frequency)
                signature, timestamp = APIRequestSecurityManager().build_payload_signature(new_order_path, req_method,
                                                                                           req_query_string,
                                                                                           order_payload)
                # 4. Set Headers
                headers = {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'api-key': DeltaExchangeConfiguration.API_KEY(),
                    'signature': signature,
                    'timestamp': timestamp
                }
                try:
                    self._logger_.info(
                        f"🚀 SENDING ORDER | {symbol} | Qty: {order_payload.get('size')} | Type: {order_payload.get('order_type')}...")
                    # 4. Make the Request - Passing the order_payload as JSON
                    place_order_response = requests.post(
                        f"{DeltaExchangeConfiguration.BASE_URL()}{new_order_path}",
                        json=order_payload,
                        headers=headers,
                        timeout=(3, 27)
                    )
                    place_order_response_data = place_order_response.json()

                    if place_order_response.status_code in [200, 201]:
                        response_data = place_order_response_data['result']
                        self._logger_.info(
                            f"✅ ORDER ACCEPTED | ID: {response_data['id']} | {response_data['product_symbol']} \n"
                            f"📍 Type: {response_data['stop_order_type']} | State: {response_data['state'].upper()} \n"
                            f"💰 Stop Price: {response_data['stop_price']} | Trigger: {response_data['stop_trigger_method']}"
                        )
                        executed_orders.append(
                            {"status": "SUCCESS", "payload": order_payload, "response": place_order_response_data})
                    else:
                        self._logger_.error(
                            f"⚠️  ORDER REJECTED | {symbol} | Reason: {place_order_response_data.get('error').get('code', 'Unknown Error')} 🛑")
                        executed_orders.append(
                            {"status": "REJECTED", "payload": order_payload, "response": place_order_response_data})
                except Exception as e:
                    self._logger_.error(f"🚨 NETWORK ERROR | {symbol} | Failed to reach Delta Exchange: {str(e)}")
                    executed_orders.append({"status": "NETWORK_FAILURE", "payload": order_payload, "error": str(e)})
        except Exception as e:
            self._logger_.error(f"Error while placing trade_record {trade_record}")
        return executed_orders

    def prepare_order(self, leg, trade_record) -> dict[str, str | Any]:
        # trigger based on Stop order trigger others are  mark_price/last_traded_price/spot_price
        # we need to pass swings value or ob for sl according to put or call
        # reduce_only set to true to close the existing one not fork new

        """
        Summary Table for Your Strangle
            Leg,                Action,         stop_trigger_method,                stop_price Logic
            Short Call,     Buy to Close,           spot_price,                     Trigger when Spot > Resistance
            Short Put,      Buy to Close,           spot_price,                     Trigger when Spot < Support

            :param leg:
            :param trade_record: ob=market_check['order_block']
            :return:
        """
        order_block = trade_record.get('market_check').get('order_block')
        swings_with_sweep = trade_record.get('market_check').get('order_block')
        leg_sl = 0.0
        # Initialize default state
        stop_trigger_method = "spot_price"
        leg_symbol = leg.get('symbol', 'Unknown')
        leg_contract_type = leg['contract_type']
        sl_by_ob = self.sl_by_ob(leg, order_block)
        sl_by_swings = self.sl_by_swings(leg, swings_with_sweep)
        # 1. Determine the tightest structural Stop Loss (Closest to current price)
        if sl_by_ob > 0 and sl_by_swings > 0:
            # Both present: Pick the one that triggers EARLIER to minimize risk
            if leg_contract_type == 'put_options':
                leg_sl = max(sl_by_ob, sl_by_swings)  # For Puts, higher price is closer
            else:
                leg_sl = min(sl_by_ob, sl_by_swings)  # For Calls, lower price is closer
            self._logger_.info(f"🎯 TIGHTEST STRUCTURAL SL | {leg_symbol} | Level: {leg_sl} | Method: SPOT 📍")
        elif sl_by_ob > 0 or sl_by_swings > 0:
            # Only one structural SL is available
            leg_sl = sl_by_ob if sl_by_ob > 0 else sl_by_swings
            self._logger_.info(f"🛡️  SINGLE ANCHOR SL | {leg_symbol} | Level: {leg_sl} | Method: SPOT 📍")
        # final stop loss would be which is closer to avoid bigger loss
        else:
            # 2. FALLBACK: No OB or Swings found. Use Monetary Max Loss (Mark Price)
            # in case ob and swings not present then i have to bear max loss in whole strangle is max_trade_sl
            stop_trigger_method = "mark_price"
            max_trade_sl = trade_record['trade']['max_trade_sl']
            max_sell_lots = trade_record['trade']['max_sell_lots']
            leg_sl_points = trade_record['trade']['leg_sl_points']
            # SL based on the premium price of the option itself
            leg_sl = float(leg['mark_price']) + leg_sl_points
            self._logger_.warning(
                f"🧨 MONETARY STOP LOSS | {leg_symbol} | "
                f"No Structure Found! Max Loss Trigger: {leg_sl:.2f} | Method: MARK 💸"
            )
        #  we should convert .005 to 5 as lots
        sell_lots = int(trade_record['trade']['sell_lots'] * 1000)
        return {
            "product_id": leg['product_id'],
            "product_symbol": leg['symbol'],
            "size": sell_lots,
            "side": "sell",
            "order_type": "limit_order",
            "limit_price": float(leg['quotes']['best_bid']),
            "time_in_force": "gtc",
            # "stop_loss_order": {"stop_price": self.round_to_tick(leg_sl, float(leg['tick_size'])),
            #                     "order_type": "market_order"
            #                     }
            "bracket_stop_trigger_method": stop_trigger_method,
            'bracket_stop_loss_price': self.round_to_tick(leg_sl, float(leg['tick_size'])),
            "client_order_id": "15_Delta_" + leg_contract_type,  # <--- YOUR TRACKING ID
            "post_only": False,
            "reduce_only": False
        }

    def sl_by_ob(self, leg, order_block) -> float:
        """
        Calculates the Stop Loss price based on the Spot Price hitting the Order Block boundary.
        """
        sl_price = 0.0
        symbol = leg.get('symbol', 'Unknown')
        contract_type = leg['contract_type']
        strike = float(leg['strike_price'])
        if order_block:
            ob_type = order_block['type']
            # PUT PROTECTION: OB bottom acts as the floor (Support)
            if contract_type == 'put_options' and ob_type == 'BULLISH':
                ob_bottom = float(order_block['bottom'])
                if ob_bottom >= strike:
                    sl_price = float(order_block['bottom'])
            # CALL PROTECTION: OB top acts as the ceiling (Resistance)
            elif contract_type == 'call_options' and ob_type == 'BEARISH':
                ob_top = float(order_block['top'])
                if ob_top <= strike:
                    sl_price = float(order_block['top'])
        # Logging based on result
        if sl_price > 0:
            self._logger_.info(
                f"🛡️  SL ANCHORED | Leg: {symbol} | "
                f"OB {order_block['type']} Level: {sl_price} 🧱 | "
                f"Trigger: Spot Price reaching OB boundary ✅"
            )
        else:
            self._logger_.warning(
                f"⚠️  SL UNPROTECTED | Leg: {symbol} | "
                f"Reason: No valid {contract_type} OB found for Strike {strike} | "
                f"Action: Reverting to default risk params 🔄"
            )
        return sl_price

    def find_legs(self, trade_record):
        """
        Determines the final execution legs based on the price-matching analysis.
        """
        # Use .get() to avoid KeyError if the analysis failed mid-way
        leg_handle_resp = trade_record.get('un_matched_leg_handle_resp')
        initial_legs = trade_record.get('initial_legs')

        # Path 1: No adjustment response found - Fallback to Initial
        if not leg_handle_resp:
            self._logger_.info("ℹ️  No adjustment response found. Using Initial Legs. 📍")
            return initial_legs

        # Path 2: Adjustment logic returned specific 'final_legs'
        final_legs = leg_handle_resp.get('final_legs')
        if final_legs:
            self._logger_.info(
                f"⚖️  Using PRICE-MATCHED Legs | "
                f"Original legs were adjusted for balance. ✅"
            )
            return final_legs

        # Path 3: Adjustment logic ran but found no better alternative
        self._logger_.info("⚠️  Adjustment logic returned empty. Reverting to Initial Legs. 🔄")
        return initial_legs

    def sl_by_swings(self, leg, swings_with_sweep):
        sl_price = 0.0
        symbol = leg.get('symbol', 'Unknown')
        contract_type = leg['contract_type']
        strike = float(leg['strike_price'])
        if swings_with_sweep:
            sh_low = float(swings_with_sweep['swing_low'])
            if contract_type == 'put_options' and strike <= sh_low:
                sl_price = sh_low
            elif contract_type == 'call_options':
                sh_high = float(swings_with_sweep['swing_high'])
                if strike >= sh_high:
                    sl_price = sh_high
        return sl_price

    def round_to_tick(self, price, tick_size):
        """
        Rounds a price to the nearest valid tick size.
        Example: price=101.1274, tick_size=0.1 -> 101.1
        """
        if not tick_size or tick_size <= 0:
            return round(price, 2)  # Fallback
        return round(math.floor(price / tick_size) * tick_size, 8)

    def nigrani_orders(self, strategy_name, orders):
        self.orders.update({strategy_name: orders})
