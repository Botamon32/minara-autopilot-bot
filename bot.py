"""HyperLiquid Position Monitor Telegram Bot

Monitors a wallet for position changes on HyperLiquid
and sends notifications via Telegram.
"""

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass

import httpx
import websockets
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

WALLET = os.getenv("WALLET_ADDRESS", "")
REST_URL = "https://api.hyperliquid.xyz/info"
WS_URL = "wss://api.hyperliquid.xyz/ws"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

http_client = httpx.AsyncClient(timeout=30)


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


async def fetch_clearinghouse_state() -> dict:
    """Fetch full clearinghouse state via REST API."""
    resp = await http_client.post(
        REST_URL,
        json={"type": "clearinghouseState", "user": WALLET},
    )
    resp.raise_for_status()
    return resp.json()


async def fetch_positions() -> dict[str, Position]:
    """Fetch current positions via REST API."""
    data = await fetch_clearinghouse_state()
    positions: dict[str, Position] = {}
    for item in data.get("assetPositions", []):
        pos = parse_position(item)
        if pos:
            positions[pos.coin] = pos
    return positions


def fmt_usd(value: float) -> str:
    """Format a number as USD."""
    sign = "+" if value > 0 else ""
    return f"{sign}${value:,.2f}" if value != 0 else "$0.00"


def fmt_pct(value: float) -> str:
    """Format a number as percentage."""
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2%}"


def fmt_open(pos: Position) -> str:
    return (
        f"🟢 POSITION OPENED\n"
        f"Coin: {pos.coin}\n"
        f"Side: {pos.side}\n"
        f"Size: {pos.size} {pos.coin}\n"
        f"Entry: ${pos.entry_price:,.2f}\n"
        f"Leverage: {pos.leverage:.0f}x\n"
        f"Position Value: ${pos.position_value:,.2f}"
    )


def fmt_close(coin: str, old: Position, new_positions: dict[str, Position]) -> str:
    return (
        f"🔴 POSITION CLOSED\n"
        f"Coin: {coin}\n"
        f"Side was: {old.side}\n"
        f"Entry was: ${old.entry_price:,.2f}\n"
        f"Size was: {old.size} {coin}"
    )


def fmt_update(old: Position, new: Position) -> str:
    size_change = new.size - old.size
    direction = "INCREASED" if size_change > 0 else "DECREASED"
    return (
        f"🔄 POSITION UPDATED ({direction})\n"
        f"Coin: {new.coin}\n"
        f"Side: {new.side}\n"
        f"Size: {old.size} → {new.size} {new.coin}\n"
        f"Entry: ${old.entry_price:,.2f} → ${new.entry_price:,.2f}\n"
        f"Leverage: {new.leverage:.0f}x\n"
        f"Position Value: ${new.position_value:,.2f}\n"
        f"Unrealized PnL: {fmt_usd(new.unrealized_pnl)}"
    )


# --- Telegram Command Handlers ---


def authorized(update: Update) -> bool:
    """Check if the user is authorized."""
    return str(update.effective_chat.id) == TELEGRAM_CHAT_ID


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not authorized(update):
        return
    await update.message.reply_text(
        "🤖 MinaraAutoPilot Watch Bot\n\n"
        "Commands:\n"
        "/position - Open positions\n"
        "/pnl - Positions & unrealized PnL\n"
        "/balance - Wallet balance\n"
        "/help - Show this message"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not authorized(update):
        return
    await cmd_start(update, context)


async def cmd_pnl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not authorized(update):
        return
    try:
        positions = await fetch_positions()
        if not positions:
            await update.message.reply_text("No open positions.")
            return

        total_pnl = 0.0
        lines = ["📊 Current Positions\n"]
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
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        log.error("cmd_pnl error: %s", e)
        await update.message.reply_text(f"Error: {e}")


async def cmd_position(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not authorized(update):
        return
    try:
        positions = await fetch_positions()
        if not positions:
            await update.message.reply_text("No open positions.")
            return

        lines = ["📋 Open Positions\n"]
        for pos in positions.values():
            lines.append(
                f"{'🟢' if pos.side == 'LONG' else '🔴'} {pos.coin} {pos.side}\n"
                f"  Size: {pos.size} {pos.coin}\n"
                f"  Entry: ${pos.entry_price:,.2f}\n"
                f"  Leverage: {pos.leverage:.0f}x\n"
                f"  Value: ${pos.position_value:,.2f}\n"
            )
        lines.append(f"Total positions: {len(positions)}")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        log.error("cmd_position error: %s", e)
        await update.message.reply_text(f"Error: {e}")


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not authorized(update):
        return
    try:
        data = await fetch_clearinghouse_state()
        margin = data.get("marginSummary", {})
        account_value = float(margin.get("accountValue", "0"))
        total_position = float(margin.get("totalNtlPos", "0"))
        margin_used = float(margin.get("totalMarginUsed", "0"))
        withdrawable = float(data.get("withdrawable", "0"))

        await update.message.reply_text(
            f"💰 Wallet Balance\n\n"
            f"Account Value: ${account_value:,.2f}\n"
            f"Position Value: ${total_position:,.2f}\n"
            f"Margin Used: ${margin_used:,.2f}\n"
            f"Withdrawable: ${withdrawable:,.2f}"
        )
    except Exception as e:
        log.error("cmd_balance error: %s", e)
        await update.message.reply_text(f"Error: {e}")


# --- WebSocket Monitor ---


async def send_telegram(app: Application, message: str) -> None:
    """Send a message via Telegram."""
    try:
        await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        log.info("Telegram notification sent")
    except Exception as e:
        log.error("Failed to send Telegram message: %s", e)


async def compare_and_notify(
    app: Application,
    old_positions: dict[str, Position],
    new_positions: dict[str, Position],
) -> None:
    """Compare positions and send notifications for changes."""
    for coin, pos in new_positions.items():
        if coin not in old_positions:
            await send_telegram(app, fmt_open(pos))

    for coin, old_pos in old_positions.items():
        if coin not in new_positions:
            await send_telegram(app, fmt_close(coin, old_pos, new_positions))

    for coin in old_positions.keys() & new_positions.keys():
        old = old_positions[coin]
        new = new_positions[coin]
        if old.size != new.size or old.side != new.side:
            await send_telegram(app, fmt_update(old, new))


async def ws_monitor(app: Application) -> None:
    """WebSocket monitor that runs alongside the Telegram bot."""
    positions = await fetch_positions()
    log.info(
        "Initial positions: %s",
        [f"{p.coin} {p.side} {p.size}" for p in positions.values()] or "none",
    )

    await send_telegram(
        app,
        f"🤖 Bot started\nMonitoring: {WALLET[:10]}...{WALLET[-6:]}\n"
        f"Current positions: {len(positions)}",
    )

    subscribe_msg = json.dumps(
        {"method": "subscribe", "subscription": {"type": "userEvents", "user": WALLET}}
    )

    while True:
        try:
            log.info("Connecting to WebSocket %s ...", WS_URL)
            async with websockets.connect(WS_URL, ping_interval=None) as ws:
                await ws.send(subscribe_msg)
                log.info("Subscribed to userEvents for %s", WALLET)

                async def send_ping():
                    while True:
                        await asyncio.sleep(50)
                        await ws.send(json.dumps({"method": "ping"}))
                        log.debug("Sent ping")

                ping_task = asyncio.create_task(send_ping())
                try:
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        channel = msg.get("channel")
                        if channel in ("pong", "subscriptionResponse"):
                            continue
                        if channel != "userEvents":
                            continue

                        data = msg.get("data", {})
                        fills = data.get("fills", [])
                        if not fills:
                            continue

                        log.info(
                            "Received %d fill(s): %s",
                            len(fills),
                            [(f.get("coin"), f.get("side"), f.get("sz")) for f in fills],
                        )

                        await asyncio.sleep(1)
                        new_positions = await fetch_positions()
                        await compare_and_notify(app, positions, new_positions)
                        positions = new_positions
                finally:
                    ping_task.cancel()

        except websockets.ConnectionClosed as e:
            log.warning("WebSocket closed: %s. Reconnecting in 5s ...", e)
        except Exception as e:
            log.error("Error: %s. Reconnecting in 5s ...", e)

        await asyncio.sleep(5)


async def post_init(app: Application) -> None:
    """Start WebSocket monitor after Telegram bot is initialized."""
    app.create_task(ws_monitor(app))


def main() -> None:
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_bot_token_here":
        log.error("TELEGRAM_BOT_TOKEN is not set in .env")
        sys.exit(1)
    if not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID == "your_chat_id_here":
        log.error("TELEGRAM_CHAT_ID is not set in .env")
        sys.exit(1)
    if not WALLET:
        log.error("WALLET_ADDRESS is not set in .env")
        sys.exit(1)

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("position", cmd_position))
    app.add_handler(CommandHandler("pnl", cmd_pnl))
    app.add_handler(CommandHandler("balance", cmd_balance))

    log.info("Starting bot ...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
