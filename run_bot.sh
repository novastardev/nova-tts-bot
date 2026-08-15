#!/usr/bin/env python3
"""Nova-TTS Bot Runner — redirects all bot logs to /var/log/nova-tts.log"""
import os, sys, subprocess

LOG_PATH = '/var/log/nova-tts.log'

# Open log file for appending
log_fd = open(LOG_PATH, 'a')

# Run bot.py and redirect stdout/stderr to log
proc = subprocess.Popen(
    ['venv/bin/python', 'bot.py'],
    stdout=log_fd,
    stderr=log_fd,
    cwd='/opt/baal-agent/workspace/voice_to_speech',
)

print(f"🟢 Bot runner started (PID: {proc.pid})")
print(f"📝 Logs → {LOG_PATH}")

# Wait for bot to exit (it shouldn't)
proc.wait()

log_fd.close()
