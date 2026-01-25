"""High-level Gemini Live API agent wrapper for Discord voice."""

import asyncio
import logging
import base64
from typing import Callable, Optional, Dict, Any

from google import genai
from google.genai import types

from ..audio.discord_audio_interface import DiscordAudioInterface

logger = logging.getLogger(__name__)

# Model for native audio (December 2025 preview)
GEMINI_LIVE_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"


class GeminiLiveAgent:
    """
    High-level wrapper for Gemini Live API with native audio.

    This class provides an easy-to-use interface for managing real-time
    voice conversations with Gemini using bidirectional audio streaming.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = GEMINI_LIVE_MODEL,
        audio_interface: Optional[DiscordAudioInterface] = None,
        system_instruction: Optional[str] = None,
    ):
        """
        Initialize the Gemini Live agent.

        Args:
            api_key: Google AI API key
            model: Model to use for native audio
            audio_interface: Custom audio interface for Discord
            system_instruction: Optional system instruction for the agent
        """
        self.api_key = api_key
        self.model = model
        self.audio_interface = audio_interface or DiscordAudioInterface()
        self.system_instruction = system_instruction or (
            "You are a helpful AI assistant in a Discord voice channel. "
            "Be conversational, friendly, and concise in your responses. "
            "Keep responses brief since this is a voice conversation."
        )

        # Initialize the Gemini client
        self.client = genai.Client(api_key=self.api_key)

        # Session state
        self._session = None
        self._session_context = None
        self._is_active = False
        self._session_task: Optional[asyncio.Task] = None

        # Event callbacks
        self._on_agent_speaking: Optional[Callable[[str], None]] = None
        self._on_user_speaking: Optional[Callable[[str], None]] = None

        # Audio queue for sending to Gemini
        self._audio_send_queue: asyncio.Queue = asyncio.Queue()

        # Event to signal session is ready
        self._session_ready = asyncio.Event()

    @property
    def is_active(self) -> bool:
        """Check if the agent session is active."""
        return self._is_active

    def on_agent_speaking(self, callback: Callable[[str], None]) -> None:
        """Set callback for when agent speaks (transcription)."""
        self._on_agent_speaking = callback

    def on_user_speaking(self, callback: Callable[[str], None]) -> None:
        """Set callback for when user speech is transcribed."""
        self._on_user_speaking = callback

    async def start_session(self) -> bool:
        """
        Start a conversation session with Gemini Live API.

        Returns:
            True if session started successfully
        """
        if self._is_active:
            logger.warning("Session already active")
            return True

        try:
            self._is_active = True
            self._session_ready.clear()

            # Start the audio interface
            self.audio_interface.start(self._handle_input_audio)

            # Start the session management task
            self._session_task = asyncio.create_task(self._run_session())

            # Wait for session to be ready (with timeout)
            try:
                await asyncio.wait_for(self._session_ready.wait(), timeout=10.0)
                logger.info("Gemini Live agent session started")
                return True
            except asyncio.TimeoutError:
                logger.error("Timeout waiting for Gemini session to start")
                self._is_active = False
                return False

        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            self._is_active = False
            return False

    async def _run_session(self) -> None:
        """Run the Gemini Live session in the background."""
        try:
            # Configure the session
            config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name="Puck"  # Natural sounding voice
                        )
                    )
                ),
                system_instruction=types.Content(
                    parts=[types.Part(text=self.system_instruction)]
                ),
            )

            # Use async context manager properly
            async with self.client.aio.live.connect(
                model=self.model,
                config=config
            ) as session:
                self._session = session
                self._session_ready.set()
                logger.info("Gemini Live session connected")

                # Run send and receive concurrently
                send_task = asyncio.create_task(self._send_loop())
                receive_task = asyncio.create_task(self._receive_loop())

                try:
                    # Wait until session ends or error occurs
                    while self._is_active:
                        await asyncio.sleep(0.1)
                finally:
                    send_task.cancel()
                    receive_task.cancel()
                    try:
                        await send_task
                    except asyncio.CancelledError:
                        pass
                    try:
                        await receive_task
                    except asyncio.CancelledError:
                        pass

        except Exception as e:
            logger.error(f"Session error: {e}")
        finally:
            self._session = None
            self._is_active = False
            logger.info("Gemini Live session closed")

    async def end_session(self) -> None:
        """End the current conversation session."""
        self._is_active = False

        # Cancel session task
        if self._session_task:
            self._session_task.cancel()
            try:
                await self._session_task
            except asyncio.CancelledError:
                pass
            self._session_task = None

        # Stop audio interface
        self.audio_interface.stop()

        logger.info("Gemini Live agent session ended")

    async def send_text(self, text: str) -> None:
        """
        Send text input to the agent.

        Args:
            text: Text message to send
        """
        if not self._is_active or not self._session:
            logger.warning("send_text called but no active session")
            return

        try:
            await self._session.send(input=text, end_of_turn=True)
            logger.info(f"Sent text to Gemini: {text[:50]}...")
        except Exception as e:
            logger.error(f"Error sending text: {e}")

    async def interrupt(self) -> None:
        """Interrupt the current agent response."""
        self.audio_interface.interrupt()
        # Clear the send queue
        while not self._audio_send_queue.empty():
            try:
                self._audio_send_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def receive_discord_audio(self, pcm_data: bytes, user_id: int) -> None:
        """
        Receive audio from Discord.

        Args:
            pcm_data: PCM audio data from Discord (48kHz stereo)
            user_id: Discord user ID
        """
        # This delegates to the audio interface
        self.audio_interface.receive_discord_audio(pcm_data, user_id)

    def _handle_input_audio(self, audio_data: bytes) -> None:
        """
        Handle audio input from Discord (via audio interface).

        Args:
            audio_data: PCM audio bytes (16kHz mono)
        """
        if not self._is_active:
            return

        # Queue the audio for sending
        try:
            self._audio_send_queue.put_nowait(audio_data)
        except asyncio.QueueFull:
            logger.warning("Audio send queue full, dropping audio")

    async def _send_loop(self) -> None:
        """Background task to send audio to Gemini."""
        logger.info("Audio send loop started")

        while self._is_active and self._session:
            try:
                # Get audio from queue with timeout
                try:
                    audio_data = await asyncio.wait_for(
                        self._audio_send_queue.get(),
                        timeout=0.1
                    )
                except asyncio.TimeoutError:
                    continue

                if not self._session:
                    continue

                # Send audio to Gemini using realtime input
                # Audio should be 16kHz mono PCM
                await self._session.send(
                    input=types.LiveClientRealtimeInput(
                        media_chunks=[
                            types.Blob(
                                mime_type="audio/pcm;rate=16000",
                                data=audio_data
                            )
                        ]
                    )
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._is_active:
                    logger.error(f"Error in send loop: {e}")

        logger.info("Audio send loop ended")

    async def _receive_loop(self) -> None:
        """Background task to receive audio from Gemini."""
        logger.info("Audio receive loop started")

        try:
            while self._is_active and self._session:
                try:
                    async for response in self._session.receive():
                        if not self._is_active:
                            break

                        await self._handle_response(response)

                except Exception as e:
                    if self._is_active:
                        logger.error(f"Error receiving from Gemini: {e}")
                    break

        except asyncio.CancelledError:
            pass

        logger.info("Audio receive loop ended")

    async def _handle_response(self, response) -> None:
        """
        Handle a response from Gemini.

        Args:
            response: Response from Gemini Live API
        """
        try:
            # Handle server content (model output)
            if hasattr(response, 'server_content') and response.server_content:
                server_content = response.server_content

                # Check for model turn with audio
                if hasattr(server_content, 'model_turn') and server_content.model_turn:
                    for part in server_content.model_turn.parts:
                        # Handle audio output
                        if hasattr(part, 'inline_data') and part.inline_data:
                            if part.inline_data.data:
                                audio_bytes = part.inline_data.data
                                if isinstance(audio_bytes, bytes) and len(audio_bytes) > 0:
                                    # Send to Discord via audio interface
                                    # Gemini outputs 24kHz mono PCM
                                    self.audio_interface.output(audio_bytes)
                                    logger.debug(f"Received {len(audio_bytes)} bytes of audio from Gemini")

                        # Handle text (transcription)
                        if hasattr(part, 'text') and part.text:
                            if self._on_agent_speaking:
                                self._on_agent_speaking(part.text)

            # Handle input transcription
            if hasattr(response, 'input_transcription') and response.input_transcription:
                if hasattr(response.input_transcription, 'text'):
                    text = response.input_transcription.text
                    if text and self._on_user_speaking:
                        self._on_user_speaking(text)

            # Handle output transcription
            if hasattr(response, 'output_transcription') and response.output_transcription:
                if hasattr(response.output_transcription, 'text'):
                    text = response.output_transcription.text
                    if text and self._on_agent_speaking:
                        self._on_agent_speaking(text)

        except Exception as e:
            logger.error(f"Error handling response: {e}")


class ConversationManager:
    """
    Manages multiple conversations across different Discord channels.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = GEMINI_LIVE_MODEL,
        system_instruction: Optional[str] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.system_instruction = system_instruction
        self._conversations: Dict[int, GeminiLiveAgent] = {}

    async def get_or_create_conversation(
        self, channel_id: int
    ) -> GeminiLiveAgent:
        if channel_id not in self._conversations:
            agent = GeminiLiveAgent(
                api_key=self.api_key,
                model=self.model,
                system_instruction=self.system_instruction,
            )
            self._conversations[channel_id] = agent

        return self._conversations[channel_id]

    async def end_conversation(self, channel_id: int) -> None:
        if channel_id in self._conversations:
            agent = self._conversations.pop(channel_id)
            await agent.end_session()

    async def end_all_conversations(self) -> None:
        for agent in self._conversations.values():
            await agent.end_session()
        self._conversations.clear()

    def get_active_conversations(self) -> Dict[int, GeminiLiveAgent]:
        return {k: v for k, v in self._conversations.items() if v.is_active}
