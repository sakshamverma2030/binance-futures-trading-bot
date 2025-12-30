# binance-futures-trading-bot

A Python bot that places **Market, Limit, and Stop-Limit orders** on Binance USDT-M Futures Testnet.  
Built for the hiring assignment: *Junior Python Developer – Crypto Trading Bot*.

---

##  Features
- Place **Market** and **Limit** orders (BUY/SELL).
- Support **Stop-Limit** orders (bonus type).
- Command-line interface (CLI) for input validation.
- Structured logging of requests, responses, and errors.
- Display open orders and positions after each trade.
- Uses official Binance API (`python-binance`).

---

##  Requirements
- Python 3.9+
- Virtual environment recommended
- Dependencies:
 
  pip install python-binance python-dotenv

  ##  Setup
1.Clone repo and create .env file:
BINANCE_API_KEY=your_testnet_api_key
BINANCE_API_SECRET=your_testnet_api_secret

2.Run inside virtual environment:
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
.venv\Scripts\activate      # Windows

## Usage
**Market Order**
python bot.py --symbol BTCUSDT --side BUY --type MARKET --qty 0.003

**Limit Order**
python bot.py --symbol BTCUSDT --side SELL --type LIMIT --qty 0.002 --price 85000


## Logs
All logs saved in logs/ directory.
ex: 2025-12-30 23:01:56 | INFO | Order placed: {...}
2025-12-30 23:01:56 | INFO | Final status: FILLED

## OUTPUT EXAMPLE

=== Order Result ===
symbol: BTCUSDT
side: BUY
type: MARKET
status: FILLED
orderId: 11270273673
price: 0.00
origQty: 0.003
executedQty: 0.003

=== Open Orders ===
[]

=== Open Positions ===
[{'symbol': 'BTCUSDT', 'positionAmt': '0.003', 'entryPrice': '85000.00', ...}]
