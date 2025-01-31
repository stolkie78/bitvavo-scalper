from datetime import datetime
import pandas as pd
from ta.momentum import RSIIndicator
import json
import time

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
    def place_order(bitvavo, pair, side, quantity, use_amountQuote=False, demo_mode=False):
        """
        Plaatst een market order en logt de API-aanroep voor debugging.

        Args:
            bitvavo (Bitvavo): Geïnitialiseerde Bitvavo API-client.
            pair (str): Trading pair, bv. "ETH-EUR".
            side (str): "buy" of "sell".
            quantity (float): De hoeveelheid die gekocht of verkocht wordt.
            use_amountQuote (bool): Gebruik amountQuote voor buy orders (standaard: False).
            demo_mode (bool): Simuleer de order in demo-modus (standaard: False).

        Returns:
            dict: Respons van de Bitvavo API of een gesimuleerde order.
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
            # ✅ Correcte API parameters
            order_params = {
                "market": pair,
                "side": side,
                "orderType": "market",
            }

            if side == "buy":
                if use_amountQuote:
                    order_params["amountQuote"] = str(
                        quantity)  # ✅ Koop X EUR aan ADA
                else:
                    order_params["amount"] = str(quantity)  # ✅ Koop X ADA
            else:
                order_params["amount"] = str(quantity)  # ✅ Verkoop X ADA

            # 🔍 **Debug Log**: Controleer de API-aanroep
            print(f"📡 Sending order to Bitvavo: {
                json.dumps(order_params, indent=2)}")

            # ✅ Bitvavo API-aanroep
            order_response = bitvavo.placeOrder(pair, side, "market", order_params)

            # 🔍 **Debug Log**: Log de API-response
            print(f"🔍 Order Response: {json.dumps(order_response, indent=4)}")

            # ✅ Controleer of de order succesvol is
            if "orderId" in order_response and "fills" in order_response and order_response["fills"]:
                actual_price = float(order_response["fills"][0]["price"])
                fee_paid = float(order_response["fills"][0]["fee"])
                quantity_filled = sum(float(fill["amount"])
                                    for fill in order_response["fills"])

                return {
                    "status": "filled",
                    "orderId": order_response["orderId"],
                    "pair": pair,
                    "side": side,
                    "quantity": quantity_filled,  # ✅ Werkelijk gevulde hoeveelheid
                    "actual_price": actual_price,
                    "fee_paid": fee_paid
                }
            else:
                print(f"⚠️ Order {order_response.get(
                    'orderId', 'UNKNOWN')} did not get filled! Possible reasons:")
                print(f"   - Insufficient liquidity?")
                print(f"   - Incorrect amount format?")
                print(f"   - Minimum trade size not met?")
                return {"status": "failed", "error": "No fills received", "pair": pair, "response": order_response}

        except Exception as e:
            print(f"⚠️ Error placing order: {e}")
            return {"status": "error", "error": str(e), "pair": pair}

    @staticmethod
    def get_order_details(bitvavo, pair, action, max_retries=3, delay=2):
        """
        Fetches the most recent filled order details for the given pair and action, 
        with retries if no data is found.

        Args:
            bitvavo: Bitvavo API client
            pair (str): Trading pair (e.g., "BTC-EUR")
            action (str): "buy" or "sell"
            max_retries (int): Number of retries before giving up (default: 3)
            delay (int): Delay (in seconds) between retries (default: 2)

        Returns:
            dict: The order details, or None if not found.
        """
        attempt = 0

        while attempt < max_retries:
            try:
                print(f"📡 Fetching last {action} order for {pair} from Bitvavo (Attempt {attempt + 1}/{max_retries})...")

                # ✅ Haal de laatste 5 orders op, filter op 'buy' of 'sell'
                orders = bitvavo.getOrders({
                    "market": pair,
                    "limit": 5,
                    "side": action,
                })

                # 🔍 **Debug Log**: Controleer de API-respons
                print(f"🔍 Order Data Received: {json.dumps(orders, indent=4)}")

                # ✅ Controleer of er orders zijn ontvangen
                if orders and isinstance(orders, list):
                    for order in orders:
                        if order.get("status") == "filled":  # Alleen succesvolle orders
                            print(f"✅ Found filled order: {json.dumps(order, indent=4)}")
                            return order  # Retourneer de eerste succesvolle order

                print(f"⚠️ No filled {action} orders found for {pair}. Retrying in {delay} seconds...")
                time.sleep(delay)  # Wacht even en probeer opnieuw
                attempt += 1

            except Exception as e:
                print(f"⚠️ Error fetching order details (Attempt {attempt + 1}): {e}")
                time.sleep(delay)  # Wacht even voordat je opnieuw probeert
                attempt += 1

        print(f"❌ No filled {action} orders found for {pair} after {max_retries} attempts.")
        return None  # Geef None terug als er na max_retries nog steeds geen order is