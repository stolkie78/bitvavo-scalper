import asyncio
import json
import os
import argparse
from datetime import datetime
from bot.config_loader import ConfigLoader
from bot.state_manager import StateManager
from bot.trading_utils import TradingUtils
from bot.logging_facility import LoggingFacility
from bot.bitvavo_client import bitvavo


class ScalpingBot:
    VERSION = "0.2.1"

    def __init__(self, config, logger, state_managers, bitvavo, args):
        self.config = config
        self.logger = logger
        self.state_managers = state_managers
        self.bitvavo = bitvavo
        self.args = args
        self.data_dir = "data"
        self.portfolio_file = os.path.join(self.data_dir, "portfolio.json")
        self.portfolio = self.load_portfolio()
        self.bot_name = args.bot_name
        self.price_history = {pair: [] for pair in config["PAIRS"]}
        self.pair_budgets = {
            pair: (self.config["TOTAL_BUDGET"] *
                   self.config["PORTFOLIO_ALLOCATION"][pair] / 100)
            for pair in self.config["PAIRS"]
            state_managers = {
                pair: StateManager(pair, logger, bitvavo,
                                   demo_mode=config.get("DEMO_MODE", False))
                for pair in config["PAIRS"]
            }
        }

        # Log startup parameters
        self.log_startup_parameters()

    def load_portfolio(self):
        """Laadt de portfolio-inhoud vanuit een JSON-bestand."""
        if os.path.exists(self.portfolio_file):
            try:
                with open(self.portfolio_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                self.logger.log(f"👽❌ Error loading portfolio: {
                                e}", to_console=True)
        return {}

    def log_message(self, message, to_slack=False):
        prefixed_message = f"[{self.bot_name}] {message}"
        self.logger.log(prefixed_message, to_console=True, to_slack=to_slack)

    def log_startup_parameters(self):
        """Log de startparameters van de bot."""
        startup_info = {
            "version": self.VERSION,
            "bot_name": self.bot_name,
            "startup_parameters": vars(self.args),
            "config_file": self.args.config,
            "trading_pairs": self.config.get("PAIRS", []),
            "total_budget": self.config.get("TOTAL_BUDGET", "N/A"),
        }
        self.log_message(f"🚀 Starting ScalpingBot", to_slack=True)
        self.log_message(f"📊 Startup Info: {json.dumps(
            startup_info, indent=2)}", to_slack=True)

    async def process_ticker_update(self, data):
        """Verwerk binnenkomende WebSocket prijsupdates."""
        pair = data.get("market")
        price = float(data.get("price"))

        if pair not in self.price_history:
            return

        self.price_history[pair].append(price)
        if len(self.price_history[pair]) > self.config["WINDOW_SIZE"]:
            self.price_history[pair].pop(0)

        rsi = TradingUtils.calculate_rsi(
            self.price_history[pair], self.config["WINDOW_SIZE"])
        if rsi is None:
            return

        self.log_message(f"✅ Current price for {pair}: {
                         price:.2f} EUR, RSI={rsi:.2f}")

        # SELL logic
        if rsi >= self.config["SELL_THRESHOLD"] and self.state_managers[pair].has_position():
            profit = await self.state_managers[pair].calculate_profit(self.config["TRADE_FEE_PERCENTAGE"])
            if profit >= self.config["MINIMUM_PROFIT_PERCENTAGE"]:
                self.log_message(f"🔴 Selling {pair}. RSI={rsi:.2f}, Price: {
                                 price:.2f}, Profit={profit:.2f}%", to_slack=True)
                await self.state_managers[pair].sell(self.config["TRADE_FEE_PERCENTAGE"])
            else:
                self.log_message(f"⚠️ Skipping sell for {pair}: Profit {
                                 profit:.2f}% below threshold.", to_slack=False)

        # BUY logic
        elif rsi <= self.config["BUY_THRESHOLD"] and not self.state_managers[pair].has_position():
            self.log_message(f"🟢 Buying {pair}. Price: {
                             price:.2f}, RSI={rsi:.2f}", to_slack=True)
            await self.state_managers[pair].buy(self.pair_budgets[pair], self.config["TRADE_FEE_PERCENTAGE"])

    async def run(self):
        """Start de WebSocket listener en trading logica."""
        self.log_message(f"📊 Trading started at {datetime.now()}")

        async def on_ticker(data):
            await self.process_ticker_update(data)

        # ✅ WebSocket verbinding maken en subscriben op live tickers
        pairs = [{"market": pair} for pair in self.config["PAIRS"]]
        self.bitvavo.websocket_tickerPrice(pairs, on_ticker)

        # ✅ Houd WebSocket-verbinding actief
        while True:
            await asyncio.sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ScalpingBot with WebSocket integration."
    )
    parser.add_argument("--config", type=str, default="scalper.json",
                        help="Path to the JSON configuration file")
    parser.add_argument("--bot-name", type=str, required=True,
                        help="Unique name for the bot instance")
    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    # ✅ WebSocket Bitvavo API initialiseren
    bitvavo = bitvavo(ConfigLoader.load_config("bitvavo.json"))
    config = ConfigLoader.load_config(config_path)
    logger = LoggingFacility(ConfigLoader.load_config("slack.json"))


    async def run(self):
        """Start de WebSocket listener en trading logica."""
        self.log_message(f"📊 Trading started at {datetime.now()}")

        async def on_ticker(response):
            await self.process_ticker_update(response)

        # 🔹 Correcte WebSocket subscription
        self.bitvavo.websocket_ticker(self.config["PAIRS"], on_ticker)

        # Houd de WebSocket actief
        while True:
            await asyncio.sleep(1)

    bot = ScalpingBot(config, logger, state_managers, bitvavo, args)

    asyncio.run(bot.run())
