import json
from datetime import datetime
import os
from bot.trading_utils import TradingUtils
import threading


class StateManager:
    _lock = threading.Lock()  # Lock om race conditions te voorkomen

    def __init__(self, pair, logger, bitvavo, demo_mode=False, bot_name=None):
        self.pair = pair
        self.logger = logger
        self.bitvavo = bitvavo
        self.bot_name = bot_name
        self.demo_mode = demo_mode
        self.position = None  # Ensure only one position per crypto
        self.data_dir = "data"
        self.portfolio_file = os.path.join(self.data_dir, "portfolio.json")
        self.trades_file = os.path.join(self.data_dir, "trades.json")
        self.portfolio = self.load_portfolio()

        # Ensure the data directory exists
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        # Restore position if it exists in the portfolio
        if self.pair in self.portfolio:
            self.position = self.portfolio[self.pair]


    def has_position(self):
        """Check if a position exists for the pair using the latest portfolio state."""
        self.portfolio = self.load_portfolio()  # ✅ Always load fresh portfolio
        has_position = self.pair in self.portfolio and self.portfolio[self.pair] is not None

        # 🔍 Debugging Log
        #self.logger.log(
        #    f"👽 Checking position for {self.pair}: {'YES' if has_position else 'NO'} "
        #    f"| Current portfolio: {json.dumps(self.portfolio, indent=4)}",
        #    to_console=True
        #)
        return has_position


    def load_portfolio(self):
        """Load the entire portfolio content from a JSON file."""
        if os.path.exists(self.portfolio_file) and os.path.getsize(self.portfolio_file) > 0:
            try:
                with open(self.portfolio_file, "r") as f:
                    # ✅ Assign directly to self.portfolio
                    self.portfolio = json.load(f)

                self.position = self.portfolio.get(
                    self.pair, None)  # ✅ Restore existing positions

                return self.portfolio  # ✅ Ensure this function always returns the correct portfolio
            except (json.JSONDecodeError, IOError):
                self.logger.log(
                    f"👽❗ Error loading portfolio.json, resetting file.", to_console=True)
                return {}  # Reset if corrupted
        return {}  # Return empty if file does not exist or is empty


    def save_portfolio(self):
        """Save the portfolio content to a JSON file without keeping old removed positions."""
        with self._lock:  # Prevent race conditions
            try:
                with open(self.portfolio_file, "w") as f:
                    # ✅ Overwrite with updated data
                    json.dump(self.portfolio, f, indent=4)

                # ✅ Reload the portfolio to confirm changes
                self.portfolio = self.load_portfolio()
                self.logger.log(
                    f"[{self.bot_name}] 👽 Portfolio successfully updated: {json.dumps(self.portfolio, indent=4)}", to_console=True)

            except Exception as e:
                self.logger.log(f"[{self.bot_name}] 👽❌ Error saving portfolio: {
                                e}", to_console=True)

    def adjust_quantity(self, pair, quantity):
        """Adjust the quantity to meet market requirements."""
        market_info = self.bitvavo.markets()
        for market in market_info:
            if market['market'] == pair:
                min_amount = float(market.get('minOrderInBaseAsset', 0.0))
                precision = int(market.get('decimalPlacesBaseAsset', 6))
                adjusted_quantity = max(min_amount, round(quantity, precision))
                return adjusted_quantity
        self.logger.log(f"[{self.bot_name}] ⚠️ Market info not found for {
                        pair}. Returning original quantity.", to_console=True)
        return quantity


    def buy(self, budget, fee_percentage):
        """Execute a buy order if no position exists for the pair."""
        if self.has_position():
            self.logger.log(
                f"[{self.bot_name}] 👽❌ Cannot open a new position for {self.pair}. Position already exists.", to_console=True)
            return

        # 🔹 Plaats kooporder en haal de daadwerkelijke koopprijs en fee op
        order = TradingUtils.place_order(
            self.bitvavo, self.pair, "buy", budget, demo_mode=self.demo_mode)

        if order.get("status") == "filled":  # ✅ Controleer of de order volledig is uitgevoerd
            # ✅ Werkelijke koopprijs per eenheid
            real_buy_price = order["actual_price"]
            buy_fee = order["fee_paid"]  # ✅ Werkelijke fee
            quantity = order["quantity_bought"]  # ✅ Hoeveelheid gekocht na fee

            if quantity <= 0:
                self.logger.log(
                    f"[{self.bot_name}] 👽❌ Invalid quantity for {self.pair} after fees: {quantity}", to_console=True, to_slack=False)
                return

            # ✅ Opslaan van de nieuwe positie in de portfolio
            new_position = {
                "price": real_buy_price,
                "quantity": quantity,
                "timestamp": datetime.now().isoformat()
            }

            self.portfolio[self.pair] = new_position
            self.save_portfolio()

            # ✅ Log de koop inclusief echte fees
            self.log_trade("buy", real_buy_price, quantity, fee=buy_fee)

            self.logger.log(
                f"[{self.bot_name}] 👽 Bought {self.pair}: Price={real_buy_price:.2f}, Quantity={
                    quantity:.6f}, Fee={buy_fee:.2f}",
                to_console=True
            )
        else:
            self.logger.log(
                f"[{self.bot_name}] 👽 Failed to execute buy order for {self.pair}: {order}", to_console=True, to_slack=False)


    def sell(self, fee_percentage):
        """Execute a sell order and remove only the sold asset from the portfolio."""
        if not self.has_position():
            self.logger.log(f"[{self.bot_name}] 👽 No position to sell for {
                            self.pair}.", to_console=True)
            return

        if self.position is None:  # Extra check to prevent NoneType errors
            self.logger.log(f"[{self.bot_name}] 👽❌ Sell failed: No valid position found for {
                            self.pair}.", to_console=True)
            return

        quantity = self.position.get("quantity", 0)
        quantity = self.adjust_quantity(self.pair, quantity)

        if quantity <= 0:
            self.logger.log(f"[{self.bot_name}] 👽 Invalid quantity for {self.pair}: {
                            quantity}", to_console=True, to_slack=False)
            return

        # 🔹 Plaats verkooporder en haal de daadwerkelijke verkoopprijs en fee op
        order = TradingUtils.place_order(
            self.bitvavo, self.pair, "sell", quantity, demo_mode=self.demo_mode)

        if order.get("status") == "filled":  # ✅ Controleer of de order volledig is uitgevoerd
            # ✅ Werkelijke verkoopprijs per eenheid
            real_sell_price = order["actual_price"]
            sell_fee = order["fee_paid"]  # ✅ Werkelijke fee

            # 🔹 Bereken de werkelijke winst
            cost_basis = self.position["price"] * \
                quantity  # ✅ Aankoopprijs * hoeveelheid
            revenue = real_sell_price * quantity  # ✅ Werkelijke opbrengst zonder fee
            profit = revenue - cost_basis - sell_fee  # ✅ Corrigeer met de verkoopfee

            # ✅ Log de verkoop inclusief echte fees
            self.log_trade("sell", real_sell_price, quantity, profit, fee=sell_fee)

            # ✅ Verwijder de positie uit de portfolio na verkoop
            if self.pair in self.portfolio:
                del self.portfolio[self.pair]  # ✅ Verwijder uit portfolio
                self.save_portfolio()  # ✅ Sla direct de wijziging op
                self.portfolio = self.load_portfolio()  # ✅ Herlaad om te verifiëren

            self.logger.log(
                f"[{self.bot_name}] 👽 Sold {self.pair}: Price={real_sell_price:.2f}, Profit={
                    profit:.2f}, Fee={sell_fee:.2f}",
                to_console=True
            )
        else:
            self.logger.log(f"[{self.bot_name}] 👽 Failed to execute sell order for {self.pair}: {
                            order}", to_console=True, to_slack=False)


    def calculate_profit(self, current_price):
        """
        Calculate the actual profit or loss for the current position based on real transaction fees.

        Args:
            current_price (float): The current market price of the asset.

        Returns:
            float or None: The profit or loss as a percentage of the initial investment, or None if no position exists.
        """
        if not self.has_position():
            self.logger.log(
                f"⚠️ No active position for {self.pair}. Skipping profit calculation.", to_console=True)
            return None  # Voorkomt crash als er geen positie is

        quantity = self.position["quantity"]
        cost_basis = self.position["price"] * quantity  # Aankoopkosten zonder fees

        # **✅ Ophalen van de echte verkoopprijs en fee via Bitvavo API**
        order_details = TradingUtils.get_order_details(
            self.bitvavo, self.pair, "sell")

        if not order_details:
            self.logger.log(f"⚠️ Geen ordergegevens gevonden voor {
                            self.pair}. Gebruik fallback.", to_console=True)
            revenue = current_price * quantity  # Als fallback nemen we de huidige marktprijs
            total_fees = 0  # We weten de echte fee niet, dus laten we die op 0
        else:
            # ✅ **Gebruik de echte prijs & fees uit Bitvavo**
            # Totale ontvangen bedrag
            revenue = float(order_details["filledAmount"])
            total_fees = float(order_details.get(
                "feePaid", 0))  # Echte betaalde fee

        # ✅ Netto winstberekening met echte fee
        profit = revenue - cost_basis - total_fees

        return (profit / cost_basis) * 100  # Winst in percentage


    def log_trade(self, trade_type, price, quantity, profit=None, fee=None):
        """
        Log trade details to a JSON file, now including actual transaction fees.

        Args:
            trade_type (str): "buy" or "sell".
            price (float): Trade price.
            quantity (float): Quantity traded.
            profit (float, optional): Profit from the trade.
            fee (float, optional): The actual fee paid.
        """
        trade = {
            "pair": self.pair,
            "type": trade_type,
            "price": price,
            "quantity": quantity,
            "profit": profit,
            "fee": fee,  # ✅ **Echte fee wordt nu gelogd**
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
            self.logger.log(f"[{self.bot_name}] 👽❗ Error logging trade: {
                            e}", to_console=True, to_slack=False)
