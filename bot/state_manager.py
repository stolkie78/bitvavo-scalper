
import datetime
from bot.trading_utils import TradingUtils

class StateManager:
    def __init__(self, pair, logger, trading_utils):
        self.pair = pair
        self.logger = logger
        self.trading_utils = trading_utils
        self.position = None

    def buy(self, price, budget, trade_fee_percentage):
        try:
            quantity = (budget / price) * (1 - trade_fee_percentage / 100)
            response = self.trading_utils.place_order(
                market=self.pair, side="buy", amount=quantity
            )
            self.position = {"price": price, "quantity": quantity, "timestamp": datetime.datetime.now().isoformat()}
            self.logger.log(f"🟢 Bought {self.pair}: Price={price}, Quantity={quantity}", to_console=True, to_slack=True)
        except Exception as e:
            self.logger.log(f"❌ Failed to place buy order for {self.pair}: {e}", to_console=True, to_slack=True)

    def sell(self, price, trade_fee_percentage):
        try:
            quantity = self.position["quantity"]
            response = self.trading_utils.place_order(
                market=self.pair, side="sell", amount=quantity
            )
            profit = (price - self.position["price"]) * quantity * (1 - trade_fee_percentage / 100)
            self.position = None
            self.logger.log(f"🔴 Sold {self.pair}: Price={price}, Profit={profit:.2f}", to_console=True, to_slack=True)
        except Exception as e:
            self.logger.log(f"❌ Failed to place sell order for {self.pair}: {e}", to_console=True, to_slack=True)

    def has_position(self):
        return self.position is not None
