"""HyperLiquid WebSocket monitor with exponential backoff."""

import asyncio
import json
import logging
import random

import httpx
import websockets

from .config import config
from .formatter import fmt_close, fmt_open, fmt_update, fmt_wallet
from .models import Position, parse_position
from .state import StateStore

log = logging.getLogger(__name__)

http_client = httpx.AsyncClient(timeout=30)


async def fetch_clearinghouse_state(wallet: str) -> dict:
    """Fetch full clearinghouse state via REST API."""
    resp = await http_client.post(
        config.REST_URL,
        json={"type": "clearinghouseState", "user": wallet},
    )
    resp.raise_for_status()
    return resp.json()


async def fetch_positions(wallet: str) -> dict[str, Position]:
    """Fetch current positions via REST API."""
    data = await fetch_clearinghouse_state(wallet)
    positions: dict[str, Position] = {}
    for item in data.get("assetPositions", []):
        pos = parse_position(item)
        if pos:
            positions[pos.coin] = pos
    return positions


def diff_positions(
    wallet: str,
    old: dict[str, Position],
    new: dict[str, Position],
    fills: list[dict],
) -> list[str]:
    """Compare positions and return notification messages."""
    # Build realized PnL map from fills
    realized_pnl: dict[str, float] = {}
    for fill in fills:
        coin = fill.get("coin", "")
        closed = float(fill.get("closedPnl", "0"))
        if closed != 0:
            realized_pnl[coin] = realized_pnl.get(coin, 0.0) + closed

    messages: list[str] = []

    for coin, pos in new.items():
        if coin not in old:
            messages.append(fmt_open(wallet, pos))

    for coin, old_pos in old.items():
        if coin not in new:
            pnl = realized_pnl.get(coin)
            messages.append(fmt_close(wallet, coin, old_pos, pnl))

    for coin in old.keys() & new.keys():
        o, n = old[coin], new[coin]
        if o.size != n.size or o.side != n.side:
            messages.append(fmt_update(wallet, o, n))

    return messages


class WalletMonitor:
    """Monitors a single wallet via WebSocket with exponential backoff."""

    ALERT_AFTER_ATTEMPTS = 3  # Send Telegram alert after this many consecutive failures

    def __init__(
        self,
        wallet: str,
        state: StateStore,
        on_notify: "asyncio.Queue[str]",
    ) -> None:
        self.wallet = wallet
        self.state = state
        self.notify_queue = on_notify
        self.positions: dict[str, Position] = {}
        self._delay = config.RECONNECT_BASE_DELAY
        self._reconnect_attempts = 0

    async def start(self) -> None:
        """Initialize positions and start monitoring."""
        # Try to load saved state first
        saved = self.state.load_positions(self.wallet)
        current = await fetch_positions(self.wallet)

        if saved is not None:
            # Compare saved state with current to detect changes while bot was down
            msgs = diff_positions(self.wallet, saved, current, [])
            for msg in msgs:
                await self.notify_queue.put(msg)
            if msgs:
                log.info(
                    "Detected %d change(s) for %s while bot was down",
                    len(msgs), fmt_wallet(self.wallet),
                )

        self.positions = current
        self.state.save_positions(self.wallet, self.positions)

        log.info(
            "Monitoring %s — positions: %s",
            fmt_wallet(self.wallet),
            [f"{p.coin} {p.side} {p.size}" for p in self.positions.values()] or "none",
        )

        await self._ws_loop()

    async def _ws_loop(self) -> None:
        """WebSocket event loop with exponential backoff reconnection."""
        subscribe_msg = json.dumps(
            {"method": "subscribe", "subscription": {"type": "userEvents", "user": self.wallet}}
        )

        while True:
            try:
                log.info("Connecting to WebSocket for %s ...", fmt_wallet(self.wallet))
                async with websockets.connect(config.WS_URL, ping_interval=None) as ws:
                    await ws.send(subscribe_msg)
                    log.info("Subscribed to userEvents for %s", fmt_wallet(self.wallet))

                    # Reset on successful connection
                    self._delay = config.RECONNECT_BASE_DELAY
                    self._reconnect_attempts = 0

                    ping_task = asyncio.create_task(self._ping_loop(ws))
                    try:
                        async for raw in ws:
                            await self._handle_message(raw)
                    finally:
                        ping_task.cancel()

            except websockets.ConnectionClosed as e:
                log.warning(
                    "WebSocket closed for %s: %s",
                    fmt_wallet(self.wallet), e,
                )
            except Exception as e:
                log.error(
                    "WebSocket error for %s: %s",
                    fmt_wallet(self.wallet), e, exc_info=True,
                )

            # Exponential backoff with jitter
            self._reconnect_attempts += 1
            jitter = random.uniform(0, self._delay * 0.1)
            wait = self._delay + jitter
            log.info("Reconnecting %s in %.1fs (attempt %d) ...",
                     fmt_wallet(self.wallet), wait, self._reconnect_attempts)

            # Alert via Telegram after repeated failures
            if self._reconnect_attempts == self.ALERT_AFTER_ATTEMPTS:
                await self.notify_queue.put(
                    f"⚠️ Bot Alert\n"
                    f"WebSocket disconnected for {fmt_wallet(self.wallet)}\n"
                    f"Reconnecting (attempt {self._reconnect_attempts}, "
                    f"next retry in {wait:.1f}s)"
                )

            await asyncio.sleep(wait)
            self._delay = min(self._delay * 2, config.RECONNECT_MAX_DELAY)

    async def _ping_loop(self, ws) -> None:
        """Send HyperLiquid application-level ping."""
        while True:
            await asyncio.sleep(config.PING_INTERVAL)
            await ws.send(json.dumps({"method": "ping"}))
            log.info("Sent ping for %s (WS alive)", fmt_wallet(self.wallet))

    async def _handle_message(self, raw: str) -> None:
        """Process a single WebSocket message."""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        channel = msg.get("channel")
        if channel in ("pong", "subscriptionResponse"):
            return
        if channel != "userEvents":
            return

        data = msg.get("data", {})
        fills = data.get("fills", [])
        if not fills:
            return

        log.info(
            "Received %d fill(s) for %s: %s",
            len(fills),
            fmt_wallet(self.wallet),
            [(f.get("coin"), f.get("side"), f.get("sz"), f.get("closedPnl")) for f in fills],
        )

        await asyncio.sleep(1)
        new_positions = await fetch_positions(self.wallet)
        messages = diff_positions(self.wallet, self.positions, new_positions, fills)

        for msg_text in messages:
            await self.notify_queue.put(msg_text)

        self.positions = new_positions
        self.state.save_positions(self.wallet, self.positions)
