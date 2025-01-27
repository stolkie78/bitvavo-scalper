import logging
import pandas as pd
from ta.momentum import RSIIndicator


class TradingUtils:
    def __init__(self, bitvavo, logger):
        self.bitvavo = bitvavo
        self.logger = logger

    def fetch_current_price(self, market):
        """Fetches the current price for a specific market."""
        try:
            response = self.bitvavo.tickerPrice({"market": market})
            return float(response["price"])
        except Exception as e:
            self.logger.error(
                f"Failed to fetch current price for {market}: {e}")
            raise

    def calculate_rsi(price_history, window_size):
        """Calculates the RSI based on the price history."""
        if len(price_history) < window_size:
            return None
        rsi_indicator = RSIIndicator(
            pd.Series(price_history), window=window_size)
        return rsi_indicator.rsi().iloc[-1]

    def place_order(self, market, side, amount):
        """Places a market order."""
        try:
            order = self.bitvavo.placeOrder(market, side, "market", {"amount": f"{amount:.8f}"})
            self.logger.info(f"✅ Order placed: {order}")
            return order
        except Exception as e:
            self.logger.error(f"❌ Failed to place order for {market} ({side}): {e}")
            raise
