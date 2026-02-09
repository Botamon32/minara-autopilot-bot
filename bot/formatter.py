"""Notification message formatters."""

from .models import Position


def fmt_usd(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}${value:,.2f}" if value != 0 else "$0.00"


def fmt_pct(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2%}"


def fmt_wallet(wallet: str) -> str:
    return f"{wallet[:6]}...{wallet[-4:]}"


def fmt_open(wallet: str, pos: Position) -> str:
    return (
        f"🟢 POSITION OPENED\n"
        f"Wallet: {fmt_wallet(wallet)}\n"
        f"Coin: {pos.coin}\n"
        f"Side: {pos.side}\n"
        f"Size: {pos.size} {pos.coin}\n"
        f"Entry: ${pos.entry_price:,.2f}\n"
        f"Leverage: {pos.leverage:.0f}x\n"
        f"Position Value: ${pos.position_value:,.2f}"
    )


def fmt_close(wallet: str, coin: str, old: Position, realized_pnl: float | None) -> str:
    lines = [
        f"🔴 POSITION CLOSED",
        f"Wallet: {fmt_wallet(wallet)}",
        f"Coin: {coin}",
        f"Side was: {old.side}",
        f"Entry was: ${old.entry_price:,.2f}",
        f"Size was: {old.size} {coin}",
    ]
    if realized_pnl is not None:
        lines.append(f"Realized PnL: {fmt_usd(realized_pnl)}")
    return "\n".join(lines)


def fmt_update(wallet: str, old: Position, new: Position) -> str:
    size_change = new.size - old.size
    direction = "INCREASED" if size_change > 0 else "DECREASED"
    return (
        f"🔄 POSITION UPDATED ({direction})\n"
        f"Wallet: {fmt_wallet(wallet)}\n"
        f"Coin: {new.coin}\n"
        f"Side: {new.side}\n"
        f"Size: {old.size} → {new.size} {new.coin}\n"
        f"Entry: ${old.entry_price:,.2f} → ${new.entry_price:,.2f}\n"
        f"Leverage: {new.leverage:.0f}x\n"
        f"Position Value: ${new.position_value:,.2f}\n"
        f"Unrealized PnL: {fmt_usd(new.unrealized_pnl)}"
    )


def fmt_position_summary(wallet: str, positions: dict[str, Position]) -> str:
    if not positions:
        return f"📊 {fmt_wallet(wallet)}\nNo open positions."

    total_pnl = 0.0
    lines = [f"📊 Positions — {fmt_wallet(wallet)}\n"]
    for pos in positions.values():
        total_pnl += pos.unrealized_pnl
        lines.append(
            f"{'🟢' if pos.side == 'LONG' else '🔴'} {pos.coin} {pos.side}\n"
            f"  Size: {pos.size} {pos.coin}\n"
            f"  Entry: ${pos.entry_price:,.2f}\n"
            f"  Leverage: {pos.leverage:.0f}x\n"
            f"  Value: ${pos.position_value:,.2f}\n"
            f"  PnL: {fmt_usd(pos.unrealized_pnl)} ({fmt_pct(pos.return_on_equity)})\n"
        )
    lines.append(f"Total Unrealized PnL: {fmt_usd(total_pnl)}")
    return "\n".join(lines)


def fmt_balance(wallet: str, data: dict) -> str:
    margin = data.get("marginSummary", {})
    account_value = float(margin.get("accountValue", "0"))
    total_position = float(margin.get("totalNtlPos", "0"))
    margin_used = float(margin.get("totalMarginUsed", "0"))
    withdrawable = float(data.get("withdrawable", "0"))

    return (
        f"💰 Balance — {fmt_wallet(wallet)}\n\n"
        f"Account Value: ${account_value:,.2f}\n"
        f"Position Value: ${total_position:,.2f}\n"
        f"Margin Used: ${margin_used:,.2f}\n"
        f"Withdrawable: ${withdrawable:,.2f}"
    )
