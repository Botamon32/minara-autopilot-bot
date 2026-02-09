"""HyperLiquid Position Monitor Telegram Bot

Monitors a wallet for position changes on HyperLiquid
and sends notifications via Telegram.
"""

import asyncio
import json
import logging
import os
import signal
import sys
from dataclasses import dataclass

import httpx
import websockets
from dotenv import load_dotenv
from telegram import Bot

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


async def fetch_positions(client: httpx.AsyncClient) -> dict[str, Position]:
    """Fetch current positions via REST API."""
    resp = await client.post(
        REST_URL,
        json={"type": "clearinghouseState", "user": WALLET},
    )
    resp.raise_for_status()
    data = resp.json()
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
    # If the coin still exists in new positions with 0 size, it was just closed
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


async def send_telegram(bot: Bot, message: str) -> None:
    """Send a message via Telegram."""
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        log.info("Telegram notification sent")
    except Exception as e:
        log.error("Failed to send Telegram message: %s", e)


async def compare_and_notify(
    bot: Bot,
    old_positions: dict[str, Position],
    new_positions: dict[str, Position],
) -> None:
    """Compare positions and send notifications for changes."""
    # Detect new / opened positions
    for coin, pos in new_positions.items():
        if coin not in old_positions:
            await send_telegram(bot, fmt_open(pos))

    # Detect closed positions
    for coin, old_pos in old_positions.items():
        if coin not in new_positions:
            await send_telegram(bot, fmt_close(coin, old_pos, new_positions))

    # Detect updated positions (size or side change)
    for coin in old_positions.keys() & new_positions.keys():
        old = old_positions[coin]
        new = new_positions[coin]
        if old.size != new.size or old.side != new.side:
            await send_telegram(bot, fmt_update(old, new))


async def run() -> None:
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_bot_token_here":
        log.error("TELEGRAM_BOT_TOKEN is not set in .env")
        sys.exit(1)
    if not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID == "your_chat_id_here":
        log.error("TELEGRAM_CHAT_ID is not set in .env")
        sys.exit(1)
    if not WALLET:
        log.error("WALLET_ADDRESS is not set in .env")
        sys.exit(1)

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    client = httpx.AsyncClient(timeout=30)

    # Fetch initial positions
    log.info("Fetching initial positions for %s ...", WALLET)
    positions = await fetch_positions(client)
    log.info(
        "Initial positions: %s",
        [f"{p.coin} {p.side} {p.size}" for p in positions.values()] or "none",
    )

    await send_telegram(
        bot,
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
                    """Send HyperLiquid application-level ping every 50s."""
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
                            log.warning("Non-JSON message: %s", raw[:200])
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

                        # Small delay to let the position state settle
                        await asyncio.sleep(1)

                        new_positions = await fetch_positions(client)
                        await compare_and_notify(bot, positions, new_positions)
                        positions = new_positions
                finally:
                    ping_task.cancel()

        except websockets.ConnectionClosed as e:
            log.warning("WebSocket closed: %s. Reconnecting in 5s ...", e)
        except Exception as e:
            log.error("Error: %s. Reconnecting in 5s ...", e)

        await asyncio.sleep(5)


def main() -> None:
    loop = asyncio.new_event_loop()

    def shutdown(sig: int, _frame) -> None:
        log.info("Received signal %s, shutting down ...", signal.Signals(sig).name)
        for task in asyncio.all_tasks(loop):
            task.cancel()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        loop.run_until_complete(run())
    except asyncio.CancelledError:
        log.info("Bot stopped.")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
