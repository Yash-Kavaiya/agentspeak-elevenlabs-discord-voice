#!/usr/bin/env python3
"""
Gemini Discord Voice Agent

A Discord bot that uses Google Gemini Live API to provide
real-time voice conversations in Discord voice channels.
"""

import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

from src.bot.voice_bot import create_bot

# Configure logging - output to both console and file
log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to capture all logs
    format=log_format,
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot_debug.log", mode='w', encoding='utf-8')
    ]
)

# Reduce noise from discord.py
logging.getLogger("discord").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def validate_environment() -> bool:
    """
    Validate required environment variables are set.

    Returns:
        True if all required variables are set
    """
    required_vars = [
        "DISCORD_BOT_TOKEN",
        "GOOGLE_API_KEY",
    ]

    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        logger.info("Please copy .env.example to .env and fill in the values")
        return False

    return True


def main():
    """Main entry point."""
    # Load Opus library for voice support
    import discord.opus
    if not discord.opus.is_loaded():
        try:
            # Try to load from discord.py's bundled opus
            import os as _os
            opus_path = _os.path.join(
                _os.path.dirname(discord.__file__),
                'bin',
                'libopus-0.x64.dll'
            )
            discord.opus.load_opus(opus_path)
            logger.info("Opus library loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load Opus library: {e}")
            logger.warning("Voice features may not work properly")
    
    # Load environment variables
    load_dotenv()

    # Enable debug logging if requested
    if os.getenv("DEBUG", "false").lower() == "true":
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("discord").setLevel(logging.DEBUG)

    # Validate environment
    if not validate_environment():
        sys.exit(1)

    # Get Discord token
    discord_token = os.getenv("DISCORD_BOT_TOKEN")

    logger.info("Starting Gemini Discord Voice Agent...")
    logger.info(f"Model: {os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-native-audio-preview-12-2025')}")

    try:
        # Create the bot
        bot = create_bot()

        # Run the bot
        bot.run(discord_token)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
