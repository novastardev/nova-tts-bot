import io
import logging
import os
import json
import http.server
import socketserver
import threading
import time
from datetime import datetime
from pathlib import Path

# Load .env variables manually
def load_env(path):
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip())
    except:
        pass
load_env(Path(__file__).parent / '.env')

# Timezone config — default UTC, override with TZ env var
TZ = os.environ.get('TZ', 'UTC')
from zoneinfo import ZoneInfo
tz = ZoneInfo(TZ)

# ============================================================
# TELEGRAM BOT IMPORTS
# ============================================================
try:
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
        save_to_library,
        get_library,
        get_library_item,
        delete_from_library,
    )
    from tts import (
        get_voices,
        generate_speech,
    )
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False
    print("⚠️ Telegram dependencies not installed. Dashboard will still work!")

# Log directory for bot logs
LOG_PATH = Path('/var/log/nova-tts.log')

# Log lines for the dashboard
log_lines = []
lastLogCount = 0
bot_username = "nova-tts-bot"

# Access control for the bot
def is_chat_allowed(user_id):
    return user_id in ALLOWED_CHAT_IDS

# ============================================================
# TELEGRAM BOT FUNCTIONS
# ============================================================

# Users who clicked Text to Speech and are expected
# to send text.
waiting_for_text = set()

# Store pending audio data for saving to library
# Format: {user_id: {"text": str, "voice": str, "message_id": int}}
pending_saves = {}

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    try:
        user_id = update.effective_user.id
        if not is_chat_allowed(user_id):
            await update.message.reply_text(
                f"❌ Access Denied\n\n"
                f"Please ask {BOT_OWNER_HANDLE} to grant you access to this bot."
            )
            return
        add_user(user_id)
        keyboard = [
            [
                InlineKeyboardButton(
                    "🎙️ Text to Speech",
                    callback_data="tts",
                )
            ],
            [
                InlineKeyboardButton(
                    "⚙️ Settings",
                    callback_data="settings",
                )
            ],
            [
                InlineKeyboardButton(
                    "📚 My Library",
                    callback_data="library_view",
                )
            ],
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

async def settings(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    try:
        user_id = update.effective_user.id
        add_user(user_id)
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔊 Voice",
                    callback_data="settings_voice",
                )
            ],
        ]
        await update.message.reply_text(
            "⚙️ *Settings*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("SETTINGS ERROR")
        await update.message.reply_text("❌ Unable to open settings.")

async def library(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    try:
        user_id = update.effective_user.id
        add_user(user_id)
        library_items = get_library(user_id, limit=10)
        if not library_items:
            await update.message.reply_text(
                "📚 *Your Library*\n\n"
                "No saved audios yet.\n\n"
                "Generate some text-to-speech and save them to your library!",
                parse_mode="Markdown",
            )
            return
        keyboard = []
        for item in library_items:
            item_id = item[0]
            text = item[1]
            voice = item[2]
            created_at = item[4]
            short_text = text[:30] + "..." if len(text) > 30 else text
            button_text = f"📄 {short_text}"
            keyboard.append([
                InlineKeyboardButton(button_text, callback_data=f"lib:{item_id}")
            ])
        await update.message.reply_text(
            "📚 *Your Library*\n\n"
            "Click any to view details",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("LIBRARY ERROR")
        await update.message.reply_text("❌ Unable to open library.")

async def library_callback(query, user_id):
    try:
        library_items = get_library(user_id, limit=10)
        if not library_items:
            await query.message.reply_text(
                "📚 *Your Library*\n\n"
                "No saved audios yet.\n\n"
                "Generate some text-to-speech and save them to your library!",
                parse_mode="Markdown",
            )
            return
        keyboard = []
        for item in library_items:
            item_id = item[0]
            text = item[1]
            voice = item[2]
            created_at = item[4]
            short_text = text[:30] + "..." if len(text) > 30 else text
            button_text = f"📄 {short_text}"
            keyboard.append([
                InlineKeyboardButton(button_text, callback_data=f"lib:{item_id}")
            ])
        await query.edit_message_text(
            "📚 *Your Library*\n\n"
            "Click any to view details",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("LIBRARY ERROR")
        await query.message.reply_text("❌ Unable to open library.")

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    try:
        user_id = query.from_user.id
        data = query.data
        if not is_chat_allowed(user_id):
            await query.answer(f"Access denied. Ask {BOT_OWNER_HANDLE}", show_alert=True)
            return
        await query.answer()
        add_user(user_id)

        if data == "tts":
            waiting_for_text.add(user_id)
            await query.message.reply_text(
                "📝 *Send the text you want to convert to speech.*",
                parse_mode="Markdown",
            )
            return

        if data == "settings":
            keyboard = [
                [
                    InlineKeyboardButton("🔊 Voice", callback_data="settings_voice"),
                ],
            ]
            await query.edit_message_text(
                "⚙️ *Settings*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )
            return

        if data == "library_view":
            await library_callback(query, user_id)
            return

        if data == "settings_voice":
            await query.edit_message_text("Loading voices...")
            try:
                voices = get_voices()
                if not voices:
                    await query.edit_message_text("No voices available. Contact @novastardev.")
                    return
                keyboard = []
                for v_name, v_voice in voices:
                    keyboard.append([
                        InlineKeyboardButton(v_name, callback_data=f"voice:{v_voice}")
                    ])
                keyboard.append([
                    InlineKeyboardButton("← Back", callback_data="settings"),
                ])
                await query.edit_message_text(
                    "🔊 *Select a Voice*\n\n"
                    "Choose the voice for your text-to-speech.",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown",
                )
            except Exception:
                logger.exception("VOICE LIST ERROR")
                await query.edit_message_text("❌ Unable to load voices.")

        if data.startswith("voice:"):
            selected_voice = data.split(":", 1)[1]
            await query.edit_message_text(
                f"✅ *Voice selected: {selected_voice}*\n\n"
                f"Your voice preference has been updated.",
                parse_mode="Markdown",
            )
            set_voice(user_id, selected_voice)
            return

        if data.startswith("lib:"):
            item_id = data.split(":", 1)[1]
            try:
                item = get_library_item(user_id, int(item_id))
                if not item:
                    await query.answer("Item not found.", show_alert=True)
                    return
                text = item[1]
                voice = item[2]
                created_at = item[4]
                await query.answer()
                keyboard = [
                    [
                        InlineKeyboardButton("🔊 Listen", callback_data=f"play:{item_id}"),
                    ],
                    [
                        InlineKeyboardButton("🗑️ Delete", callback_data=f"del:{item_id}"),
                    ],
                    [
                        InlineKeyboardButton("← Back to Library", callback_data="library_view"),
                    ],
                ]
                await query.edit_message_text(
                    f"📄 *Details*\n\n"
                    f"📝 *Text:* {text}\n\n"
                    f"🔊 *Voice:* {voice}\n\n"
                    f"📅 *Created:* {created_at}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"*NOVA-TTS MONITOR v2.0*\n"
                    f"© 2025 Nova-TTS",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown",
                )
            except Exception:
                logger.exception("LIBRARY ITEM ERROR")
                await query.answer("Error loading item.", show_alert=True)
            return

        if data.startswith("play:"):
            item_id = data.split(":", 1)[1]
            try:
                item = get_library_item(user_id, int(item_id))
                if not item:
                    await query.answer("Item not found.", show_alert=True)
                    return
                audio_file_id = item[3]
                if not audio_file_id:
                    await query.answer("Audio not available.", show_alert=True)
                    return
                await query.answer()
                voice = item[2]
                text = item[1]
                keyboard = [
                    [
                        InlineKeyboardButton("← Back", callback_data=f"lib:{item_id}"),
                    ],
                ]
                await query.message.reply_voice(
                    audio_file_id,
                    caption=f"🔊 *Generated Voice*\n\n📝 *Text:* {text}\n🔊 *Voice:* {voice}\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n*Built by Novastar*\n\nFeel free to reach out for collaborations, questions, or just to say hi! 😁",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown",
                )
            except Exception:
                logger.exception("PLAY ERROR")
                await query.answer("Error playing audio.", show_alert=True)
            return

        if data.startswith("del:"):
            item_id = data.split(":", 1)[1]
            try:
                success = delete_from_library(user_id, int(item_id))
                if success:
                    await query.answer("✅ Deleted!", show_alert=True)
                    await query.edit_message_text(
                        "✅ *Deleted*\n\n"
                        "The item has been removed from your library.",
                        parse_mode="Markdown",
                    )
                else:
                    await query.answer("Item not found.", show_alert=True)
            except Exception:
                logger.exception("DELETE ERROR")
                await query.answer("Error deleting item.", show_alert=True)
            return

    except Exception:
        logger.exception("CALLBACK ERROR")
        await query.answer("Error processing request.", show_alert=True)

async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    try:
        user_id = update.effective_user.id
        user_text = update.message.text
        if user_id in waiting_for_text:
            waiting_for_text.discard(user_id)
            try:
                keyboard = [
                    [
                        InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
                    ],
                ]
                await update.message.reply_text(
                    "⏳ *Generating speech...*",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown",
                )
                voice = get_voice(user_id)
                if not voice:
                    keyboard2 = [
                        [
                            InlineKeyboardButton("Select Voice", callback_data="settings_voice"),
                        ],
                        [
                            InlineKeyboardButton("← Back", callback_data="tts"),
                        ],
                    ]
                    await update.message.reply_text(
                        "⚠️ No voice selected. Please select a voice first!",
                        reply_markup=InlineKeyboardMarkup(keyboard2),
                        parse_mode="Markdown",
                    )
                    return
                result = generate_speech(user_text, voice)
                if result.get("success"):
                    audio = result.get("audio")
                    if audio:
                        await update.message.reply_voice(audio)
                        pending_saves[user_id] = {
                            "text": user_text,
                            "voice": voice,
                            "message_id": update.message.message_id,
                        }
                        keyboard = [
                            [
                                InlineKeyboardButton("💾 Save to Library", callback_data=f"save:{update.message.message_id}"),
                            ],
                            [
                                InlineKeyboardButton("🔊 TTS Again", callback_data="tts"),
                            ],
                        ]
                        await update.message.reply_text(
                            "✅ *Speech generated!*\n\n"
                            "Want to save this to your library?",
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode="Markdown",
                        )
                    else:
                        await update.message.reply_text(
                            "⚠️ No audio received. Please try again."
                        )
                else:
                    error = result.get("error", "Unknown error")
                    await update.message.reply_text(
                        f"❌ Error: {error}\n\n"
                        f"Please try again or contact @novastardev"
                    )
            except Exception:
                logger.exception("TTS ERROR")
                await update.message.reply_text("❌ Something went wrong.")
    except Exception:
        logger.exception("TEXT ERROR")
        await update.message.reply_text("❌ Something went wrong.")

async def error_handler(update, context):
    logger.exception(context.error)

async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    try:
        user_id = update.effective_user.id
        waiting_for_text.discard(user_id)
        keyboard = [
            [
                InlineKeyboardButton("🎙️ Text to Speech", callback_data="tts"),
            ],
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
            ],
            [
                InlineKeyboardButton("📚 My Library", callback_data="library_view"),
            ],
        ]
        await update.message.reply_text(
            "❌ *Cancelled*\n\n"
            "What would you like to do next?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("CANCEL ERROR")
        await update.message.reply_text("❌ Unable to cancel operation.")

# ============================================================
# COLLECT LOGS
# ============================================================

# ============================================================
# LIVE LOGS COLLECTION — reads existing + tails new
# ============================================================
log_lines = []

def collect_logs():
    """Read existing log lines, then follow for new ones"""
    if not LOG_PATH.exists():
        log_lines.append("[SYSTEM] Log file not found — bot may not be running")
        return
    
    # Read existing content
    try:
        with open(LOG_PATH, 'r') as f:
            existing = f.readlines()
            for line in existing:
                line = line.strip()
                if line and not line.startswith('#'):
                    log_lines.append(line)
    except Exception as e:
        log_lines.append(f"[SYSTEM] Error reading log: {e}")
    
    # Now follow for new lines
    try:
        with open(LOG_PATH, 'r') as f:
            # Go to end of file
            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        log_lines.append(line)
                        if len(log_lines) > 500:
                            log_lines.pop(0)
                else:
                    time.sleep(0.5)
    except Exception as e:
        log_lines.append(f"[SYSTEM] Tailing error: {e}")

threading.Thread(target=collect_logs, daemon=True).start()

# ============================================================
# BOT INFO — fetch from getMe API
# ============================================================
bot_username = "@Dice_ff_bot"  # fallback

def fetch_bot_info():
    global bot_username
    try:
        import httpx
        token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
        if token:
            r = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data.get('ok'):
                    bot_username = '@' + data['result']['username']
    except:
        pass

fetch_bot_info()
# Refresh bot info every 5 minutes
def refresh_bot_info_loop():
    while True:
        time.sleep(300)
        fetch_bot_info()

threading.Thread(target=refresh_bot_info_loop, daemon=True).start()

# ============================================================
# HTML PAGE
# ============================================================
def get_html():
    import hashlib
    now_utc = datetime.now(ZoneInfo('UTC')).strftime("%Y-%m-%d %H:%M:%S")
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    # Get offset from strftime %z — returns +0100 for Douala
    tz_str = datetime.now(tz).strftime('%z')  # e.g. '+0100'
    sign = tz_str[:1]  # '+' or '-'
    hours = int(tz_str[1:3])
    offset_str = f'{sign}{hours}h'
    log_html = ""
    for line in log_lines:
        log_html += f'<div class="log-line">{line}</div>'
    
    if not log_lines:
        log_html = '<div class="log-line log-empty">Waiting for bot logs...</div>'
    
    # Cache-busting version — changes every request
    version = hashlib.md5(str(datetime.now().timestamp()).encode()).hexdigest()[:8]
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nova-TTS // System</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #0a0a0f;
    color: #00ff41;
    font-family: 'Share Tech Mono', monospace;
    min-height: 100vh;
    overflow-x: hidden;
  }}
  body::before {{
    content: '';
    position: fixed;
    top: 0; left: 0; width: 100%; height: 100%;
    background: repeating-linear-gradient(
      0deg, rgba(0, 255, 65, 0.03) 0px, rgba(0, 255, 65, 0.03) 1px,
      transparent 1px, transparent 3px
    ));
    pointer-events: none;
    z-index: 1;
  }}
  @keyframes glitch {{
    0%,100% {{ text-shadow: 2px 0 #ff00ff, -2px 0 #00ffff; }}
    25% {{ text-shadow: -2px 0 #ff00ff, 2px 0 #00ffff; }}
    50% {{ text-shadow: 2px 2px #ff00ff, -2px -2px #00ffff; }}
    75% {{ text-shadow: -2px 2px #ff00ff, 2px -2px #00ffff; }}
  }}
  @keyframes pulse {{
    0%,100% {{ opacity: 1; }}
    50% {{ opacity: 0.6; }}
  }}
  .container {{
    max-width: 900px;
    margin: 20px auto;
    padding: 20px;
    border: 1px solid #00ff41;
    border-radius: 4px;
    background: rgba(0, 255, 65, 0.02);
    min-height: calc(100vh - 40px);
    animation: borderGlow 4s infinite;
  }}
  @keyframes borderGlow {{
    0%,100% {{ border-color: #00ff41; box-shadow: 0 0 10px #00ff4144, inset 0 0 10px #00ff4111; }}
    50% {{ border-color: #00ffff; box-shadow: 0 0 20px #00ffff44, inset 0 0 20px #00ffff11; }}
  }}
  .header {{
    text-align: center;
    padding: 30px 0 20px;
    border-bottom: 1px solid #00ff4133;
    margin-bottom: 20px;
  }}
  .header h1 {{
    font-size: 2em;
    letter-spacing: 4px;
    animation: glitch 3s infinite;
    text-transform: uppercase;
  }}
  .header .subtitle {{
    color: #00ffff;
    font-size: 0.8em;
    margin-top: 8px;
    letter-spacing: 2px;
  }}
  .status-panel {{
    background: rgba(0, 255, 65, 0.05);
    border: 1px solid #00ff4155;
    border-radius: 4px;
    padding: 20px;
    margin-bottom: 12px;
  }}
  .status-line {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid #00ff4122;
  }}
  .status-line:last-child {{ border-bottom: none; }}
  .status-label {{ color: #888; font-size: 0.85em; }}
  .status-value {{ color: #00ff41; font-weight: bold; }}
  .status-value.online {{ animation: pulse 2s infinite; }}
  .big-status {{
    text-align: center;
    padding: 30px;
    margin: 20px 0;
    border: 1px solid #00ff41;
    background: rgba(0, 255, 65, 0.08);
    border-radius: 4px;
  }}
  .big-status .icon {{ font-size: 3em; animation: pulse 2s infinite; }}
  .big-status .text {{
    font-size: 1.8em;
    margin-top: 10px;
    animation: glitch 4s infinite;
    letter-spacing: 3px;
  }}
  .logs-section {{ margin-top: 4px; }}
  .logs-section h2 {{
    color: #00ffff;
    font-size: 1em;
    letter-spacing: 2px;
    margin-bottom: 10px;
    text-transform: uppercase;
  }}
  .logs-container {{
    background: #050508;
    border: 1px solid #00ff4133;
    border-radius: 4px;
    padding: 10px;
    max-height: 400px;
    overflow-y: auto;
    font-size: 0.75em;
    line-height: 1.6;
  }}
  .logs-container::-webkit-scrollbar {{ width: 6px; }}
  .logs-container::-webkit-scrollbar-track {{ background: #0a0a0f; }}
  .logs-container::-webkit-scrollbar-thumb {{ background: #00ff41; border-radius: 3px; }}
  .log-line {{
    color: #00ff4199;
    border-left: 2px solid #00ff4133;
    padding-left: 8px;
    margin: 2px 0;
    word-break: break-all;
  }}
  .log-line:hover {{ color: #00ff41; border-left-color: #00ffff; }}
  .log-empty {{ color: #666; font-style: italic; }}
  .delete-btn {{
    background: none;
    border: 1px solid #ff444466;
    color: #ff4444;
    cursor: pointer;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 0.85em;
    transition: all 0.3s ease;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    margin-left: 12px;
    font-family: 'Share Tech Mono', monospace;
  }}
  .delete-btn:hover {{
    background: #ff444422;
    border-color: #ff4444;
    color: #ff6666;
    box-shadow: 0 0 8px #ff444444;
  }}
  .delete-btn:active {{
    transform: scale(0.9);
  }}
  .delete-btn.cleared {{
    color: #00ff41;
    border-color: #00ff41;
    background: #00ff4122;
  }}
  .footer {{
    text-align: center;
    padding: 20px;
    margin-top: 30px;
    border-top: 1px solid #00ff4133;
    color: #444;
    font-size: 0.7em;
    letter-spacing: 1px;
  }}
  .matrix-bg {{
    position: fixed;
    top: 0; left: 0;
    width: 100%; height: 100%;
    z-index: -1;
    opacity: 0.05;
  }}
  @media (max-width: 600px) {{
    .container {{ padding: 10px; margin: 10px; }}
    .header h1 {{ font-size: 1.3em; }}
    .big-status .text {{ font-size: 1.2em; }}
    .logs-container {{ max-height: 250px; font-size: 0.65em; }}
  }}
</style>
</head>
<body>
<canvas class="matrix-bg" id="matrix"></canvas>
<div class="container">
  <div class="header">
    <h1>&#9608; Nova-TTS // System</h1>
    <div class="subtitle">TELEGRAM TEXT-TO-SPEECH BOT // REAL-TIME MONITORING</div>
  </div>
  <div class="big-status">
    <div class="icon">&#9729;</div>
    <div class="text">SYSTEM ONLINE</div>
  </div>
  <div class="status-panel">
    <div class="status-line">
      <span class="status-label">BOT STATUS</span>
      <span class="status-value online">&#9679; ONLINE</span>
    </div>
    <div class="status-line">
      <span class="status-label">BOT USERNAME</span>
      <span class="status-value">{bot_username}</span>
    </div>
    <div class="status-line">
      <span class="status-label">API ENDPOINT</span>
      <span class="status-value">api.telegram.org</span>
    </div>
    <div class="status-line">
      <span class="status-label">DATABASE</span>
      <span class="status-value">SQLite (bot.db)</span>
    </div>
    <div class="status-line">
      <span class="status-label">ACCESS CONTROL</span>
      <span class="status-value warn">WHITELIST ACTIVE</span>
    </div>
    <div class="status-line">
      <span class="status-label">ONLINE AT</span>
      <span class="status-value" id="last-check" style="font-variant-numeric: tabular-nums;">{now} ({TZ}, {offset_str})</span>
    </div>
  </div>
  <div class="logs-section">
    <h2>
      [&#9654;] LIVE BOT LOGS
      <button class="delete-btn" id="clear-btn" title="Clear all logs">✕ Clear</button>
    </h2>
    <div class="logs-container" id="logs">
      {log_html}
    </div>
  </div>
  <div class="footer">
    NOVA-TTS MONITOR v2.0 &#9608; BUILD {now} &#9608; ALL SYSTEMS NOMINAL
  </div>
</div>
<script>
const canvas = document.getElementById('matrix');
const ctx = canvas.getContext('2d');
canvas.width = window.innerWidth;
canvas.height = window.innerHeight;
const chars = '01アイウエオカキクケコサシスセソタチツテトNOVA';
const fontSize = 14;
const columns = Math.floor(canvas.width / fontSize);
const drops = Array(columns).fill(1);
function drawMatrix() {{
  ctx.fillStyle = 'rgba(10, 10, 15, 0.05)';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#00ff41';
  ctx.font = fontSize + 'px monospace';
  for (let i = 0; i < drops.length; i++) {{
    const text = chars[Math.floor(Math.random() * chars.length)];
    ctx.fillText(text, i * fontSize, drops[i] * fontSize);
    if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) drops[i] = 0;
    drops[i]++;
  }}
}}
setInterval(drawMatrix, 50);

// LIVE CLOCK — ticks the server-configured timezone every second
(function() {{
  var el = document.getElementById('last-check');
  if (el) el.textContent = "{now} ({TZ}, {offset_str})";

  function tick() {{
    if (!el) return;
    var now = new Date();
    var h = now.getHours().toString().padStart(2, '0');
    var m = now.getMinutes().toString().padStart(2, '0');
    var s = now.getSeconds().toString().padStart(2, '0');
    el.textContent = h + ':' + m + ':' + s + ' ({TZ}, {offset_str})';
  }}
  tick();
  setInterval(tick, 1000);
}})();

// Smooth log updater only
let lastLogCount = {{ log_lines|length }};
setInterval(function() {{
  fetch('/api/logs?since=' + lastLogCount)
    .then(r => r.json())
    .then(data => {{
      if (data.count > lastLogCount) {{
        const container = document.getElementById('logs');
        for (let i = lastLogCount; i < data.count; i++) {{
          const div = document.createElement('div');
          div.className = 'log-line';
          div.textContent = data.lines[i];
          container.appendChild(div);
        }}
        lastLogCount = data.count;
        container.scrollTop = container.scrollHeight;
      }}
    }})
    .catch(() => {{}});
}}, 2000);

// Delete logs — SIMPLE, CLEAN, WORKS
var clearBtn = document.getElementById('clear-btn');
if (clearBtn) {{
  clearBtn.addEventListener('click', function() {{
    fetch('/api/clear-logs', {{ method: 'POST' }})
      .then(function(r) {{ return r.json(); }})
      .then(function(data) {{
        this.innerHTML = '✓ Cleared!';
        this.classList.add('cleared');
        document.getElementById('logs').innerHTML = '<div class="log-line log-empty">Logs cleared — waiting for new entries...</div>';
        var btn = this;
        setTimeout(function() {{ btn.innerHTML = '✕ Clear'; btn.classList.remove('cleared'); }}, 2000);
      }});
  }});
}}
</script>
<!-- NOVA-CACHE-BUST: {version} -->
</body>
</html>"""

# ============================================================
# HTTP HANDLER
# ============================================================
class CyberHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Smooth log API — returns new logs since index
        if self.path.startswith('/api/logs?since='):
            since = int(self.path.split('=')[1])
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            data = json.dumps({
                "count": len(log_lines),
                "lines": log_lines[since:]
            })
            self.wfile.write(data.encode())
        elif self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            status = json.dumps({
                "status": "online",
                "bot": bot_username,
                "database": "SQLite",
                "access": "whitelist",
                "last_check": datetime.now().isoformat(),
                "uptime": "active",
                "log_lines": len(log_lines)
            })
            self.wfile.write(status.encode())
        elif self.path == '/api/live-time':
            # REAL-TIME CLOCK ENDPOINT — returns current time in configured TZ
            now = datetime.now(tz).strftime("%H:%M:%S")
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            self.send_header('Pragma', 'no-cache')
            self.end_headers()
            self.wfile.write(now.encode())
            self.wfile.write(status.encode())
        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.end_headers()
            html = get_html()
            # Append version hash to force browser to reload
            self.wfile.write(html.encode())
        elif self.path == '/api/clear-logs' and self.command == 'POST':
            # CLEAR ALL LOGS — THIS IS THE BACKEND DELETE
            log_lines.clear()
            lastLogCount = 0
            print("[WEB] Logs cleared via API!")
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "cleared": True}).encode())
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.end_headers()
            self.wfile.write(get_html().encode())
    
    def do_POST(self):
        # Handle /api/clear-logs POST request
        if self.path == '/api/clear-logs':
            log_lines.clear()
            lastLogCount = 0
            print("[WEB] Logs cleared via API!")
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "cleared": True}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        msg = f"[WEB] {datetime.now().strftime('%H:%M:%S')} {format % args}"
        log_lines.append(msg)

# ============================================================
# LOGGER SETUP
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============================================================
# START
# ============================================================
PORT = int(os.environ.get('PORT', 3900))
class ReuseTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

server = ReuseTCPServer(("0.0.0.0", PORT), CyberHandler)
print(f"🟢 Nova-TTS Monitor on port {PORT}")
print(f"📊 Dashboard: http://0.0.0.0:{PORT}/")
print(f"📊 API: http://0.0.0.0:{PORT}/api/status")

# ============================================================
# START TELEGRAM BOT (in a separate thread)
# ============================================================

def run_telegram_bot():
    if not HAS_TELEGRAM:
        print("⚠️ Telegram not installed, skipping bot")
        return
    try:
        from telegram import Bot
        import os
        from pathlib import Path
        init_db(Path("bot.db"))
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
        print("--------------------------------")
        print("🔊 TTS Telegram Bot starting...")
        print("--------------------------------")
        app.run_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
        )
    except Exception as e:
        print(f"❌ Telegram bot error: {e}")
        raise

def run_bot_thread():
    """Run the Telegram bot in a separate thread."""
    try:
        run_telegram_bot()
    except Exception as e:
        print(f"Bot thread error: {e}")

# Start the Telegram bot in a background thread
bot_thread = threading.Thread(target=run_bot_thread, daemon=True)
bot_thread.start()
print("🤖 Telegram bot running in background...")

# Keep the server running
server.serve_forever()
