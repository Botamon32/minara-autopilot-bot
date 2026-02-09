"""Configuration management."""

import os
import sys
import logging

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)


class Config:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    WALLET_ADDRESSES: list[str] = []
    REST_URL: str = "https://api.hyperliquid.xyz/info"
    WS_URL: str = "wss://api.hyperliquid.xyz/ws"
    DB_PATH: str = os.getenv("DB_PATH", "state.db")
    PING_INTERVAL: int = int(os.getenv("PING_INTERVAL", "50"))
    RECONNECT_BASE_DELAY: float = float(os.getenv("RECONNECT_BASE_DELAY", "5"))
    RECONNECT_MAX_DELAY: float = float(os.getenv("RECONNECT_MAX_DELAY", "300"))
    LOG_PATH: str = os.getenv("LOG_PATH", "bot.log")

    def __init__(self) -> None:
        # Support multiple wallets: WALLET_ADDRESS or WALLET_ADDRESSES (comma-separated)
        addrs = os.getenv("WALLET_ADDRESSES", "")
        single = os.getenv("WALLET_ADDRESS", "")
        if addrs:
            self.WALLET_ADDRESSES = [a.strip() for a in addrs.split(",") if a.strip()]
        elif single:
            self.WALLET_ADDRESSES = [single]

    def validate(self) -> None:
        errors = []
        if not self.TELEGRAM_BOT_TOKEN or self.TELEGRAM_BOT_TOKEN == "your_bot_token_here":
            errors.append("TELEGRAM_BOT_TOKEN is not set")
        if not self.TELEGRAM_CHAT_ID or self.TELEGRAM_CHAT_ID == "your_chat_id_here":
            errors.append("TELEGRAM_CHAT_ID is not set")
        if not self.WALLET_ADDRESSES:
            errors.append("WALLET_ADDRESS or WALLET_ADDRESSES is not set")
        if errors:
            for e in errors:
                log.error(e)
            sys.exit(1)


config = Config()
