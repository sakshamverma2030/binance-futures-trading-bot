import os
from dotenv import load_dotenv
from binance.client import Client

load_dotenv()
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

client = Client(api_key, api_secret)
client.API_URL = "https://testnet.binancefuture.com/fapi"

print("Ping:", client.futures_ping())
print("Server time:", client.futures_time())
print("Exchange info sample:", [s["symbol"] for s in client.futures_exchange_info()["symbols"][:5]])
