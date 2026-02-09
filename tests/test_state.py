"""Tests for StateStore save/load/clear."""

import pytest

from bot.models import Position
from bot.state import StateStore

WALLET = "0xtest1234567890"


@pytest.fixture
def store(tmp_path):
    return StateStore(str(tmp_path / "test.db"))


def make_position(**overrides):
    defaults = dict(
        coin="ETH",
        size=1.5,
        side="LONG",
        entry_price=3000.0,
        leverage=10.0,
        position_value=4500.0,
        unrealized_pnl=100.0,
        return_on_equity=0.05,
    )
    defaults.update(overrides)
    return Position(**defaults)


def test_load_empty(store):
    assert store.load_positions(WALLET) is None


def test_save_and_load(store):
    positions = {
        "ETH": make_position(coin="ETH"),
        "BTC": make_position(coin="BTC", size=0.5, entry_price=95000.0),
    }
    store.save_positions(WALLET, positions)
    loaded = store.load_positions(WALLET)

    assert loaded is not None
    assert set(loaded.keys()) == {"ETH", "BTC"}
    assert loaded["ETH"].size == 1.5
    assert loaded["BTC"].entry_price == 95000.0


def test_save_overwrites(store):
    store.save_positions(WALLET, {"ETH": make_position()})
    store.save_positions(WALLET, {"BTC": make_position(coin="BTC")})

    loaded = store.load_positions(WALLET)
    assert set(loaded.keys()) == {"BTC"}


def test_clear(store):
    store.save_positions(WALLET, {"ETH": make_position()})
    store.clear(WALLET)
    assert store.load_positions(WALLET) is None


def test_multiple_wallets(store):
    wallet_a = "0xAAAA"
    wallet_b = "0xBBBB"

    store.save_positions(wallet_a, {"ETH": make_position()})
    store.save_positions(wallet_b, {"BTC": make_position(coin="BTC")})

    loaded_a = store.load_positions(wallet_a)
    loaded_b = store.load_positions(wallet_b)

    assert set(loaded_a.keys()) == {"ETH"}
    assert set(loaded_b.keys()) == {"BTC"}

    store.clear(wallet_a)
    assert store.load_positions(wallet_a) is None
    assert store.load_positions(wallet_b) is not None
