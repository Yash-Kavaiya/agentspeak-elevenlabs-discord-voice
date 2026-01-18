#!/usr/bin/env python3
"""
ElevenLabs Discord Voice Agent

A Discord bot that uses ElevenLabs Conversational AI to provide
real-time voice conversations in Discord voice channels.
"""

import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

from src.bot.voice_bot import create_bot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Reduce noise from discord.py
logging.getLogger("discord").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def validate_environment() -> bool:
    """
    Validate required environment variables are set.

    Returns:
        True if all required variables are set
    """
    required_vars = [
        "DISCORD_BOT_TOKEN",
        "ELEVENLABS_AGENT_ID",
    ]

    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        logger.info("Please copy .env.example to .env and fill in the values")
        return False

    return True


def main():
    """Main entry point."""
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

    logger.info("Starting ElevenLabs Discord Voice Agent...")
    logger.info(f"Agent ID: {os.getenv('ELEVENLABS_AGENT_ID')}")

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
