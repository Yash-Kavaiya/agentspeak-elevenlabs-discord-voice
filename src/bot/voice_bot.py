"""Discord voice bot with Gemini Live API integration."""

import asyncio
import logging
import os
from typing import Optional, Dict, Set
import discord
from discord.ext import commands

from ..gemini_agent.agent import GeminiLiveAgent, ConversationManager
from ..audio.discord_audio_source import GeminiAudioSource
from ..audio.discord_audio_interface import DiscordAudioInterface
from .audio_sink import create_audio_sink, HAS_VOICE_RECV

logger = logging.getLogger(__name__)

# Try to import voice receive extension
try:
    from discord.ext import voice_recv

    VoiceRecvClient = voice_recv.VoiceRecvClient
except ImportError:
    VoiceRecvClient = discord.VoiceClient


class VoiceBot(commands.Bot):
    """
    Discord bot with Gemini Live API integration.

    Automatically joins voice channels when users join and provides
    real-time AI voice conversation capabilities.
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        gemini_model: str = "gemini-2.5-flash-native-audio-preview-12-2025",
        system_instruction: Optional[str] = None,
        auto_join: bool = True,
        greeting_enabled: bool = True,
        greeting_message: str = "Hello! I'm your AI assistant. How can I help you today?",
        **kwargs,
    ):
        """
        Initialize the voice bot.

        Args:
            gemini_api_key: Google AI API key
            gemini_model: Gemini model to use
            system_instruction: Optional system instruction for the agent
            auto_join: Whether to auto-join when users join voice
            greeting_enabled: Whether to greet users when they join
            greeting_message: Custom greeting message
            **kwargs: Additional arguments for commands.Bot
        """
        # Set up intents
        intents = kwargs.pop("intents", discord.Intents.default())
        intents.voice_states = True
        intents.guilds = True
        intents.message_content = True
        intents.members = True  # Needed for voice state member info

        super().__init__(
            command_prefix=kwargs.pop("command_prefix", "!"),
            intents=intents,
            **kwargs,
        )

        self.gemini_api_key = gemini_api_key
        self.gemini_model = gemini_model
        self.system_instruction = system_instruction
        self.auto_join = auto_join
        self.greeting_enabled = greeting_enabled
        self.greeting_message = greeting_message

        # Conversation manager for multiple channels
        self.conversation_manager = ConversationManager(
            api_key=gemini_api_key,
            model=gemini_model,
            system_instruction=system_instruction,
        )

        # Track active voice connections
        self._voice_connections: Dict[int, VoiceRecvClient] = {}
        self._active_conversations: Dict[int, GeminiLiveAgent] = {}
        self._greeted_users: Set[int] = set()

        # Register commands
        self._setup_commands()

    def _setup_commands(self) -> None:
        """Set up bot commands."""

        @self.command(name="join")
        async def join_voice(ctx: commands.Context):
            """Join the user's voice channel."""
            if ctx.author.voice is None:
                await ctx.send("You need to be in a voice channel!")
                return

            channel = ctx.author.voice.channel
            try:
                await self._join_voice_channel(channel)
                await ctx.send(f"Joined {channel.name}!")
            except discord.ClientException:
                await ctx.send("I'm already in a voice channel!")
            except Exception as e:
                await ctx.send(f"Failed to join: {e}")
                logger.error(f"Join error: {e}")

        @self.command(name="leave")
        async def leave_voice(ctx: commands.Context):
            """Leave the current voice channel."""
            if ctx.guild.id in self._voice_connections:
                await self._leave_voice_channel(ctx.guild.id)
                await ctx.send("Left the voice channel!")
            else:
                await ctx.send("I'm not in a voice channel!")

        @self.command(name="ask")
        async def ask_text(ctx: commands.Context, *, question: str):
            """Ask the AI a question via text."""
            if ctx.guild.id not in self._active_conversations:
                await ctx.send("I need to be in a voice channel first! Use `!join`")
                return

            agent = self._active_conversations[ctx.guild.id]
            await agent.send_text(question)
            await ctx.send(f"Processing: {question}")

        @self.command(name="stop")
        async def stop_speaking(ctx: commands.Context):
            """Interrupt the AI while it's speaking."""
            if ctx.guild.id in self._active_conversations:
                agent = self._active_conversations[ctx.guild.id]
                await agent.interrupt()
                await ctx.send("Interrupted!")

        @self.command(name="status")
        async def show_status(ctx: commands.Context):
            """Show bot status."""
            voice_channels = len(self._voice_connections)
            active_convs = len(self._active_conversations)
            await ctx.send(
                f"Voice connections: {voice_channels}\n"
                f"Active conversations: {active_convs}"
            )

    async def on_ready(self) -> None:
        """Called when bot is ready."""
        logger.info(f"Bot is ready! Logged in as {self.user}")
        logger.info(f"Gemini Model: {self.gemini_model}")

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """
        Handle voice state changes (user joins/leaves voice channel).

        Args:
            member: The member whose voice state changed
            before: Previous voice state
            after: New voice state
        """
        # Ignore bot's own voice state changes
        if member.bot:
            return

        # User joined a voice channel
        if before.channel is None and after.channel is not None:
            logger.info(f"{member.name} joined {after.channel.name}")

            if self.auto_join:
                await self._handle_user_join(member, after.channel)

        # User left a voice channel
        elif before.channel is not None and after.channel is None:
            logger.info(f"{member.name} left {before.channel.name}")
            await self._handle_user_leave(member, before.channel)

        # User moved between channels
        elif before.channel != after.channel:
            logger.info(
                f"{member.name} moved from {before.channel.name} to {after.channel.name}"
            )

    async def _handle_user_join(
        self, member: discord.Member, channel: discord.VoiceChannel
    ) -> None:
        """
        Handle a user joining a voice channel.

        Args:
            member: The member who joined
            channel: The voice channel they joined
        """
        guild_id = channel.guild.id

        # Check if we're already in this channel
        if guild_id in self._voice_connections:
            vc = self._voice_connections[guild_id]
            if vc.channel == channel:
                # Already in the same channel, just greet
                if self.greeting_enabled and member.id not in self._greeted_users:
                    await self._greet_user(guild_id, member)
                return

        # Join the channel
        await self._join_voice_channel(channel)

        # Wait a moment for the audio pipeline to be ready
        await asyncio.sleep(1.0)

        # Greet the user
        if self.greeting_enabled:
            await self._greet_user(guild_id, member)

    async def _handle_user_leave(
        self, member: discord.Member, channel: discord.VoiceChannel
    ) -> None:
        """
        Handle a user leaving a voice channel.

        Args:
            member: The member who left
            channel: The voice channel they left
        """
        guild_id = channel.guild.id

        # Check if the channel is now empty (except bot)
        if channel.members == [self.user] or len(channel.members) == 0:
            # Leave if we're alone
            await self._leave_voice_channel(guild_id)

        # Remove from greeted users
        self._greeted_users.discard(member.id)

    async def _join_voice_channel(self, channel: discord.VoiceChannel) -> None:
        """
        Join a voice channel and start conversation.

        Args:
            channel: The voice channel to join
        """
        guild_id = channel.guild.id

        try:
            # Connect to voice channel
            if HAS_VOICE_RECV:
                vc = await channel.connect(cls=VoiceRecvClient, timeout=120)
            else:
                vc = await channel.connect(timeout=120)

            self._voice_connections[guild_id] = vc
            logger.info(f"Connected to voice channel: {channel.name}")

            # Create Gemini Live agent
            audio_interface = DiscordAudioInterface()
            agent = GeminiLiveAgent(
                api_key=self.gemini_api_key,
                model=self.gemini_model,
                audio_interface=audio_interface,
                system_instruction=self.system_instruction,
            )

            # Set up callbacks
            agent.on_agent_speaking(lambda text: logger.info(f"[Agent]: {text}"))
            agent.on_user_speaking(lambda text: logger.info(f"[User]: {text}"))

            # Start the agent session
            await agent.start_session()
            self._active_conversations[guild_id] = agent

            # Set up audio source for playback
            audio_source = GeminiAudioSource(audio_interface.get_output_buffer())
            # Wrap with PCMVolumeTransformer for proper playback
            volume_source = discord.PCMVolumeTransformer(audio_source, volume=1.0)

            # Start playing (this runs in background)
            logger.info(f"Voice client is_playing before: {vc.is_playing()}")
            if not vc.is_playing():
                vc.play(
                    volume_source,
                    after=lambda e: logger.error(f"Player error: {e}") if e else logger.info("Audio playback finished"),
                )
                logger.info(f"Started audio playback, is_playing: {vc.is_playing()}")

            # Set up audio sink for receiving (if available)
            if HAS_VOICE_RECV:
                sink = create_audio_sink(
                    on_audio=lambda data, uid: agent.receive_discord_audio(data, uid)
                )
                vc.listen(sink)
                logger.info("Voice receiving enabled with voice_recv")
            else:
                logger.warning("Voice receive not available - install discord-ext-voice-recv")

            logger.info(f"Gemini conversation started for {channel.name}")

        except Exception as e:
            logger.error(f"Failed to join voice channel: {e}")
            raise

    async def _leave_voice_channel(self, guild_id: int) -> None:
        """
        Leave a voice channel and end conversation.

        Args:
            guild_id: The guild ID to leave
        """
        try:
            # End Gemini conversation
            if guild_id in self._active_conversations:
                agent = self._active_conversations.pop(guild_id)
                await agent.end_session()

            # Disconnect from voice
            if guild_id in self._voice_connections:
                vc = self._voice_connections.pop(guild_id)
                if vc.is_connected():
                    await vc.disconnect()

            logger.info(f"Left voice channel for guild {guild_id}")

        except Exception as e:
            logger.error(f"Error leaving voice channel: {e}")

    async def _greet_user(self, guild_id: int, member: discord.Member) -> None:
        """
        Greet a user who joined the voice channel.

        Args:
            guild_id: The guild ID
            member: The member to greet
        """
        if guild_id not in self._active_conversations:
            return

        agent = self._active_conversations[guild_id]

        # Personalize greeting
        greeting = self.greeting_message.replace("{user}", member.display_name)

        # Send greeting as text input to trigger voice response
        await agent.send_text(greeting)
        self._greeted_users.add(member.id)

        logger.info(f"Greeted {member.name}")

    async def close(self) -> None:
        """Clean up when bot is closing."""
        # End all conversations
        await self.conversation_manager.end_all_conversations()

        # Disconnect from all voice channels
        for guild_id in list(self._voice_connections.keys()):
            await self._leave_voice_channel(guild_id)

        await super().close()


def create_bot(
    gemini_api_key: Optional[str] = None,
    gemini_model: Optional[str] = None,
    system_instruction: Optional[str] = None,
    **kwargs,
) -> VoiceBot:
    """
    Factory function to create a configured VoiceBot.

    Args:
        gemini_api_key: Google AI API key (or from env)
        gemini_model: Gemini model to use (or from env)
        system_instruction: System instruction for the agent (or from env)
        **kwargs: Additional bot configuration

    Returns:
        Configured VoiceBot instance
    """
    api_key = gemini_api_key or os.getenv("GOOGLE_API_KEY")
    model = gemini_model or os.getenv(
        "GEMINI_MODEL",
        "gemini-2.5-flash-native-audio-preview-12-2025"
    )
    instruction = system_instruction or os.getenv("SYSTEM_INSTRUCTION")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY is required")

    return VoiceBot(
        gemini_api_key=api_key,
        gemini_model=model,
        system_instruction=instruction,
        auto_join=os.getenv("AUTO_JOIN_VOICE", "true").lower() == "true",
        greeting_enabled=os.getenv("GREETING_ENABLED", "true").lower() == "true",
        greeting_message=os.getenv(
            "GREETING_MESSAGE",
            "Hello! I'm your AI assistant. How can I help you today?",
        ),
        **kwargs,
    )
