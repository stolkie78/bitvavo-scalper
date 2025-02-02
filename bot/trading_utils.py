from datetime import datetime
import pandas as pd
import asyncio
from ta.momentum import RSIIndicator


class TradingUtils:
    @staticmethod
    async def fetch_current_price(bitvavo, pair):
        """
        Fetches the current price of a trading pair using Bitvavo WebSockets.
        """
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        def callback(response):
            """Callback om live prijsdata te verwerken."""
            if isinstance(response, dict) and "market" in response and "price" in response:
                future.set_result(float(response["price"]))
            else:
                future.set_exception(ValueError(
                    f"Unexpected response format: {response}"))

        # ✅ Abonneer op live prijsupdates via WebSocket
        bitvavo.subscriptionTicker(pair, callback)

        try:
            return await future  # Wacht op de WebSocket-reactie
        except Exception as e:
            raise RuntimeError(
                f"❌ Error fetching current price for {pair}: {e}")

    @staticmethod
    def calculate_rsi(price_history, window_size):
        """
        Calculates the RSI based on the price history.
        """
        if len(price_history) < window_size:
            return None
        rsi_indicator = RSIIndicator(
            pd.Series(price_history), window=window_size)
        return rsi_indicator.rsi().iloc[-1]

    @staticmethod
    async def place_order(bitvavo, market, side, amount, demo_mode=False):
        """
        Places a buy or sell order via Bitvavo WebSockets or simulates it in demo mode.

        Args:
            bitvavo (Bitvavo): The initialized Bitvavo WebSocket client.
            market (str): Trading pair, e.g., "BTC-EUR".
            side (str): "buy" or "sell".
            amount (float): The amount to buy or sell.
            demo_mode (bool): Whether to simulate the order (default: False).

        Returns:
            dict: Response from the Bitvavo WebSocket API or a simulated order.
        """
        if demo_mode:
            return {
                "status": "demo",
                "side": side,
                "market": market,
                "amount": amount,
                "order_type": "market",
                "timestamp": datetime.now().isoformat()
            }

        loop = asyncio.get_event_loop()
        future = loop.create_future()

        def callback(response):
            """Callback om orderresponse te verwerken."""
            if isinstance(response, dict) and "orderId" in response:
                future.set_result(response)
            else:
                future.set_exception(ValueError(
                    f"❌ Unexpected order response: {response}"))

        order_params = {
            "market": market,
            "side": side,
            "orderType": "market",
            "amount": str(amount)
        }

        # ✅ Plaats een order via WebSocket
        bitvavo.subscriptionPlaceOrder(order_params, callback)

        try:
            return await future  # Wacht op de WebSocket-reactie
        except Exception as e:
            raise RuntimeError(f"❌ Error placing {side} order for {market}: {e}")
