"""Data models for positions."""

from dataclasses import dataclass


@dataclass
class Position:
    coin: str
    size: float
    side: str
    entry_price: float
    leverage: float
    position_value: float
    unrealized_pnl: float
    return_on_equity: float


def parse_position(item: dict) -> Position | None:
    """Parse a position item from clearinghouseState response."""
    pos = item.get("position", {})
    size = float(pos.get("szi", "0"))
    if size == 0:
        return None
    entry_price = float(pos.get("entryPx", "0"))
    return Position(
        coin=pos.get("coin", ""),
        size=abs(size),
        side="LONG" if size > 0 else "SHORT",
        entry_price=entry_price,
        leverage=float(pos.get("leverage", {}).get("value", "0")),
        position_value=abs(size) * entry_price,
        unrealized_pnl=float(pos.get("unrealizedPnl", "0")),
        return_on_equity=float(pos.get("returnOnEquity", "0")),
    )
