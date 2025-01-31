from datetime import datetime
import pandas as pd
from ta.momentum import RSIIndicator
import json

class TradingUtils:
    @staticmethod
    def fetch_current_price(bitvavo, pair):
        """Fetches the current price of a trading pair using the Bitvavo API."""
        try:
            ticker = bitvavo.tickerPrice({"market": pair})
            if "price" in ticker:
                return float(ticker["price"])
            else:
                raise ValueError(f"Unexpected response format: {ticker}")
        except Exception as e:
            raise RuntimeError(f"Error fetching current price for {pair}: {e}")

    @staticmethod
    def calculate_rsi(price_history, window_size):
        """Calculates the RSI based on the price history."""
        if len(price_history) < window_size:
            return None
        rsi_indicator = RSIIndicator(pd.Series(price_history), window=window_size)
        return rsi_indicator.rsi().iloc[-1]


    @staticmethod
    def place_order(bitvavo, pair, side, quantity, demo_mode=False):
        """
        Plaats een market order en log de API-aanroep voor debugging.
        """
        if demo_mode:
            return {
                "status": "demo",
                "pair": pair,
                "side": side,
                "quantity": quantity,
                "fills": [{"price": "0.0", "amount": str(quantity), "fee": "0.0"}]
            }
    
        try:
            # ✅ Correcte API parameters gebruiken
            order_params = {
                "market": pair,
                "side": side,
                "orderType": "market",
            }
    
            if side == "buy":
                order_params["amount"] = str(quantity)  # ✅ Bitvavo verwacht 'amount' voor een market buy
            else:
                order_params["size"] = str(quantity)  # ✅ Bitvavo verwacht 'size' voor een market sell
    
            # 🔍 **Debug Log**: Controleer welke parameters worden doorgestuurd naar Bitvavo
            print(f"📡 Sending order to Bitvavo: {json.dumps(order_params, indent=2)}")
    
            order_response = bitvavo.placeOrder(**order_params)
    
            # ✅ Controleer of de order succesvol is
            if "orderId" in order_response and "fills" in order_response and order_response["fills"]:
                actual_price = float(order_response["fills"][0]["price"])
                fee_paid = float(order_response["fills"][0]["fee"])
    
                return {
                    "status": "filled",
                    "orderId": order_response["orderId"],
                    "pair": pair,
                    "side": side,
                    "quantity": quantity,
                    "actual_price": actual_price,
                    "fee_paid": fee_paid
                }
            else:
                return {"status": "failed", "error": "No fills received", "pair": pair}
    
        except Exception as e:
            return {"status": "error", "error": str(e), "pair": pair}


    @staticmethod
    def get_order_details(bitvavo, pair, action):
        """
        Fetches the most recent order details for the given pair and action.

        Args:
            bitvavo: Bitvavo API client
            pair (str): Trading pair (e.g., "BTC-EUR")
            action (str): "buy" or "sell"

        Returns:
            dict: The order details, or None if not found.
        """
        try:
            orders = bitvavo.getOrders({'market': pair, 'limit': 1})  # Fetch last order
            if orders and isinstance(orders, list) and len(orders) > 0:
                last_order = orders[0]
                if last_order["side"] == action:
                    return last_order
            return None
        except Exception as e:
            print(f"⚠️ Error fetching order details: {e}")
            return None