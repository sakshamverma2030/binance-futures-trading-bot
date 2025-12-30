import os
import sys
import time
import logging
import argparse
from dotenv import load_dotenv
from binance.client import Client


LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, f"bot_{int(time.time())}.log")),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("TradingBot")

class BasicBot:
    def __init__(self, api_key, api_secret, testnet=True):
        self.client = Client(api_key, api_secret, testnet=testnet)
        # Force Futures Testnet base URL
        self.client.FUTURES_URL = "https://testnet.binancefuture.com/fapi"
        logger.info(" Binance Futures Testnet client initialized.")

    def validate_order(self, symbol, price=None, qty=None):
        """Check exchange filters for price and quantity validity."""
        info = self.client.futures_exchange_info()
        sym_info = next(s for s in info["symbols"] if s["symbol"] == symbol.upper())
        filters = {f["filterType"]: f for f in sym_info["filters"]}

        if price:
            min_price = float(filters["PRICE_FILTER"]["minPrice"])
            tick_size = float(filters["PRICE_FILTER"]["tickSize"])
            if price < min_price:
                raise ValueError(f" Price {price} below minPrice {min_price}")
            if round(price / tick_size) * tick_size != price:
                raise ValueError(f" Price {price} not aligned with tickSize {tick_size}")

        if qty:
            min_qty = float(filters["LOT_SIZE"]["minQty"])
            step_size = float(filters["LOT_SIZE"]["stepSize"])
            if qty < min_qty:
                raise ValueError(f" Qty {qty} below minQty {min_qty}")
            if round(qty / step_size) * step_size != qty:
                raise ValueError(f" Qty {qty} not aligned with stepSize {step_size}")

    def place_order(self, symbol, side, order_type, quantity, price=None, stop_price=None):
        self.validate_order(symbol, price, quantity)

        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
        }

        if order_type.upper() == "LIMIT":
            if not price:
                raise ValueError("LIMIT order requires --price")
            params.update({"price": price, "timeInForce": "GTC"})
        elif order_type.upper() == "STOP_LIMIT":
            if not price or not stop_price:
                raise ValueError("STOP_LIMIT order requires --price and --stop")
            params.update({
                "price": price,
                "stopPrice": stop_price,
                "timeInForce": "GTC"
            })

        try:
            resp = self.client.futures_create_order(**params)
            logger.info(f"Order placed: {resp}")
            return resp
        except Exception as e:
            logger.error(f"Order failed: {e}", exc_info=True)
            raise

    def show_open_orders(self, symbol):
        return self.client.futures_get_open_orders(symbol=symbol.upper())

    def show_positions(self, symbol):
        return self.client.futures_position_information(symbol=symbol.upper())

def main():
    load_dotenv()
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    if not api_key or not api_secret:
        print(" Missing API keys in .env file")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Simplified Binance Futures Testnet Bot")
    parser.add_argument("--symbol", required=True, help="Trading pair, e.g. BTCUSDT")
    parser.add_argument("--side", required=True, choices=["BUY", "SELL"], help="Order side")
    parser.add_argument("--type", required=True, choices=["MARKET", "LIMIT", "STOP_LIMIT"], help="Order type")
    parser.add_argument("--qty", type=float, required=True, help="Order quantity")
    parser.add_argument("--price", type=float, help="Price (for LIMIT/STOP_LIMIT)")
    parser.add_argument("--stop", type=float, help="Stop price (for STOP_LIMIT)")
    args = parser.parse_args()

    bot = BasicBot(api_key, api_secret)

    # Place order
    resp = bot.place_order(args.symbol, args.side, args.type, args.qty, args.price, args.stop)

    print("\n=== Order Result ===")
    for key in ["symbol", "side", "type", "status", "orderId", "price", "origQty", "executedQty"]:
        print(f"{key}: {resp.get(key)}")

    # Show open orders
    print("\n=== Open Orders ===")
    print(bot.show_open_orders(args.symbol))

    # Show positions
    print("\n=== Open Positions ===")
    print(bot.show_positions(args.symbol))

if __name__ == "__main__":
    main()

