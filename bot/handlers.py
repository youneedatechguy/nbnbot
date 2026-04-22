"""Telegram bot command and message handlers."""

import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from .nbn_service import NBNService

logger = logging.getLogger(__name__)

# Try to import tracking module; use stubs if not available
try:
    import sys
    sys.path.insert(0, "/mnt/apps/yambabroadband/analytics")
    from tracking import track_command_used, track_address_lookup, track_error
except ImportError:
    # Stubs if tracking module not available
    def track_command_used(*args, **kwargs): pass
    def track_address_lookup(*args, **kwargs): pass
    def track_error(*args, **kwargs): pass
    logger.warning("tracking module not available - analytics disabled")

_nbn_service: NBNService | None = None


def _get_service() -> NBNService:
    global _nbn_service
    if _nbn_service is None:
        _nbn_service = NBNService()
    return _nbn_service


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    track_command_used("start", str(update.effective_user.id) if update.effective_user else None)
    await update.message.reply_text(
        "👋 Hi! I can check NBN availability for any Australian address.\n\n"
        "Just send me an address — for example:\n"
        "_11 Wattle Drive, Yamba NSW 2464_\n\n"
        "Use /help for more info.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    track_command_used("help", str(update.effective_user.id) if update.effective_user else None)
    await update.message.reply_text(
        "*NBN Address Lookup Bot*\n\n"
        "Send any Australian address and I'll check NBN availability via the Iperium API.\n\n"
        "*Examples:*\n"
        "• `11 Wattle Drive, Yamba NSW 2464`\n"
        "• `Unit 3/45 Smith St, Brisbane QLD 4000`\n"
        "• `Lot 5 Rural Road, Grafton NSW 2460`\n\n"
        "*Commands:*\n"
        "/start — welcome message\n"
        "/help — this message\n"
        "/lookup <address> — explicit lookup command",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    address = " ".join(context.args or []).strip()
    if not address:
        await update.message.reply_text("Usage: /lookup <address>")
        return
    track_command_used("lookup", str(update.effective_user.id) if update.effective_user else None)
    await _perform_lookup(update, address)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    if not text:
        return
    await _perform_lookup(update, text)


async def _perform_lookup(update: Update, address: str) -> None:
    thinking_msg = await update.message.reply_text(
        f"🔍 Looking up *{address}*…", parse_mode=ParseMode.MARKDOWN
    )

    try:
        service = _get_service()
        results = await service.lookup(address)
    except ValueError as exc:
        if "Address could not be matched" in str(exc):
            # Address could not be matched by Iperium API
            track_error("address_not_matched", str(exc), str(update.effective_user.id) if update.effective_user else None)
            await thinking_msg.edit_text(
                f"❌ Address could not be matched: {address}\n\n"
                "The address may not exist in the NBN database or may not be serviceable yet."
            )
        else:
            # Geocoding error
            await thinking_msg.edit_text(
                f"❌ Could not geocode address: {exc}\n\nPlease try a more specific address."
            )
        return
    except Exception as exc:
        logger.exception("Lookup failed for %r", address)
        track_error("lookup_exception", str(exc), str(update.effective_user.id) if update.effective_user else None)
        await thinking_msg.edit_text(
            "⚠️ An error occurred while looking up NBN availability. Please try again later."
        )
        return

    if not results:
        await thinking_msg.edit_text(
            f"📭 No NBN results found for:\n_{address}_\n\n"
            "The address may not be in the NBN database or is not yet serviceable.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = [f"📡 *NBN Availability for {address}*\n"]
    for i, result in enumerate(results, 1):
        if len(results) > 1:
            lines.append(f"*Result {i}:*")
        lines.append(result.format_message())
        lines.append("")

    track_address_lookup(
        str(update.effective_user.id) if update.effective_user else "",
        address,
        bool(results),
    )
    await thinking_msg.edit_text("\n".join(lines).strip(), parse_mode=ParseMode.MARKDOWN)


def build_application(token: str) -> Application:
    """Build and return the configured Telegram Application."""
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("lookup", cmd_lookup))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app
