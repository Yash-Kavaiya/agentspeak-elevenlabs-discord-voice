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
        description="ElevenLabs Discord Voice Agent"
    )
    parser.add_argument(
        "--token",
        help="Discord bot token (or set DISCORD_BOT_TOKEN env var)",
    )
    parser.add_argument(
        "--agent-id",
        help="ElevenLabs agent ID (or set ELEVENLABS_AGENT_ID env var)",
    )
    parser.add_argument(
        "--api-key",
        help="ElevenLabs API key (or set ELEVENLABS_API_KEY env var)",
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
    load_dotenv()
    args = parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get configuration from args or environment
    token = args.token or os.getenv("DISCORD_BOT_TOKEN")
    agent_id = args.agent_id or os.getenv("ELEVENLABS_AGENT_ID")
    api_key = args.api_key or os.getenv("ELEVENLABS_API_KEY")

    if not token:
        logger.error("Discord bot token is required")
        sys.exit(1)

    if not agent_id:
        logger.error("ElevenLabs agent ID is required")
        sys.exit(1)

    logger.info("Starting ElevenLabs Discord Voice Agent...")

    try:
        bot = VoiceBot(
            elevenlabs_agent_id=agent_id,
            elevenlabs_api_key=api_key,
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
