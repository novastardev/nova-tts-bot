from setuptools import setup, find_packages

setup(
    name="nova-tts-bot",
    version="1.0.0",
    description="Telegram voice bot with live monitor dashboard",
    author="Novastar",
    author_email="your@email.com",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "flask==3.0.0",
        "python-telegram-bot==21.0",
        "httpx==0.27.0",
        "aiohttp==3.9.0",
        "requests==2.31.0",
        "python-dotenv==1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "nova-tts=bot:main",
        ],
    },
)
