"""
Legacy entry point — kept for backwards compatibility.

The dashboard now lives in dashboard.py and bot.py starts it automatically,
so bot.py alone gives you bot + dashboard on ONE port:

    python bot.py

This file just forwards to that.
"""
from bot import main

if __name__ == "__main__":
    main()
