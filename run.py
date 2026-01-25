#!/usr/bin/env python3
"""
Alternative entry point with more configuration options.

This script provides additional CLI arguments for testing and development.
"""

import argparse
import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

from src.bot.voice_bot import VoiceBot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Gemini Discord Voice Agent"
    )
    parser.add_argument(
        "--token",
        help="Discord bot token (or set DISCORD_BOT_TOKEN env var)",
    )
    parser.add_argument(
        "--api-key",
        help="Google API key (or set GOOGLE_API_KEY env var)",
    )
    parser.add_argument(
        "--model",
        default="gemini-2.5-flash-native-audio-preview-12-2025",
        help="Gemini model to use (or set GEMINI_MODEL env var)",
    )
    parser.add_argument(
        "--no-auto-join",
        action="store_true",
        help="Disable auto-joining voice channels",
    )
    parser.add_argument(
        "--no-greeting",
        action="store_true",
        help="Disable greeting message when users join",
    )
    parser.add_argument(
        "--greeting",
        default="Hello! I'm your AI assistant. How can I help you today?",
        help="Custom greeting message",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--prefix",
        default="!",
        help="Command prefix (default: !)",
    )
    return parser.parse_args()


def main():
    """Main entry point with CLI arguments."""
    # Load Opus library for voice support
    import discord
    import discord.opus
    if not discord.opus.is_loaded():
        try:
            opus_path = os.path.join(
                os.path.dirname(discord.__file__),
                'bin',
                'libopus-0.x64.dll'
            )
            discord.opus.load_opus(opus_path)
            logger.info("Opus library loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load Opus library: {e}")

    load_dotenv()
    args = parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get configuration from args or environment
    token = args.token or os.getenv("DISCORD_BOT_TOKEN")
    api_key = args.api_key or os.getenv("GOOGLE_API_KEY")
    model = args.model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025")

    if not token:
        logger.error("Discord bot token is required")
        sys.exit(1)

    if not api_key:
        logger.error("Google API key is required")
        sys.exit(1)

    logger.info("Starting Gemini Discord Voice Agent...")
    logger.info(f"Model: {model}")

    try:
        bot = VoiceBot(
            gemini_api_key=api_key,
            gemini_model=model,
            auto_join=not args.no_auto_join,
            greeting_enabled=not args.no_greeting,
            greeting_message=args.greeting,
            command_prefix=args.prefix,
        )

        bot.run(token)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
