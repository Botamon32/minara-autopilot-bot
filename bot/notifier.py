"""Telegram notification handler with commands."""

import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from .config import config
from .formatter import fmt_balance, fmt_position_summary, fmt_wallet
from .monitor import fetch_clearinghouse_state, fetch_positions

log = logging.getLogger(__name__)

SHORTCUT_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("📊 Position", callback_data="position"),
        InlineKeyboardButton("💰 Balance", callback_data="balance"),
    ]
])


def authorized(update: Update) -> bool:
    return str(update.effective_chat.id) == config.TELEGRAM_CHAT_ID


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not authorized(update):
        return
    wallets = ", ".join(fmt_wallet(w) for w in config.WALLET_ADDRESSES)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"🤖 MinaraAutoPilot Watch Bot\n\n"
            f"Monitoring: {wallets}\n\n"
            f"Commands:\n"
            f"/position - Positions & unrealized PnL\n"
            f"/balance - Wallet balance\n"
            f"/help - Show this message"
        ),
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not authorized(update):
        return
    await cmd_start(update, context)


async def cmd_position(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not authorized(update):
        return
    chat_id = update.effective_chat.id
    try:
        for wallet in config.WALLET_ADDRESSES:
            positions = await fetch_positions(wallet)
            text = fmt_position_summary(wallet, positions)
            await context.bot.send_message(
                chat_id=chat_id, text=text, reply_markup=SHORTCUT_KEYBOARD,
            )
    except Exception as e:
        log.error("cmd_position error: %s", e)
        await context.bot.send_message(chat_id=chat_id, text=f"Error: {e}")


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not authorized(update):
        return
    chat_id = update.effective_chat.id
    try:
        for wallet in config.WALLET_ADDRESSES:
            data = await fetch_clearinghouse_state(wallet)
            text = fmt_balance(wallet, data)
            await context.bot.send_message(
                chat_id=chat_id, text=text, reply_markup=SHORTCUT_KEYBOARD,
            )
    except Exception as e:
        log.error("cmd_balance error: %s", e)
        await context.bot.send_message(chat_id=chat_id, text=f"Error: {e}")


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if str(query.message.chat_id) != config.TELEGRAM_CHAT_ID:
        return
    await query.answer()
    if query.data == "position":
        await cmd_position(update, context)
    elif query.data == "balance":
        await cmd_balance(update, context)


class TelegramNotifier:
    """Manages Telegram bot with commands and notification queue."""

    def __init__(self, notify_queue: asyncio.Queue[str]) -> None:
        self.notify_queue = notify_queue
        self.app = (
            Application.builder()
            .token(config.TELEGRAM_BOT_TOKEN)
            .post_init(self._post_init)
            .build()
        )
        self.app.add_handler(CommandHandler("start", cmd_start))
        self.app.add_handler(CommandHandler("help", cmd_help))
        self.app.add_handler(CommandHandler("position", cmd_position))
        self.app.add_handler(CommandHandler("balance", cmd_balance))
        self.app.add_handler(CallbackQueryHandler(callback_handler))

    async def _post_init(self, app: Application) -> None:
        """Start notification consumer after bot is initialized."""

        async def consumer() -> None:
            try:
                await self._consume_notifications()
            except asyncio.CancelledError:
                log.info("Notification consumer cancelled")
            except Exception as e:
                log.error("Notification consumer crashed: %s", e, exc_info=True)

        app.create_task(consumer())

    async def _consume_notifications(self) -> None:
        """Consume messages from the queue and send to Telegram."""
        while True:
            message = await self.notify_queue.get()
            try:
                await self.app.bot.send_message(
                    chat_id=config.TELEGRAM_CHAT_ID,
                    text=message,
                    reply_markup=SHORTCUT_KEYBOARD,
                )
                log.info("Notification sent: %s", message[:50])
            except Exception as e:
                log.error("Failed to send notification: %s", e)
            self.notify_queue.task_done()

    def run(self) -> None:
        """Start the Telegram bot polling."""
        self.app.run_polling(drop_pending_updates=True)
