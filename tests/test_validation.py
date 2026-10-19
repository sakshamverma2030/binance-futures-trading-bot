from decimal import Decimal
from unittest.mock import MagicMock

import pytest

import bot

EXCHANGE_INFO = {
    "symbols": [{
        "symbol": "BTCUSDT",
        "filters": [
            {"filterType": "PRICE_FILTER", "minPrice": "0.10", "tickSize": "0.10"},
            {"filterType": "LOT_SIZE", "minQty": "0.001", "stepSize": "0.001"},
            {"filterType": "MIN_NOTIONAL", "notional": "100"},
        ],
    }]
}


@pytest.fixture
def trader():
    b = bot.BasicBot.__new__(bot.BasicBot)
    b.client = MagicMock()
    b.client.futures_exchange_info.return_value = EXCHANGE_INFO
    return b


def test_rounds_price_and_qty_down_to_tick_and_step(trader):
    assert trader.validate_order("btcusdt", 85000.37, 0.0029) == (Decimal("85000.30"), Decimal("0.002"))


def test_float_tick_values_are_accepted(trader):
    price, _ = trader.validate_order("BTCUSDT", 0.3, None)
    assert price == Decimal("0.30")


def test_qty_below_min_is_rejected(trader):
    with pytest.raises(ValueError, match="minQty"):
        trader.validate_order("BTCUSDT", None, 0.0004)


def test_below_min_notional_is_rejected(trader):
    with pytest.raises(ValueError, match="notional"):
        trader.validate_order("BTCUSDT", 1000, 0.05)


def test_unknown_symbol_is_rejected(trader):
    with pytest.raises(ValueError, match="Unknown symbol"):
        trader.validate_order("NOPEUSDT", 1, 1)


def test_limit_without_price_is_rejected(trader):
    with pytest.raises(ValueError, match="requires --price"):
        trader.place_order("BTCUSDT", "BUY", "LIMIT", 0.002)
    trader.client.futures_create_order.assert_not_called()


def test_stop_limit_without_stop_is_rejected(trader):
    with pytest.raises(ValueError, match="--stop"):
        trader.place_order("BTCUSDT", "SELL", "STOP_LIMIT", 0.002, price=84000)


def test_stop_limit_is_sent_as_stop(trader):
    trader.place_order("BTCUSDT", "SELL", "STOP_LIMIT", 0.002, price=84000, stop_price=84500)
    sent = trader.client.futures_create_order.call_args.kwargs
    assert sent["type"] == "STOP"
    assert sent["stopPrice"] == "84500"


def _api_error(status, code):
    from binance.exceptions import BinanceAPIException
    resp = MagicMock(status_code=status, text='{"code": %d, "msg": "x"}' % code)
    return BinanceAPIException(resp, status, resp.text)


def test_temporary_error_is_retried(trader, monkeypatch):
    monkeypatch.setattr(bot, "RETRY_DELAY", 0)
    trader.client.futures_create_order.side_effect = [_api_error(503, -1001), {"status": "NEW"}]
    assert trader.place_order("BTCUSDT", "BUY", "MARKET", 0.002) == {"status": "NEW"}
    assert trader.client.futures_create_order.call_count == 2


def test_rejected_order_is_not_retried(trader):
    trader.client.futures_create_order.side_effect = _api_error(400, -2019)
    with pytest.raises(Exception):
        trader.place_order("BTCUSDT", "BUY", "MARKET", 0.002)
    assert trader.client.futures_create_order.call_count == 1


def test_timeout_does_not_duplicate_a_filled_order(trader, monkeypatch):
    from requests.exceptions import Timeout
    monkeypatch.setattr(bot, "RETRY_DELAY", 0)
    trader.client.futures_create_order.side_effect = Timeout()
    trader.client.futures_get_order.return_value = {"status": "FILLED"}
    assert trader.place_order("BTCUSDT", "BUY", "MARKET", 0.002) == {"status": "FILLED"}
    assert trader.client.futures_create_order.call_count == 1
