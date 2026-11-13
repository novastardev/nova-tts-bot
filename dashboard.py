"""
Nova-TTS Dashboard — self-contained web monitor module.

Embed this in any bot by calling:

    from dashboard import start_dashboard
    start_dashboard()   # non-blocking, serves on $PORT (default 8080)

The dashboard shows live status, the bot username (fetched from Telegram),
system info and a real-time log stream. Logs are collected from:
  - the Python logging system (root logger), and
  - the log file at $NOVA_TTS_LOG (default /var/log/nova-tts.log)
"""

import http.server
import socketserver
import io
import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path

# Timezone config — default UTC, override with TZ env var
TZ = os.environ.get('TZ', 'UTC')
from zoneinfo import ZoneInfo
tz = ZoneInfo(TZ)

# Bot tokens must never be shown on the public dashboard
_TOKEN_RE = re.compile(r"bot\d+:[A-Za-z0-9_-]+")

# Log file for the collector thread
LOG_PATH = Path(os.environ.get('NOVA_TTS_LOG', '/var/log/nova-tts.log'))

# Shared state shown on the dashboard
log_lines = []
bot_username = "nova-tts-bot"

MAX_LOG_LINES = 500


def _push_log(line: str):
    """Append a line to the dashboard log buffer (capped)."""
    log_lines.append(line)
    if len(log_lines) > MAX_LOG_LINES:
        del log_lines[: len(log_lines) - MAX_LOG_LINES]


class DashboardLogHandler(logging.Handler):
    """Feeds Python log records into the dashboard in real time."""

    def emit(self, record):
        try:
            msg = f"{self.format(record)}"
            # Skip repetitive Telegram polling spam
            if "getUpdates" in msg:
                return
            # Mask bot tokens before they reach the dashboard
            msg = _TOKEN_RE.sub("bot***:***", msg)
            _push_log(msg)
        except Exception:
            pass


def attach_log_handler():
    """Start capturing root-logger output into the dashboard."""
    handler = DashboardLogHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"))
    root = logging.getLogger()
    root.addHandler(handler)
    return handler


def collect_logs():
    """Periodically pull lines from the log file (for external runners)."""
    while True:
        try:
            if LOG_PATH.exists():
                lines = LOG_PATH.read_text(errors="replace").strip().splitlines()
                if lines and lines != log_lines:
                    log_lines.clear()
                    for line in lines[-MAX_LOG_LINES:]:
                        _push_log(line)
            threading.Event().wait(10)
        except Exception:
            threading.Event().wait(10)


def fetch_bot_info():
    """Fetch the real bot username from Telegram (runs its own event loop)."""
    global bot_username
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    if not token:
        return
    try:
        import asyncio
        from telegram import Bot
        async def _get_me():
            bot = Bot(token=token)
            info = await bot.get_me()
            await bot.shutdown()
            return info
        info = asyncio.run(_get_me())
        if info:
            bot_username = f"@{info.username}"
    except Exception as e:
        print(f"⚠️ Could not fetch bot info: {e}")


def refresh_bot_info_loop():
    fetch_bot_info()
    while True:
        threading.Event().wait(300)
        fetch_bot_info()


def get_html():
    import hashlib
    now_utc = datetime.now(ZoneInfo('UTC')).strftime("%Y-%m-%d %H:%M:%S")
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    tz_str = datetime.now(tz).strftime('%z')
    sign = tz_str[:1]
    hours = int(tz_str[1:3])
    offset_str = f'{sign}{hours}h'
    log_html = ""
    for line in log_lines:
        log_html += f'<div class="log-line">{line}</div>'
    if not log_lines:
        log_html = '<div class="log-line log-empty">Waiting for bot logs...</div>'
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
  body {{ background: #0a0a0f; color: #00ff41; font-family: 'Share Tech Mono', monospace; min-height: 100vh; overflow-x: hidden; }}
  body::before {{ content: ''; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: repeating-linear-gradient(0deg, rgba(0, 255, 65, 0.03) 0px, rgba(0, 255, 65, 0.03) 1px, transparent 1px, transparent 3px)); pointer-events: none; z-index: 1; }}
  @keyframes glitch {{ 0%,100% {{ text-shadow: 2px 0 #ff00ff, -2px 0 #00ffff; }} 25% {{ text-shadow: -2px 0 #ff00ff, 2px 0 #00ffff; }} 50% {{ text-shadow: 2px 2px #ff00ff, -2px -2px #00ffff; }} 75% {{ text-shadow: -2px 2px #ff00ff, 2px -2px #00ffff; }} }}
  @keyframes pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.6; }} }}
  .container {{ max-width: 900px; margin: 20px auto; padding: 20px; border: 1px solid #00ff41; border-radius: 4px; background: rgba(0, 255, 65, 0.02); min-height: calc(100vh - 40px); animation: borderGlow 4s infinite; }}
  @keyframes borderGlow {{ 0%,100% {{ border-color: #00ff41; box-shadow: 0 0 10px #00ff4144, inset 0 0 10px #00ff4111; }} 50% {{ border-color: #00ffff; box-shadow: 0 0 20px #00ffff44, inset 0 0 20px #00ffff11; }} }}
  .header {{ text-align: center; padding: 30px 0 20px; border-bottom: 1px solid #00ff4133; margin-bottom: 20px; }}
  .header h1 {{ font-size: 2em; letter-spacing: 4px; animation: glitch 3s infinite; text-transform: uppercase; }}
  .header .subtitle {{ color: #00ffff; font-size: 0.8em; margin-top: 8px; letter-spacing: 2px; }}
  .status-panel {{ background: rgba(0, 255, 65, 0.05); border: 1px solid #00ff4155; border-radius: 4px; padding: 20px; margin-bottom: 12px; }}
  .status-line {{ display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #00ff4122; }}
  .status-line:last-child {{ border-bottom: none; }}
  .status-label {{ color: #888; font-size: 0.85em; }}
  .status-value {{ color: #00ff41; font-weight: bold; }}
  .status-value.online {{ animation: pulse 2s infinite; }}
  .big-status {{ text-align: center; padding: 30px; margin: 20px 0; border: 1px solid #00ff41; background: rgba(0, 255, 65, 0.08); border-radius: 4px; }}
  .big-status .icon {{ font-size: 3em; animation: pulse 2s infinite; }}
  .big-status .text {{ font-size: 1.8em; margin-top: 10px; animation: glitch 4s infinite; letter-spacing: 3px; }}
  .logs-section {{ margin-top: 4px; }}
  .logs-section h2 {{ color: #00ffff; font-size: 1em; letter-spacing: 2px; margin-bottom: 10px; text-transform: uppercase; }}
  .logs-container {{ background: #050508; border: 1px solid #00ff4133; border-radius: 4px; padding: 10px; max-height: 400px; overflow-y: auto; font-size: 0.75em; line-height: 1.6; }}
  .logs-container::-webkit-scrollbar {{ width: 6px; }}
  .logs-container::-webkit-scrollbar-track {{ background: #0a0a0f; }}
  .logs-container::-webkit-scrollbar-thumb {{ background: #00ff41; border-radius: 3px; }}
  .log-line {{ color: #00ff4199; border-left: 2px solid #00ff4133; padding-left: 8px; margin: 2px 0; word-break: break-all; }}
  .log-line:hover {{ color: #00ff41; border-left-color: #00ffff; }}
  .log-empty {{ color: #666; font-style: italic; }}
  .delete-btn {{ background: none; border: 1px solid #ff444466; color: #ff4444; cursor: pointer; padding: 3px 8px; border-radius: 4px; font-size: 0.85em; transition: all 0.3s ease; display: inline-flex; align-items: center; gap: 4px; margin-left: 12px; font-family: 'Share Tech Mono', monospace; }}
  .delete-btn:hover {{ background: #ff444422; border-color: #ff4444; color: #ff6666; box-shadow: 0 0 8px #ff444444; }}
  .delete-btn:active {{ transform: scale(0.9); }}
  .delete-btn.cleared {{ color: #00ff41; border-color: #00ff41; background: #00ff4122; }}
  .footer {{ text-align: center; padding: 20px; margin-top: 30px; border-top: 1px solid #00ff4133; color: #444; font-size: 0.7em; letter-spacing: 1px; }}
  .matrix-bg {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: -1; opacity: 0.05; }}
  @media (max-width: 600px) {{ .container {{ padding: 10px; margin: 10px; }} .header h1 {{ font-size: 1.3em; }} .big-status .text {{ font-size: 1.2em; }} .logs-container {{ max-height: 250px; font-size: 0.65em; }} }}
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

class CyberHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api/logs?since='):
            since = int(self.path.split('=')[1])
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            data = json.dumps({"count": len(log_lines), "lines": log_lines[since:]})
            self.wfile.write(data.encode())
        elif self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            status = json.dumps({
                "status": "online", "bot": bot_username, "database": "SQLite",
                "access": "whitelist", "last_check": datetime.now().isoformat(),
                "uptime": "active", "log_lines": len(log_lines)
            })
            self.wfile.write(status.encode())
        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.end_headers()
            html = get_html()
            self.wfile.write(html.encode())
        elif self.path == '/api/clear-logs' and self.command == 'POST':
            log_lines.clear()
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
        if self.path == '/api/clear-logs':
            log_lines.clear()
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
# PUBLIC API
# ============================================================

def start_dashboard(port=None):
    """Start the dashboard web server on a background thread.

    Returns the server. Non-blocking — safe to call before the bot starts.
    """
    port = port or int(os.environ.get('PORT', 8080))

    class ReuseTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    server = ReuseTCPServer(("0.0.0.0", port), CyberHandler)
    threading.Thread(target=server.serve_forever, daemon=True, name="dashboard").start()

    threading.Thread(target=collect_logs, daemon=True, name="log-collector").start()
    threading.Thread(target=refresh_bot_info_loop, daemon=True, name="bot-info").start()

    print(f"🟢 Nova-TTS Dashboard on port {port}")
    print(f"📊 Dashboard: http://0.0.0.0:{port}/")
    print(f"📊 API: http://0.0.0.0:{port}/api/status")
    return server


if __name__ == "__main__":
    # Standalone mode: dashboard only (bot not started)
    logging.basicConfig(level=logging.INFO)
    start_dashboard()
    print("🤖 (dashboard-only mode — run bot.py to serve bot + dashboard together)")
    threading.Event().wait()
