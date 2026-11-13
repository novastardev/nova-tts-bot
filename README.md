<div align="center">

# Nova-TTS Bot

**A Telegram text-to-speech bot with a built-in live monitoring dashboard — one process, one port, zero extra setup.**

Send text, get natural AI speech back as audio. Watch your bot live from any browser.

<img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/Telegram-Bot-green.svg?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram">
<img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge" alt="License">
<img src="https://img.shields.io/badge/One%20Port-8080-brightgreen.svg?style=for-the-badge" alt="One port">

</div>

---

## <img src="https://api-novastack.vercel.app/v1/icons/asset?path=/icons/icon/sparkle.svg&style=fill&color=10b981" width="22" valign="middle"> What it does

| | |
|---|---|
| <img src="https://api-novastack.vercel.app/v1/icons/asset?path=/icons/icon/speaker-high.svg&style=fill&color=10b981" width="18" valign="middle"> **Text to Speech** | Send any text to the bot in private chat, get an audio file back in seconds (Kokoro AI voices via tts.ai) |
| <img src="https://api-novastack.vercel.app/v1/icons/asset?path=/icons/icon/waveform.svg&style=fill&color=10b981" width="18" valign="middle"> **Multiple voices** | Dozens of AI voices, English voices first, switch on the fly with inline buttons |
| <img src="https://api-novastack.vercel.app/v1/icons/asset?path=/icons/icon/book-bookmark.svg&style=fill&color=10b981" width="18" valign="middle"> **Voice library** | Every speech you generate is saved in SQLite and replayable anytime |
| <img src="https://api-novastack.vercel.app/v1/icons/asset?path=/icons/icon/monitor.svg&style=fill&color=10b981" width="18" valign="middle"> **Live dashboard** | Auto-starts with the bot: real-time logs, status, bot username, uptime |
| <img src="https://api-novastack.vercel.app/v1/icons/asset?path=/icons/icon/shield-check.svg&style=fill&color=10b981" width="18" valign="middle"> **Whitelist access** | Only user IDs you approve can use the bot |
| <img src="https://api-novastack.vercel.app/v1/icons/asset?path=/icons/icon/lifebuoy.svg&style=fill&color=10b981" width="18" valign="middle"> **Crash-proof dashboard** | If the bot token is wrong, the dashboard stays up and shows you the error instead of dying silently |
| <img src="https://api-novastack.vercel.app/v1/icons/asset?path=/icons/icon/eye-slash.svg&style=fill&color=10b981" width="18" valign="middle"> **Secret-safe** | Bot tokens are automatically masked before anything is shown on the dashboard |

## <img src="https://api-novastack.vercel.app/v1/icons/asset?path=/icons/icon/lightning.svg&style=fill&color=f59e0b" width="22" valign="middle"> Quick deploy

The whole thing is one command — the dashboard starts automatically with the bot:

```bash
python bot.py
```

That's it. Bot + dashboard on the same port (`8080`, or set `PORT`).

---

## <img src="https://api-novastack.vercel.app/v1/icons/asset?path=/icons/icon/cloud-arrow-up.svg&style=fill&color=3b82f6" width="22" valign="middle"> Deploy on Render (free, no server needed)

1. Fork or push this repo to your GitHub
2. Go to [Render.com](https://render.com), then **New** > **Web Service**, and connect the repo
3. Render picks up `render.yaml` automatically (start command: `python bot.py`)
4. Add your environment variables (table below)
5. Deploy — done

Your dashboard will be live at `https://your-service.onrender.com/`

> **Note:** free Render instances sleep after inactivity — your bot goes quiet until the next request wakes it. The dashboard will show it sleeping.

## <img src="https://api-novastack.vercel.app/v1/icons/asset?path=/icons/icon/hard-drives.svg&style=fill&color=3b82f6" width="22" valign="middle"> Deploy on your own VPS (systemd)

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

## <img src="https://api-novastack.vercel.app/v1/icons/asset?path=/icons/icon/gear-six.svg&style=fill&color=8b5cf6" width="22" valign="middle"> Configuration

`cp .env.example .env` and fill in:

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from [@BotFather](https://t.me/BotFather) | `7777777777:AAF...` |
| `TTS_API_KEY` | Yes | API key from [tts.ai](https://tts.ai) | `sk-...` |
| `ALLOWED_CHAT_IDS` | Yes | JSON array of allowed Telegram user IDs | `[123456789, 987654321]` |
| `BOT_OWNER_HANDLE` | Yes | Your Telegram username (shown in bot messages) | `@yourname` |
| `PORT` | No | Dashboard port (default `8080`) | `8080` |
| `TZ` | No | Dashboard clock timezone (default UTC) | `Africa/Lagos` |

### Getting your user ID

1. Send `/start` to your bot on Telegram
2. Open `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Find your `"id": 123456789` in the response
4. Put it in `ALLOWED_CHAT_IDS`

---

## <img src="https://api-novastack.vercel.app/v1/icons/asset?path=/icons/brands/telegram.svg&style=fill&color=229ED9" width="22" valign="middle"> Bot commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and access check |
| `/tts` | Start a text-to-speech conversion |
| `/settings` | Pick your voice with inline buttons |
| `/library` | Browse and replay your saved speeches |
| `/stats` | Usage stats (owner only) |
| `/about` | About the bot |
| `/contribute` | How to support the project |
| `/cancel` | Cancel the current action |

**Using `/tts`:** send `/tts`, send your text, wait a few seconds, get your audio. Replay anything later from `/library`.

## <img src="https://api-novastack.vercel.app/v1/icons/asset?path=/icons/icon/pulse.svg&style=fill&color=ef4444" width="22" valign="middle"> Dashboard endpoints

| Path | Description |
|------|-------------|
| `/` | Live dashboard — status, bot info, real-time log stream |
| `/api/status` | JSON health check (`GET`) |
| `/api/logs?since=N` | Log lines since index N (used for live streaming) |
| `/api/clear-logs` | Clear the log buffer (`POST`) |

## <img src="https://api-novastack.vercel.app/v1/icons/asset?path=/icons/icon/tree-structure.svg&style=fill&color=64748b" width="22" valign="middle"> Project structure

```
nova-tts-bot/
├── bot.py              # Main entry point: Telegram bot + dashboard (one port)
├── dashboard.py        # Self-contained web dashboard module
├── tts_monitor.py      # Legacy shim (forwards to bot.py)
├── config.py           # Loads and validates .env
├── tts.py              # tts.ai API client (Kokoro voices)
├── database.py         # SQLite storage (users, voices, library)
├── requirements.txt
├── render.yaml         # Render.com blueprint
├── Procfile
└── LICENSE             # MIT
```

## <img src="https://api-novastack.vercel.app/v1/icons/asset?path=/icons/icon/wrench.svg&style=fill&color=64748b" width="22" valign="middle"> Troubleshooting

| Problem | Fix |
|---------|-----|
| Dashboard up, bot not responding | Token invalid — the dashboard shows the exact error. Check `TELEGRAM_BOT_TOKEN` |
| "TELEGRAM_BOT_TOKEN is missing" | `.env` file not created or not in the working directory |
| `401 Unauthorized` from Telegram | Token is wrong or was revoked — get a fresh one from @BotFather |
| Port already in use | Another process holds `PORT` — change it or kill the process |
| Audio not generated | Check `TTS_API_KEY` and your tts.ai quota |
| User gets "not authorized" | Their ID isn't in `ALLOWED_CHAT_IDS` — add it and restart |

---

## <img src="https://api-novastack.vercel.app/v1/icons/asset?path=/icons/icon/stack.svg&style=fill&color=64748b" width="22" valign="middle"> Built with

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) — Telegram bot framework
- [tts.ai](https://tts.ai) — AI voice generation (Kokoro)
- Python stdlib `http.server` — zero-dependency dashboard
- [NovaStack Icons](https://api-novastack.vercel.app) — the icons in this README are served live from my own icons API

## <img src="https://api-novastack.vercel.app/v1/icons/asset?path=/icons/icon/user-circle.svg&style=fill&color=ec4899" width="22" valign="middle"> Credits

**Built by [Novastar.dev](https://github.com/novastardev)** (Olarinde Isaiah)

Teenage developer from Lagos, Nigeria — building AI tools, bots and web platforms. Check out my other projects:

- [Portfolio](https://novastar-dev.vercel.app) — my personal site
- [NovaStack](https://app-novastack.vercel.app) — OpenAI-compatible AI API platform (the icons API powering this README is part of it)
- Telegram: [@novastar_dev](https://t.me/novastar_dev)

If this repo helped you, a star would make my day.

## <img src="https://api-novastack.vercel.app/v1/icons/asset?path=/icons/icon/scales.svg&style=fill&color=64748b" width="22" valign="middle"> License

[MIT](LICENSE) — free to use, modify and deploy.
