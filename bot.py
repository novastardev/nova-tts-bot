import io
import logging
import os

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from config import (
    TELEGRAM_BOT_TOKEN,
    ALLOWED_CHAT_IDS,
    BOT_OWNER_HANDLE,
    PUBLIC_MODE,
    OWNER_CHAT_ID,
    RATE_LIMIT_ENABLED,
    MAX_TEXT_LENGTH,
    COOLDOWN_SECONDS,
    DAILY_LIMIT,
)
from database import (
    init_db,
    add_user,
    get_voice,
    set_voice,
    get_library,
    get_library_item,
    delete_from_library,
    save_to_library,
    is_new_user,
    check_and_record_usage,
    get_stats,
)
from tts import get_voices, generate_speech

# ============================================================
# BOT LOGIC
# ============================================================

waiting_for_text = set()

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎙️ Text to Speech", callback_data="tts")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton("📚 My Library", callback_data="library_view")],
    ])

MENU_TEXT = (
    "🔊 *Text to Speech Bot*\n\n"
    "Convert your text into natural speech with multiple voices.\n\n"
    "Tap a button below to get started 👇"
)

def is_chat_allowed(user_id):
    if PUBLIC_MODE:
        return True
    return user_id in ALLOWED_CHAT_IDS


def notify_owner(context, text):
    """Best-effort notification to the owner's chat."""
    if OWNER_CHAT_ID:
        try:
            context.bot.send_message(chat_id=OWNER_CHAT_ID, text=text)
        except Exception:
            logger.exception("Failed to notify owner")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if not is_chat_allowed(user_id):
            await update.message.reply_text(
                f"❌ Access Denied\n\nPlease ask {BOT_OWNER_HANDLE} to grant you access."
            )
            return
        if is_new_user(user_id):
            notify_owner(
                context,
                f"🎉 New user!\n\n"
                f"Name: {update.effective_user.full_name}\n"
                f"Username: @{update.effective_user.username or 'none'}\n"
                f"ID: {user_id}",
            )
        add_user(user_id)
        await update.message.reply_text(MENU_TEXT, reply_markup=main_menu_keyboard(), parse_mode="Markdown")
    except Exception:
        logger.exception("START ERROR")
        await update.message.reply_text("❌ Something went wrong.")

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        add_user(update.effective_user.id)
        keyboard = [[InlineKeyboardButton("🔊 Voice", callback_data="settings_voice")]]
        await update.message.reply_text("⚙️ *Settings*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception:
        logger.exception("SETTINGS ERROR")
        await update.message.reply_text("❌ Unable to open settings.")

async def show_library_message(message, user_id):
    """Render the library list.

    Works for both /library (update.message exists) and button presses
    (only query.message exists).
    """
    items = get_library(user_id, limit=10)
    if not items:
        await message.reply_text(
            "📚 *Your Library*\n\nNo saved audios yet.", parse_mode="Markdown"
        )
        return
    keyboard = []
    for item in items:
        item_id, text = item[0], item[1]
        short = text[:30] + "..." if len(text) > 30 else text
        keyboard.append([InlineKeyboardButton(f"📄 {short}", callback_data=f"lib:{item_id}")])
    await message.reply_text(
        "📚 *Your Library*\n\nClick any to view details",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown",
    )

async def library(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        add_user(update.effective_user.id)
        await show_library_message(update.message, update.effective_user.id)
    except Exception:
        logger.exception("LIBRARY ERROR")

VOICES_PER_PAGE = 20

def voices_keyboard(page, user_id):
    """Two-column paginated voice buttons, ✅ on the user's current voice."""
    voices = get_voices()
    if not voices:
        return None
    current = get_voice(user_id)
    start = page * VOICES_PER_PAGE
    chunk = voices[start:start + VOICES_PER_PAGE]
    keyboard = []
    row = []
    for name, voice in chunk:
        label = f"✅ {name}" if voice == current else name
        row.append(InlineKeyboardButton(label[:40], callback_data=f"voice:{voice}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"vpage:{page-1}"))
    total_pages = (len(voices) + VOICES_PER_PAGE - 1) // VOICES_PER_PAGE
    nav.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"))
    if start + VOICES_PER_PAGE < len(voices):
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"vpage:{page+1}"))
    keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("← Back", callback_data="settings")])
    return InlineKeyboardMarkup(keyboard)

async def show_voices(query, user_id, page=0):
    try:
        markup = voices_keyboard(page, user_id)
        if markup is None:
            await query.edit_message_text("No voices available.")
            return
        await query.edit_message_text(
            "🔊 *Select a Voice*",
            reply_markup=markup, parse_mode="Markdown",
        )
    except Exception:
        logger.exception("VOICE LIST ERROR")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        user_id = query.from_user.id
        data = query.data
        if not is_chat_allowed(user_id):
            await query.answer(f"Access denied", show_alert=True)
            return
        await query.answer()
        add_user(user_id)

        if data == "tts":
            waiting_for_text.add(user_id)
            await query.message.reply_text(
                "📝 *Send the text you want to convert.*\n\n"
                f"Max {MAX_TEXT_LENGTH} characters. /cancel to stop.",
                parse_mode="Markdown"
            )
        elif data == "settings":
            keyboard = [[InlineKeyboardButton("🔊 Voice", callback_data="settings_voice")]]
            await query.edit_message_text("⚙️ *Settings*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        elif data == "library_view":
            await show_library_message(query.message, user_id)
        elif data == "noop":
            pass
        elif data == "settings_voice":
            await show_voices(query, user_id, page=0)
        elif data.startswith("vpage:"):
            page = int(data.split(":", 1)[1])
            await show_voices(query, user_id, page=page)
        elif data.startswith("voice:"):
            voice = data.split(":", 1)[1]
            await query.edit_message_text(f"✅ Voice set to: {voice}")
            set_voice(user_id, voice)
        elif data.startswith("lib:"):
            item_id = int(data.split(":", 1)[1])
            item = get_library_item(user_id, item_id)
            if not item:
                await query.answer("Not found", show_alert=True)
                return
            text, voice, _, created_at = item[1], item[2], item[3], item[4]
            keyboard = [
                [InlineKeyboardButton("🔊 Listen", callback_data=f"play:{item_id}")],
                [InlineKeyboardButton("🗑️ Delete", callback_data=f"del:{item_id}")],
                [InlineKeyboardButton("← Back", callback_data="library_view")],
            ]
            await query.edit_message_text(
                f"📄 *Details*\n\n📝 {text}\n🔊 {voice}\n📅 {created_at}",
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown",
            )
        elif data.startswith("play:"):
            item_id = int(data.split(":", 1)[1])
            item = get_library_item(user_id, item_id)
            if not item or not item[3]:
                await query.answer("Not found", show_alert=True)
                return
            await query.message.reply_voice(item[3])
        elif data.startswith("del:"):
            item_id = int(data.split(":", 1)[1])
            delete_from_library(user_id, item_id)
            await query.answer("✅ Deleted", show_alert=True)
    except Exception:
        logger.exception("BUTTON ERROR")

def check_usage(user_id):
    """Apply rate limits if enabled; always record usage for /stats.

    Returns (allowed, message). message is empty string when allowed.
    """
    if RATE_LIMIT_ENABLED:
        allowed, info = check_and_record_usage(user_id, COOLDOWN_SECONDS, DAILY_LIMIT)
        if not allowed:
            return False, info
        return True, f"({info} left today)"
    # Limits off: just record the usage silently for stats
    check_and_record_usage(user_id, 0, 10**9)
    return True, ""


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if not is_chat_allowed(user_id):
            return
        text = update.message.text
        if user_id not in waiting_for_text:
            # User sent a message outside the TTS flow — they're probably
            # lost. Show the start menu so they can find their way.
            add_user(user_id)
            await update.message.reply_text(
                "🤔 *I didn't quite get that.*\n\n"
                "Here's the menu to get you started 👇",
                reply_markup=main_menu_keyboard(),
                parse_mode="Markdown",
            )
            return
        waiting_for_text.discard(user_id)

        if len(text) > MAX_TEXT_LENGTH:
            await update.message.reply_text(
                f"📏 Text too long ({len(text)} chars).\n"
                f"Maximum is {MAX_TEXT_LENGTH} characters."
            )
            return

        allowed, remaining_msg = check_usage(user_id)
        if not allowed:
            await update.message.reply_text(remaining_msg)
            return

        status_text = "⏳ *Generating...*"
        if remaining_msg:
            status_text = f"⏳ *Generating...* {remaining_msg}"
        await update.message.reply_text(status_text, parse_mode="Markdown")
        voice = get_voice(user_id)
        if not voice:
            await update.message.reply_text("⚠️ No voice selected. Click Settings → Voice first.")
            return

        result = generate_speech(text, voice)
        if result.get("success") and result.get("audio"):
            audio = result["audio"]
            save_to_library(user_id, text, voice, audio)
            await update.message.reply_voice(audio)
        else:
            await update.message.reply_text(f"❌ Error: {result.get('error', 'Unknown')}")
    except Exception:
        logger.exception("TEXT ERROR")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if user_id != OWNER_CHAT_ID:
            await update.message.reply_text("❌ This command is for the bot owner only.")
            return
        total_users, gens_today, gens_total = get_stats()
        await update.message.reply_text(
            f"📊 *Bot Stats*\n\n"
            f"👥 Total users: {total_users}\n"
            f"🎙️ Generations today: {gens_today}\n"
            f"📈 Generations all-time: {gens_total}\n"
            f"🔒 Mode: {'PUBLIC 🌍' if PUBLIC_MODE else 'PRIVATE 🔐'}",
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("STATS ERROR")

async def start_tts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Slash-command version of the 🎙️ Text to Speech button."""
    user_id = update.effective_user.id
    if not is_chat_allowed(user_id):
        return
    add_user(user_id)
    waiting_for_text.add(user_id)
    await update.message.reply_text(
        "📝 *Send the text you want to convert.*\n\n"
        f"Max {MAX_TEXT_LENGTH} characters. /cancel to stop.",
        parse_mode="Markdown",
    )

REPO_URL = "https://github.com/novastardev/nova-tts-bot"

async def contribute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⭐ Star on GitHub", url=REPO_URL)],
        [InlineKeyboardButton("🐛 Report a Bug", url=f"{REPO_URL}/issues/new")],
    ]
    # NOTE: HTML mode — Markdown mode breaks on underscores in @novastar_dev
    await update.message.reply_text(
        "🛠️ <b>Contribute to Nova-TTS Bot</b>\n\n"
        "This bot is <b>open source</b>! 🎉\n\n"
        f"📦 Repository owner: <b>Novastar</b> (@novastar_dev)\n"
        f"🔗 Source code: {REPO_URL}\n\n"
        "<b>How you can help:</b>\n"
        "• ⭐ Star the repo\n"
        "• 🍴 Fork it &amp; add features\n"
        "• 🐛 Report bugs via Issues\n"
        "• 📖 Improve the docs\n"
        "• 🔊 Suggest new voices\n\n"
        "Every contribution makes the bot better. Thank you! 💙",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # NOTE: HTML mode — Markdown mode breaks on underscores in @novastar_dev
    await update.message.reply_text(
        "<b>Built by Novastar</b> 👨‍💻\n\n"
        "A passionate IT developer creating awesome tools.\n"
        "Currently focused on building intelligent Telegram bots and innovative solutions.\n\n"
        "<b>Get in touch:</b>\n"
        "• Telegram: @novastar_dev\n"
        "• Portfolio: novastar-dev.vercel.app\n\n"
        "Feel free to reach out for collaborations, questions, or just to say hi! 😁",
        parse_mode="HTML",
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    waiting_for_text.discard(user_id)
    await update.message.reply_text(
        "❌ *Cancelled*\n\nHere's the menu 👇",
        reply_markup=main_menu_keyboard(), parse_mode="Markdown",
    )

async def error_handler(update, context):
    logger.exception(context.error)

# ============================================================
# MAIN
# ============================================================

def main():
    init_db()

    # ---- Dashboard (same process, same port as the bot) ----
    from dashboard import attach_log_handler, start_dashboard
    attach_log_handler()          # stream bot logs to the dashboard live
    start_dashboard()             # non-blocking; serves on $PORT (default 8080)

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tts", start_tts_command))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("library", library))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("contribute", contribute))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)

    print("🔊 Nova-TTS Bot starting — dashboard + bot on one port")
    print("--------------------------------")
    try:
        app.run_polling(drop_pending_updates=True)
    except KeyboardInterrupt:
        raise
    except Exception:
        logger.exception("Bot crashed — keeping dashboard alive so the error is visible")
        import threading
        from dashboard import _push_log
        _push_log("❌ BOT CRASHED — see logs below. Dashboard is still running.")
        threading.Event().wait()  # block forever, dashboard thread keeps serving

if __name__ == "__main__":
    main()
