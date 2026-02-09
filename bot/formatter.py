"""Notification message formatters (HTML mode)."""

from html import escape

from .models import Position

LINE = "━━━━━━━━━━━━━━━━━━"


def fmt_usd(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}${value:,.2f}" if value != 0 else "$0.00"


def fmt_pnl(value: float) -> str:
    """Format PnL with emoji color indicator and bold."""
    if value > 0:
        return f"🟢 <b>+${value:,.2f}</b>"
    elif value < 0:
        return f"🔴 <b>-${abs(value):,.2f}</b>"
    return "⚪ <b>$0.00</b>"


def fmt_pnl_with_pct(value: float, roe: float) -> str:
    """Format PnL with percentage and emoji."""
    sign = "+" if roe > 0 else ""
    pct = f"({sign}{roe:.2%})"
    if value > 0:
        return f"🟢 <b>+${value:,.2f}</b> {pct}"
    elif value < 0:
        return f"🔴 <b>-${abs(value):,.2f}</b> {pct}"
    return f"⚪ <b>$0.00</b> {pct}"


def fmt_pct(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2%}"


def fmt_wallet(wallet: str) -> str:
    return f"{wallet[:6]}...{wallet[-4:]}"


def fmt_side(side: str) -> str:
    return f"{'🟢' if side == 'LONG' else '🔴'} {side}"


def fmt_open(wallet: str, pos: Position) -> str:
    return (
        f"🟢🟢🟢 <b>POSITION OPENED</b> 🟢🟢🟢\n"
        f"{LINE}\n"
        f"👛 {fmt_wallet(wallet)}\n"
        f"🪙 <b>{escape(pos.coin)}</b> — {fmt_side(pos.side)}\n"
        f"📏 Size: <b>{pos.size} {escape(pos.coin)}</b>\n"
        f"💵 Entry: <b>${pos.entry_price:,.2f}</b>\n"
        f"⚡ Leverage: <b>{pos.leverage:.0f}x</b>\n"
        f"💎 Value: ${pos.position_value:,.2f}"
    )


def fmt_close(wallet: str, coin: str, old: Position, realized_pnl: float | None) -> str:
    lines = [
        f"🔴🔴🔴 <b>POSITION CLOSED</b> 🔴🔴🔴",
        LINE,
        f"👛 {fmt_wallet(wallet)}",
        f"🪙 <b>{escape(coin)}</b>",
        f"📊 Side: {fmt_side(old.side)} → Closed",
        f"💵 Entry: ${old.entry_price:,.2f}",
        f"📏 Size: {old.size} {escape(coin)}",
    ]
    if realized_pnl is not None:
        lines.append(f"💰 Realized PnL: {fmt_pnl(realized_pnl)}")
    return "\n".join(lines)


def fmt_update(wallet: str, old: Position, new: Position) -> str:
    size_change = new.size - old.size
    if size_change > 0:
        direction = "INCREASED"
        icon = "📈📈📈"
    else:
        direction = "DECREASED"
        icon = "📉📉📉"
    return (
        f"{icon} <b>POSITION {direction}</b> {icon}\n"
        f"{LINE}\n"
        f"👛 {fmt_wallet(wallet)}\n"
        f"🪙 <b>{escape(new.coin)}</b> — {fmt_side(new.side)}\n"
        f"📏 Size: {old.size} → <b>{new.size} {escape(new.coin)}</b>\n"
        f"💵 Entry: ${old.entry_price:,.2f} → <b>${new.entry_price:,.2f}</b>\n"
        f"⚡ Leverage: <b>{new.leverage:.0f}x</b>\n"
        f"💎 Value: ${new.position_value:,.2f}\n"
        f"💰 Unrealized PnL: {fmt_pnl(new.unrealized_pnl)}"
    )


def fmt_position_summary(wallet: str, positions: dict[str, Position]) -> str:
    if not positions:
        return f"📊 <b>{fmt_wallet(wallet)}</b>\n😴 No open positions."

    total_pnl = 0.0
    lines = [f"📊 <b>Positions — {fmt_wallet(wallet)}</b>\n{LINE}\n"]
    for pos in positions.values():
        total_pnl += pos.unrealized_pnl
        lines.append(
            f"🪙 <b>{escape(pos.coin)}</b> — {fmt_side(pos.side)}\n"
            f"  📏 Size: {pos.size} {escape(pos.coin)}\n"
            f"  💵 Entry: ${pos.entry_price:,.2f}\n"
            f"  ⚡ Leverage: {pos.leverage:.0f}x\n"
            f"  💎 Value: ${pos.position_value:,.2f}\n"
            f"  💰 PnL: {fmt_pnl_with_pct(pos.unrealized_pnl, pos.return_on_equity)}\n"
        )
    lines.append(f"{LINE}\n💰 Total PnL: {fmt_pnl(total_pnl)}")
    return "\n".join(lines)


def fmt_balance(wallet: str, data: dict) -> str:
    margin = data.get("marginSummary", {})
    account_value = float(margin.get("accountValue", "0"))
    total_position = float(margin.get("totalNtlPos", "0"))
    margin_used = float(margin.get("totalMarginUsed", "0"))
    withdrawable = float(data.get("withdrawable", "0"))

    return (
        f"💰 <b>Balance — {fmt_wallet(wallet)}</b>\n"
        f"{LINE}\n"
        f"🏦 Account Value: <b>${account_value:,.2f}</b>\n"
        f"📊 Position Value: ${total_position:,.2f}\n"
        f"🔒 Margin Used: ${margin_used:,.2f}\n"
        f"💸 Withdrawable: <b>${withdrawable:,.2f}</b>"
    )
