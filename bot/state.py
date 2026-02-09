"""State persistence using SQLite.

Stores position snapshots so the bot can resume after restart
without missing changes that occurred while it was down.
"""

import json
import logging
import sqlite3
from pathlib import Path

from .models import Position

log = logging.getLogger(__name__)


class StateStore:
    def __init__(self, db_path: str = "state.db") -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    wallet TEXT NOT NULL,
                    coin TEXT NOT NULL,
                    data TEXT NOT NULL,
                    PRIMARY KEY (wallet, coin)
                )
            """)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def save_positions(self, wallet: str, positions: dict[str, Position]) -> None:
        """Save current positions for a wallet."""
        try:
            with self._conn() as conn:
                conn.execute("DELETE FROM positions WHERE wallet = ?", (wallet,))
                for coin, pos in positions.items():
                    data = json.dumps({
                        "coin": pos.coin,
                        "size": pos.size,
                        "side": pos.side,
                        "entry_price": pos.entry_price,
                        "leverage": pos.leverage,
                        "position_value": pos.position_value,
                        "unrealized_pnl": pos.unrealized_pnl,
                        "return_on_equity": pos.return_on_equity,
                    })
                    conn.execute(
                        "INSERT INTO positions (wallet, coin, data) VALUES (?, ?, ?)",
                        (wallet, coin, data),
                    )
        except sqlite3.Error as e:
            log.error("Failed to save positions for %s: %s", wallet, e)

    def load_positions(self, wallet: str) -> dict[str, Position] | None:
        """Load saved positions for a wallet. Returns None if no saved state."""
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT coin, data FROM positions WHERE wallet = ?", (wallet,)
                ).fetchall()
            if not rows:
                return None
            positions: dict[str, Position] = {}
            for coin, data_str in rows:
                d = json.loads(data_str)
                positions[coin] = Position(**d)
            return positions
        except sqlite3.Error as e:
            log.error("Failed to load positions for %s: %s", wallet, e)
            return None

    def clear(self, wallet: str) -> None:
        """Clear saved positions for a wallet."""
        with self._conn() as conn:
            conn.execute("DELETE FROM positions WHERE wallet = ?", (wallet,))
