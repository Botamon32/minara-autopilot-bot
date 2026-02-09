"""Main application entry point."""

import asyncio
import logging
import logging.handlers

from telegram.constants import ParseMode

from .config import config
from .formatter import fmt_wallet
from .monitor import WalletMonitor
from .notifier import TelegramNotifier
from .state import StateStore

log = logging.getLogger(__name__)


def run() -> None:
    """Start the bot."""
    log_format = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
    log_datefmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=log_datefmt,
        handlers=[
            logging.StreamHandler(),
            logging.handlers.RotatingFileHandler(
                config.LOG_PATH,
                maxBytes=5 * 1024 * 1024,  # 5MB
                backupCount=3,
                encoding="utf-8",
            ),
        ],
    )

    config.validate()

    log.info(
        "Starting MinaraAutoPilot Watch Bot — wallets: %s",
        [fmt_wallet(w) for w in config.WALLET_ADDRESSES],
    )

    state = StateStore(config.DB_PATH)
    notify_queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()
    notifier = TelegramNotifier(notify_queue)

    # Patch post_init to also start wallet monitors
    original_post_init = notifier.app.post_init

    async def combined_post_init(app) -> None:
        if original_post_init:
            await original_post_init(app)

        # Start a monitor for each wallet
        for wallet in config.WALLET_ADDRESSES:
            monitor = WalletMonitor(wallet, state, notify_queue)

            async def run_monitor(m=monitor) -> None:
                try:
                    await m.start()
                except asyncio.CancelledError:
                    log.info("Monitor for %s cancelled", fmt_wallet(m.wallet))
                except Exception as e:
                    log.error(
                        "Monitor for %s crashed: %s",
                        fmt_wallet(m.wallet), e, exc_info=True,
                    )
                    try:
                        await app.bot.send_message(
                            chat_id=config.TELEGRAM_CHAT_ID,
                            text=f"⚠️ Bot Alert\nMonitor crashed for {fmt_wallet(m.wallet)}\nError: {e}",
                        )
                    except Exception:
                        log.error("Failed to send crash alert")

            app.create_task(run_monitor())

        # Send startup message
        wallets_str = ", ".join(fmt_wallet(w) for w in config.WALLET_ADDRESSES)
        await app.bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            parse_mode=ParseMode.HTML,
            text=(
                f"🚀 <b>Bot Started</b>\n"
                f"👛 Monitoring: {wallets_str}\n"
                f"📡 Wallets: {len(config.WALLET_ADDRESSES)}"
            ),
        )

    notifier.app.post_init = combined_post_init
    notifier.run()
