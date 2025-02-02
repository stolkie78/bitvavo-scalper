import json
import os
import asyncio
from datetime import datetime
from bot.trading_utils import TradingUtils
import threading


class StateManager:
    _lock = threading.Lock()  # Lock om race conditions te voorkomen

    def __init__(self, pair, logger, bitvavo, demo_mode=False):
        self.pair = pair
        self.logger = logger
        self.bitvavo = bitvavo
        self.demo_mode = demo_mode
        self.position = None  # Zorgt ervoor dat er maar 1 positie per crypto is
        self.data_dir = "data"
        self.portfolio_file = os.path.join(self.data_dir, "portfolio.json")
        self.trades_file = os.path.join(self.data_dir, "trades.json")
        self.portfolio = self.load_portfolio()

        # Zorg dat de map bestaat
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        # Herstel positie als die bestaat
        if self.pair in self.portfolio:
            self.position = self.portfolio[self.pair]

    def has_position(self):
        """Controleer of een positie bestaat voor het paar."""
        self.portfolio = self.load_portfolio()  # ✅ Altijd een up-to-date portfolio ophalen
        return self.pair in self.portfolio and self.portfolio[self.pair] is not None

    def load_portfolio(self):
        """Laad de portefeuille-inhoud uit een JSON-bestand."""
        if os.path.exists(self.portfolio_file) and os.path.getsize(self.portfolio_file) > 0:
            try:
                with open(self.portfolio_file, "r") as f:
                    self.portfolio = json.load(f)
                self.position = self.portfolio.get(self.pair, None)
                return self.portfolio
            except (json.JSONDecodeError, IOError):
                self.logger.log(
                    "👽❗ Error loading portfolio.json, resetting file.", to_console=True)
                return {}  # Reset bij fout
        return {}  # Lege return als bestand niet bestaat

    def save_portfolio(self):
        """Sla de portefeuille-inhoud op naar een JSON-bestand."""
        with self._lock:
            try:
                with open(self.portfolio_file, "w") as f:
                    json.dump(self.portfolio, f, indent=4)
                self.portfolio = self.load_portfolio()
                self.logger.log(f"👽 Portfolio successfully updated: {
                                json.dumps(self.portfolio, indent=4)}", to_console=True)
            except Exception as e:
                self.logger.log(f"👽❌ Error saving portfolio: {
                                e}", to_console=True)

    async def buy(self, budget, fee_percentage):
        """Voer een kooporder uit via WebSocket."""
        if self.has_position():
            self.logger.log(f"👽❌ Cannot open a new position for {
                            self.pair}. Position already exists.", to_console=True)
            return

        # ✅ Haal de live prijs op via WebSockets
        price = await TradingUtils.fetch_current_price(self.bitvavo, self.pair)
        quantity = (budget / price) * (1 - fee_percentage / 100)

        if quantity <= 0:
            self.logger.log(f"👽❌ Invalid quantity for {self.pair}: {
                            quantity}", to_console=True)
            return

        # ✅ Plaats order via WebSockets
        order = await TradingUtils.place_order(self.bitvavo, self.pair, "buy", quantity, demo_mode=self.demo_mode)

        if order.get("status") == "filled":
            real_price = order["actual_price"]
            real_quantity = order["quantity"]
            buy_fee = order["fee_paid"]

            # ✅ Opslaan van de nieuwe positie
            new_position = {
                "price": real_price,
                "quantity": real_quantity,
                "timestamp": datetime.now().isoformat()
            }
            self.portfolio[self.pair] = new_position
            self.save_portfolio()

            self.log_trade("buy", real_price, real_quantity, fee=buy_fee)
            self.logger.log(f"👽 Bought {self.pair}: Price={real_price:.2f}, Quantity={
                            real_quantity:.6f}, Fee={buy_fee:.2f}", to_console=True)
        else:
            self.logger.log(f"👽 Failed to execute buy order for {
                            self.pair}: {order}", to_console=True)

    async def sell(self, fee_percentage):
        """Voer een verkooporder uit via WebSockets."""
        if not self.has_position():
            self.logger.log(f"👽 No position to sell for {
                            self.pair}.", to_console=True)
            return

        if self.position is None:
            self.logger.log(f"👽❌ Sell failed: No valid position found for {
                            self.pair}.", to_console=True)
            return

        # ✅ Live prijs ophalen via WebSockets
        price = await TradingUtils.fetch_current_price(self.bitvavo, self.pair)
        quantity = self.position.get("quantity", 0)

        if quantity <= 0:
            self.logger.log(f"👽 Invalid quantity for {self.pair}: {
                            quantity}", to_console=True)
            return

        cost_basis = self.position["price"] * quantity
        revenue = price * quantity * (1 - fee_percentage / 100)
        profit = revenue - cost_basis

        # ✅ Plaats verkooporder via WebSockets
        order = await TradingUtils.place_order(self.bitvavo, self.pair, "sell", quantity, demo_mode=self.demo_mode)

        if order.get("status") == "filled":
            real_price = order["actual_price"]
            real_quantity = order["quantity"]
            sell_fee = order["fee_paid"]

            self.log_trade("sell", real_price, real_quantity,
                           profit, fee=sell_fee)

            if self.pair in self.portfolio:
                del self.portfolio[self.pair]  # ✅ Verwijder uit portefeuille
                self.save_portfolio()  # ✅ Sla wijzigingen op

            self.logger.log(f"👽 Sold {self.pair}: Price={real_price:.2f}, Profit={
                            profit:.2f}, Fee={sell_fee:.2f}", to_console=True)
        else:
            self.logger.log(f"👽 Failed to execute sell order for {
                            self.pair}: {order}", to_console=True)

    async def calculate_profit(self, fee_percentage):
        """Bereken de winst of verlies voor de huidige positie."""
        if not self.has_position():
            self.logger.log(f"⚠️ No active position for {
                            self.pair}. Skipping profit calculation.", to_console=True)
            return None

        price = await TradingUtils.fetch_current_price(self.bitvavo, self.pair)
        quantity = self.position["quantity"]
        cost_basis = self.position["price"] * quantity
        revenue = price * quantity * (1 - fee_percentage / 100)
        profit = revenue - cost_basis

        return (profit / cost_basis) * 100  # Winst in percentage

    def log_trade(self, trade_type, price, quantity, profit=None, fee=None):
        """Log trades naar een JSON-bestand."""
        trade = {
            "pair": self.pair,
            "type": trade_type,
            "price": price,
            "quantity": quantity,
            "profit": profit,
            "fee": fee,
            "timestamp": datetime.now().isoformat()
        }
        try:
            if not os.path.exists(self.trades_file):
                with open(self.trades_file, "w") as f:
                    json.dump([trade], f, indent=4)
            else:
                with open(self.trades_file, "r") as f:
                    trades = json.load(f)
                trades.append(trade)
                with open(self.trades_file, "w") as f:
                    json.dump(trades, f, indent=4)
        except Exception as e:
            self.logger.log(f"👽❗ Error logging trade: {e}", to_console=True)
