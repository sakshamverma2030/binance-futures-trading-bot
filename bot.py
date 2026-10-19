import os
import sys
import time
import logging
import argparse
from decimal import Decimal, ROUND_DOWN
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException
from requests.exceptions import ConnectionError as NetConnectionError, Timeout


LOG_DIR = "logs"
MAX_TRIES = 3
RETRY_DELAY = 1.0  # seconds, grows with each try
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

    def _symbol_filters(self, symbol):
        """Return the exchange filters for one symbol, keyed by filterType."""
        info = self.client.futures_exchange_info()
        sym_info = next((s for s in info["symbols"] if s["symbol"] == symbol.upper()), None)
        if sym_info is None:
            raise ValueError(f" Unknown symbol {symbol.upper()}")
        return {f["filterType"]: f for f in sym_info["filters"]}

    @staticmethod
    def _round_down(value, step):
        """Round value down to a multiple of step, using Decimal to avoid float errors."""
        step = Decimal(str(step))
        return (Decimal(str(value)) / step).to_integral_value(rounding=ROUND_DOWN) * step

    def validate_order(self, symbol, price=None, qty=None):
        """Round price and qty to the symbol's tick and step size, then check the limits.

        Returns (price, qty) as Decimals ready to send.
        """
        filters = self._symbol_filters(symbol)

        if price:
            pf = filters["PRICE_FILTER"]
            price = self._round_down(price, pf["tickSize"])
            if price < Decimal(pf["minPrice"]):
                raise ValueError(f" Price {price} below minPrice {pf['minPrice']}")

        if qty:
            lot = filters["LOT_SIZE"]
            qty = self._round_down(qty, lot["stepSize"])
            if qty < Decimal(lot["minQty"]):
                raise ValueError(f" Qty {qty} below minQty {lot['minQty']}")

        notional = filters.get("MIN_NOTIONAL")
        if notional and price and qty:
            min_notional = Decimal(notional.get("notional", notional.get("minNotional", "0")))
            if price * qty < min_notional:
                raise ValueError(f" Order value {price * qty} below minimum notional {min_notional}")

        return price, qty

    def place_order(self, symbol, side, order_type, quantity, price=None, stop_price=None):
        if order_type.upper() == "LIMIT" and not price:
            raise ValueError("LIMIT order requires --price")
        if order_type.upper() == "STOP_LIMIT" and (not price or not stop_price):
            raise ValueError("STOP_LIMIT order requires --price and --stop")

        price, quantity = self.validate_order(symbol, price, quantity)
        if stop_price:
            stop_price, _ = self.validate_order(symbol, stop_price, None)

        # USDT-M futures calls a stop-limit order "STOP"
        api_type = "STOP" if order_type.upper() == "STOP_LIMIT" else order_type.upper()
        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": api_type,
            "quantity": str(quantity),
        }

        if order_type.upper() == "LIMIT":
            params.update({"price": str(price), "timeInForce": "GTC"})
        elif order_type.upper() == "STOP_LIMIT":
            params.update({
                "price": str(price),
                "stopPrice": str(stop_price),
                "timeInForce": "GTC"
            })

        # Tag the order so a retry after a timeout can find it instead of placing it twice
        params["newClientOrderId"] = f"bot_{int(time.time() * 1000)}"
        for attempt in range(1, MAX_TRIES + 1):
            try:
                resp = self.client.futures_create_order(**params)
                logger.info(f"Order placed: {resp}")
                return resp
            except BinanceAPIException as e:
                # 5xx and rate limits are temporary; anything else (bad params, balance) is final
                if e.status_code < 500 and e.code != -1003:
                    logger.error(f"Order rejected: {e}")
                    raise
                logger.warning(f"Temporary API error (try {attempt}/{MAX_TRIES}): {e}")
            except (Timeout, NetConnectionError) as e:
                logger.warning(f"Network error (try {attempt}/{MAX_TRIES}): {e}")
                existing = self._find_order(params["symbol"], params["newClientOrderId"])
                if existing:
                    logger.info(f"Order went through before the timeout: {existing}")
                    return existing
            if attempt == MAX_TRIES:
                raise RuntimeError("Order failed after retries; check open orders before trying again")
            time.sleep(RETRY_DELAY * attempt)

    def _find_order(self, symbol, client_order_id):
        """Look up an order by our client id; None if it was never created."""
        try:
            return self.client.futures_get_order(symbol=symbol, origClientOrderId=client_order_id)
        except BinanceAPIException:
            return None

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

