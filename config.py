import os
import json
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TTS_API_KEY = os.getenv("TTS_API_KEY")
BOT_OWNER_HANDLE = os.getenv("BOT_OWNER_HANDLE", "@novastardev")

# --- Access mode ---
# PUBLIC_MODE=true  -> anyone can use the bot
# PUBLIC_MODE=false -> only chat IDs in ALLOWED_CHAT_IDS can use it
PUBLIC_MODE = os.getenv("PUBLIC_MODE", "false").strip().lower() in ("true", "1", "yes")

ALLOWED_CHAT_IDS = os.getenv("ALLOWED_CHAT_IDS", "[]")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing from .env")

if not TTS_API_KEY:
    raise RuntimeError("TTS_API_KEY is missing from .env")

# Parse allowed chat IDs from JSON (only strictly needed in private mode)
try:
    ALLOWED_CHAT_IDS = json.loads(ALLOWED_CHAT_IDS)
except (json.JSONDecodeError, ValueError):
    ALLOWED_CHAT_IDS = []

if not PUBLIC_MODE and not ALLOWED_CHAT_IDS:
    raise RuntimeError(
        "PRIVATE mode requires ALLOWED_CHAT_IDS in .env "
        "(e.g., [123456789]) — or set PUBLIC_MODE=true"
    )

# Owner chat id (optional; used for new-user notifications & /stats)
try:
    OWNER_CHAT_ID = int(OWNER_CHAT_ID) if OWNER_CHAT_ID else None
except ValueError:
    OWNER_CHAT_ID = None

# --- Public-mode limits (protect your TTS credits) ---
MAX_TEXT_LENGTH = int(os.getenv("MAX_TEXT_LENGTH", "500"))      # chars per request
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "15"))     # between requests
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "10"))               # generations per user/day
