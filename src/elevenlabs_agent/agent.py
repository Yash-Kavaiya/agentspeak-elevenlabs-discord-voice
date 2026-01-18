"""High-level ElevenLabs Conversational AI agent wrapper."""

import asyncio
import logging
from typing import Callable, Optional, Dict, Any
from .websocket_client import ElevenLabsWebSocketClient
from ..audio.discord_audio_interface import DiscordAudioInterface

logger = logging.getLogger(__name__)


class ElevenLabsAgent:
    """
    High-level wrapper for ElevenLabs Conversational AI.

    This class provides an easy-to-use interface for managing conversations
    with ElevenLabs AI agents, including audio streaming and event handling.
    """

    def __init__(
        self,
        agent_id: str,
        api_key: Optional[str] = None,
        audio_interface: Optional[DiscordAudioInterface] = None,
    ):
        """
        Initialize the ElevenLabs agent.

        Args:
            agent_id: ElevenLabs agent ID (from the ElevenLabs dashboard)
            api_key: Optional API key for private agents
            audio_interface: Optional custom audio interface
        """
        self.agent_id = agent_id
        self.api_key = api_key
        self.audio_interface = audio_interface or DiscordAudioInterface()

        self._ws_client: Optional[ElevenLabsWebSocketClient] = None
        self._is_active = False
        self._audio_send_task: Optional[asyncio.Task] = None

        # Event callbacks
        self._on_agent_speaking: Optional[Callable[[str], None]] = None
        self._on_user_speaking: Optional[Callable[[str], None]] = None
        self._on_connected: Optional[Callable[[], None]] = None
        self._on_disconnected: Optional[Callable[[], None]] = None
        self._on_error: Optional[Callable[[Exception], None]] = None

    @property
    def is_active(self) -> bool:
        """Check if the agent session is active."""
        return self._is_active

    @property
    def conversation_id(self) -> Optional[str]:
        """Get the current conversation ID."""
        if self._ws_client:
            return self._ws_client.conversation_id
        return None

    def on_agent_speaking(self, callback: Callable[[str], None]) -> None:
        """
        Set callback for when agent speaks.

        Args:
            callback: Function receiving the agent's text
        """
        self._on_agent_speaking = callback

    def on_user_speaking(self, callback: Callable[[str], None]) -> None:
        """
        Set callback for when user speech is transcribed.

        Args:
            callback: Function receiving the user's text
        """
        self._on_user_speaking = callback

    def on_connected(self, callback: Callable[[], None]) -> None:
        """Set callback for when connected to ElevenLabs."""
        self._on_connected = callback

    def on_disconnected(self, callback: Callable[[], None]) -> None:
        """Set callback for when disconnected from ElevenLabs."""
        self._on_disconnected = callback

    def on_error(self, callback: Callable[[Exception], None]) -> None:
        """Set callback for errors."""
        self._on_error = callback

    async def start_session(self) -> bool:
        """
        Start a conversation session with ElevenLabs.

        Returns:
            True if session started successfully
        """
        if self._is_active:
            logger.warning("Session already active")
            return True

        try:
            # Create WebSocket client
            self._ws_client = ElevenLabsWebSocketClient(
                agent_id=self.agent_id,
                api_key=self.api_key,
                on_audio=self._handle_agent_audio,
                on_transcript=self._handle_transcript,
                on_error=self._handle_error,
                on_connected=self._handle_connected,
                on_disconnected=self._handle_disconnected,
            )

            # Connect to ElevenLabs
            connected = await self._ws_client.connect()
            if not connected:
                return False

            # Start audio interface
            self.audio_interface.start(self._send_audio_to_elevenlabs)

            self._is_active = True
            logger.info("ElevenLabs agent session started")
            return True

        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            if self._on_error:
                self._on_error(e)
            return False

    async def end_session(self) -> None:
        """End the current conversation session."""
        self._is_active = False

        # Stop audio interface
        self.audio_interface.stop()

        # Cancel audio send task
        if self._audio_send_task:
            self._audio_send_task.cancel()
            try:
                await self._audio_send_task
            except asyncio.CancelledError:
                pass

        # Disconnect WebSocket
        if self._ws_client:
            await self._ws_client.disconnect()
            self._ws_client = None

        logger.info("ElevenLabs agent session ended")

    async def send_text(self, text: str) -> None:
        """
        Send text input to the agent.

        Args:
            text: Text message to send
        """
        if self._ws_client and self._is_active:
            await self._ws_client.send_text(text)

    async def interrupt(self) -> None:
        """Interrupt the current agent response."""
        if self._ws_client:
            await self._ws_client.interrupt()
        self.audio_interface.interrupt()

    def receive_discord_audio(self, pcm_data: bytes, user_id: int) -> None:
        """
        Receive audio from Discord.

        Args:
            pcm_data: PCM audio data from Discord
            user_id: Discord user ID
        """
        self.audio_interface.receive_discord_audio(pcm_data, user_id)

    def _send_audio_to_elevenlabs(self, audio_data: bytes) -> None:
        """
        Send audio to ElevenLabs (called by audio interface).

        Args:
            audio_data: Converted audio data for ElevenLabs
        """
        if self._ws_client and self._is_active:
            # Schedule async send
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._ws_client.send_audio(audio_data))
            except RuntimeError:
                # No running loop, skip
                pass

    def _handle_agent_audio(self, audio_data: bytes) -> None:
        """
        Handle audio received from ElevenLabs agent.

        Args:
            audio_data: PCM audio data from agent
        """
        # Pass to audio interface for Discord playback
        self.audio_interface.output(audio_data)

    def _handle_transcript(self, role: str, text: str) -> None:
        """
        Handle transcript from ElevenLabs.

        Args:
            role: 'user' or 'agent'
            text: Transcript text
        """
        logger.info(f"[{role}]: {text}")

        if role == "agent" and self._on_agent_speaking:
            self._on_agent_speaking(text)
        elif role == "user" and self._on_user_speaking:
            self._on_user_speaking(text)

    def _handle_connected(self) -> None:
        """Handle WebSocket connection established."""
        if self._on_connected:
            self._on_connected()

    def _handle_disconnected(self) -> None:
        """Handle WebSocket disconnection."""
        self._is_active = False
        if self._on_disconnected:
            self._on_disconnected()

    def _handle_error(self, error: Exception) -> None:
        """
        Handle error from WebSocket.

        Args:
            error: Exception that occurred
        """
        logger.error(f"ElevenLabs error: {error}")
        if self._on_error:
            self._on_error(error)


class ConversationManager:
    """
    Manages multiple conversations across different Discord channels.

    This allows running separate ElevenLabs conversations for each
    Discord voice channel or user.
    """

    def __init__(self, agent_id: str, api_key: Optional[str] = None):
        """
        Initialize the conversation manager.

        Args:
            agent_id: Default ElevenLabs agent ID
            api_key: Optional API key
        """
        self.agent_id = agent_id
        self.api_key = api_key
        self._conversations: Dict[int, ElevenLabsAgent] = {}

    async def get_or_create_conversation(
        self, channel_id: int
    ) -> ElevenLabsAgent:
        """
        Get or create a conversation for a channel.

        Args:
            channel_id: Discord channel ID

        Returns:
            ElevenLabsAgent instance
        """
        if channel_id not in self._conversations:
            agent = ElevenLabsAgent(
                agent_id=self.agent_id,
                api_key=self.api_key,
            )
            self._conversations[channel_id] = agent

        return self._conversations[channel_id]

    async def end_conversation(self, channel_id: int) -> None:
        """
        End a conversation for a channel.

        Args:
            channel_id: Discord channel ID
        """
        if channel_id in self._conversations:
            agent = self._conversations.pop(channel_id)
            await agent.end_session()

    async def end_all_conversations(self) -> None:
        """End all active conversations."""
        for agent in self._conversations.values():
            await agent.end_session()
        self._conversations.clear()

    def get_active_conversations(self) -> Dict[int, ElevenLabsAgent]:
        """Get all active conversations."""
        return {k: v for k, v in self._conversations.items() if v.is_active}
