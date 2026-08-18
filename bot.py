import io
import logging
import os
import threading
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

# ============================================================
# BEAUTIFUL CYBERPUNK HEALTH PAGE
# ============================================================

HEALTH_PAGE = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nova-TTS // Health</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: #0a0a0f;
  color: #00ff41;
  font-family: 'Share Tech Mono', monospace;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
}
.container {
  text-align: center;
  padding: 40px;
  border: 1px solid #00ff41;
  border-radius: 4px;
  background: rgba(0, 255, 65, 0.05);
  animation: glow 3s infinite;
}
@keyframes glow {
  0%, 100% { box-shadow: 0 0 10px #00ff4144, inset 0 0 10px #00ff4111; }
  50% { box-shadow: 0 0 20px #00ffff44, inset 0 0 20px #00ffff11; }
}
h1 { font-size: 2em; letter-spacing: 4px; margin-bottom: 10px; }
h1::before { content: "◆ "; color: #00ffff; }
h1::after { content: " ◆"; color: #00ffff; }
.status {
  font-size: 1.5em;
  margin: 20px 0;
  padding: 20px;
  border: 1px solid #00ff41;
  background: rgba(0, 255, 65, 0.1);
  border-radius: 4px;
}
.status .dot {
  display: inline-block;
  width: 12px; height: 12px;
  background: #00ff41;
  border-radius: 50%;
  animation: pulse 2s infinite;
  margin-right: 10px;
}
@keyframes pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 10px #00ff41; }
  50% { opacity: 0.4; box-shadow: 0 0 3px #00ff41; }
}
.info { color: #888; font-size: 0.8em; margin-top: 15px; }
.footer { margin-top: 30px; color: #444; font-size: 0.7em; }
</style>
</head>
<body>
<div class="container">
  <h1>NOVA-TTS</h1>
  <div class="status"><span class="dot"></span> SYSTEM ONLINE</div>
  <div class="info">TELEGRAM TEXT-TO-SPEECH BOT // HEALTH CHECK</div>
  <div class="footer">NOVA-TTS MONITOR v2.0 ◆ ALL SYSTEMS NOMINAL</div>
</div>
</body>
</html>"""

HEALTH_JSON = json.dumps({
    "status": "online",
    "service": "Nova-TTS",
    "description": "Telegram Text-to-Speech Bot"
})

# ============================================================
# SIMPLE HTTP SERVER (no Flask server, just routes)
# ============================================================

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HEALTH_PAGE.encode())
        elif self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(HEALTH_JSON.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # silence request logs

# Start health server on RENDER PORT in a SEPARATE thread
PORT = int(os.environ.get("PORT", 8080))
http_thread = threading.Thread(
    target=HTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever,
    daemon=True
)
http_thread.start()
print(f"🟢 Health endpoint on port {PORT}")

# ============================================================
# TELEGRAM BOT
# ============================================================

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
)
from database import (
    init_db,
    add_user,
    get_voice,
    set_voice,
    get_library,
    get_library_item,
    delete_from_library,
)
from tts import get_voices, generate_speech

# ============================================================
# BOT LOGIC
# ============================================================

waiting_for_text = set()

def is_chat_allowed(user_id):
    return user_id in ALLOWED_CHAT_IDS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if not is_chat_allowed(user_id):
            await update.message.reply_text(
                f"❌ Access Denied\n\nPlease ask {BOT_OWNER_HANDLE} to grant you access."
            )
            return
        add_user(user_id)
        keyboard = [
            [InlineKeyboardButton("🎙️ Text to Speech", callback_data="tts")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
            [InlineKeyboardButton("📚 My Library", callback_data="library_view")],
        ]
        await update.message.reply_text(
            "🔊 *Text to Speech Bot*\n\n"
            "Convert your text into natural speech with multiple voices.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "*Built by Novastar* 👨‍💻\n\n"
            "A passionate IT developer creating awesome tools.\n"
            "Currently focused on building intelligent Telegram bots and innovative solutions.\n\n"
            "*Get in touch:*\n"
            "• Telegram: @novastar\n"
            "• Portfolio: novastar-dev.vercel.app\n\n"
            "Feel free to reach out for collaborations, questions, or just to say hi! 😁\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
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

async def library(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        add_user(update.effective_user.id)
        items = get_library(update.effective_user.id, limit=10)
        if not items:
            await update.message.reply_text(
                "📚 *Your Library*\n\nNo saved audios yet.", parse_mode="Markdown"
            )
            return
        keyboard = []
        for item in items:
            item_id, text, voice, _, created_at = item
            short = text[:30] + "..." if len(text) > 30 else text
            keyboard.append([InlineKeyboardButton(f"📄 {short}", callback_data=f"lib:{item_id}")])
        await update.message.reply_text(
            "📚 *Your Library*\n\nClick any to view details",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown",
        )
    except Exception:
        logger.exception("LIBRARY ERROR")

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
                "📝 *Send the text you want to convert.*", parse_mode="Markdown"
            )
        elif data == "settings":
            keyboard = [[InlineKeyboardButton("🔊 Voice", callback_data="settings_voice")]]
            await query.edit_message_text("⚙️ *Settings*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        elif data == "library_view":
            await library(update, context)
        elif data == "settings_voice":
            await query.edit_message_text("Loading voices...")
            try:
                voices = get_voices()
                if not voices:
                    await query.edit_message_text("No voices available.")
                    return
                keyboard = []
                for name, voice in voices:
                    keyboard.append([InlineKeyboardButton(name, callback_data=f"voice:{voice}")])
                keyboard.append([InlineKeyboardButton("← Back", callback_data="settings")])
                await query.edit_message_text(
                    "🔊 *Select a Voice*",
                    reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown",
                )
            except Exception:
                logger.exception("VOICE ERROR")
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
            await query.message.reply_voice(item[3], parse_mode="Markdown")
        elif data.startswith("del:"):
            item_id = int(data.split(":", 1)[1])
            delete_from_library(user_id, item_id)
            await query.answer("✅ Deleted", show_alert=True)
    except Exception:
        logger.exception("BUTTON ERROR")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        text = update.message.text
        if user_id not in waiting_for_text:
            return
        waiting_for_text.discard(user_id)

        await update.message.reply_text("⏳ *Generating...*")
        voice = get_voice(user_id)
        if not voice:
            await update.message.reply_text("⚠️ No voice selected. Click Settings → Voice first.")
            return

        result = generate_speech(text, voice)
        if result.get("success") and result.get("audio"):
            await update.message.reply_voice(result["audio"])
        else:
            await update.message.reply_text(f"❌ Error: {result.get('error', 'Unknown')}")
    except Exception:
        logger.exception("TEXT ERROR")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    waiting_for_text.discard(user_id)
    keyboard = [
        [InlineKeyboardButton("🎙️ Text to Speech", callback_data="tts")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
    ]
    await update.message.reply_text(
        "❌ *Cancelled*",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown",
    )

async def error_handler(update, context):
    logger.exception(context.error)

# ============================================================
# MAIN
# ============================================================

def main():
    init_db("bot.db")
    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("library", library))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)

    print("🔊 Nova-TTS Bot starting...")
    print("📊 Health: /health (cyberpunk page!)")
    print("--------------------------------")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
