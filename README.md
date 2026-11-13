<div align="center">

# 🔊 Nova-TTS Bot

**A Telegram text-to-speech bot with a built-in live monitoring dashboard — one process, one port, zero extra setup.**

Send text → get natural AI speech back as audio. Watch your bot live from any browser.

<img src="https://img.shields.io/badge/Python-3.10+-blue.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/Telegram-Bot-green.svg?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram">
<img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge&logoColor=white" alt="License">
<img src="https://img.shields.io/badge/One%20Port-8080-brightgreen.svg?style=for-the-badge" alt="One port">

</div>

---

## ✨ What it does

- 🎙 **Text to Speech** — send any text to the bot in private chat, get an audio file back in seconds (Kokoro AI voices via tts.ai)
- 🗣 **Multiple voices** — dozens of AI voices, English voices first, switch on the fly with inline buttons
- 📚 **Voice library** — every speech you generate is saved in SQLite and replayable anytime
- 📊 **Live dashboard** — auto-starts with the bot: real-time logs, status, bot username, uptime — terminal-green hacker style
- 🔒 **Whitelist access** — only user IDs you approve can use the bot
- 🚑 **Crash-proof dashboard** — if the bot token is wrong, the dashboard *stays up* and shows you the error instead of dying silently
- 🛡 **Secret-safe** — bot tokens are automatically masked before anything is shown on the dashboard

## ⚡ Quick deploy

The whole thing is **one command** — the dashboard starts automatically with the bot:

```bash
python bot.py
```

That's it. Bot + dashboard on the same port (`8080`, or set `PORT`).

---

## 🚀 Deploy on Render (free, no server needed)

1. Fork or push this repo to your GitHub
2. Go to [Render.com](https://render.com) → **New** → **Web Service** → connect the repo
3. Render picks up `render.yaml` automatically (start command: `python bot.py`)
4. Add your environment variables (table below)
5. Deploy — done ✅

Your dashboard will be live at `https://your-service.onrender.com/`

> ⚠️ Free Render instances sleep after inactivity — your bot goes quiet until the next request wakes it. The dashboard will show it sleeping.

## 🖥 Deploy on your own VPS (systemd)

```bash
git clone https://github.com/novastardev/nova-tts-bot.git
cd nova-tts-bot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env        # fill in your values
```

Create `/etc/systemd/system/nova-tts.service`:

```ini
[Unit]
Description=Nova TTS Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/nova-tts-bot
Environment=PORT=8080
ExecStart=/opt/nova-tts-bot/venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nova-tts
sudo systemctl status nova-tts       # should be active (running)
```

**Optional — HTTPS with Caddy** (one snippet, no config bloat):

```caddy
# /etc/caddy/conf.d/nova-tts.caddy
handle_path /nova-tts/* {
    reverse_proxy localhost:8080
}
```

Then `sudo systemctl reload caddy` — dashboard live at `https://yourdomain.com/nova-tts/`

---

## ⚙️ Configuration

`cp .env.example .env` and fill in:

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | ✅ | Bot token from [@BotFather](https://t.me/BotFather) | `7777777777:AAF...` |
| `TTS_API_KEY` | ✅ | API key from [tts.ai](https://tts.ai) | `sk-...` |
| `ALLOWED_CHAT_IDS` | ✅ | JSON array of allowed Telegram user IDs | `[123456789, 987654321]` |
| `BOT_OWNER_HANDLE` | ✅ | Your Telegram username (shown in bot messages) | `@yourname` |
| `PORT` | ❌ | Dashboard port (default `8080`) | `8080` |
| `TZ` | ❌ | Dashboard clock timezone (default UTC) | `Africa/Lagos` |

### Getting your user ID

1. Send `/start` to your bot on Telegram
2. Open `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Find your `"id": 123456789` in the response
4. Put it in `ALLOWED_CHAT_IDS`

---

## 🤖 Bot commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message + access check |
| `/tts` | Start a text-to-speech conversion |
| `/settings` | Pick your voice with inline buttons |
| `/library` | Browse and replay your saved speeches |
| `/stats` | Usage stats (owner only) |
| `/about` | About the bot |
| `/contribute` | How to support the project |
| `/cancel` | Cancel the current action |

**Using `/tts`:** send `/tts` → send your text → wait a few seconds → get your audio 🎧 Replay anything later from `/library`.

## 📊 Dashboard endpoints

| Path | Description |
|------|-------------|
| `/` | Live dashboard — status, bot info, real-time log stream |
| `/api/status` | JSON health check (`GET`) |
| `/api/logs?since=N` | Log lines since index N (used for live streaming) |
| `/api/clear-logs` | Clear the log buffer (`POST`) |

## 📁 Project structure

```
nova-tts-bot/
├── bot.py              # 🚀 Main entry point: Telegram bot + dashboard (one port)
├── dashboard.py        # 📊 Self-contained web dashboard module
├── tts_monitor.py      # ↪️ Legacy shim (forwards to bot.py)
├── config.py           # ⚙️ Loads and validates .env
├── tts.py              # 🎙 tts.ai API client (Kokoro voices)
├── database.py         # 💾 SQLite storage (users, voices, library)
├── requirements.txt
├── render.yaml         # ☁️ Render.com blueprint
├── Procfile
└── LICENSE             # MIT
```

## 🐛 Troubleshooting

| Problem | Fix |
|---------|-----|
| Dashboard up, bot not responding | Token invalid — the dashboard shows the exact error. Check `TELEGRAM_BOT_TOKEN` |
| "TELEGRAM_BOT_TOKEN is missing" | `.env` file not created or not in the working directory |
| `401 Unauthorized` from Telegram | Token is wrong or was revoked — get a fresh one from @BotFather |
| Port already in use | Another process holds `PORT` — change it or kill the process |
| Audio not generated | Check `TTS_API_KEY` and your tts.ai quota |
| User gets "not authorized" | Their ID isn't in `ALLOWED_CHAT_IDS` — add it and restart |

---

## 🛠 Built with

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) — Telegram bot framework
- [tts.ai](https://tts.ai) — AI voice generation (Kokoro)
- Python stdlib `http.server` — zero-dependency dashboard

## 👤 Credits

**Built with 💛 by [Novastar.dev](https://github.com/novastardev)** (Olarinde Isaiah)

Teenage developer from Lagos, Nigeria — building AI tools, bots and web platforms.
Check out my other projects:

- 🌐 [Portfolio](https://novastar-dev.vercel.app)
- ⚡ [NovaStack](https://app-novastack.vercel.app) — OpenAI-compatible AI API platform
- 💬 Telegram: [@novastar_dev](https://t.me/novastar_dev)

If this repo helped you, **a star would make my day** ⭐

## 📄 License

[MIT](LICENSE) — free to use, modify and deploy. Just don't sell it as-is and call it yours 😉
