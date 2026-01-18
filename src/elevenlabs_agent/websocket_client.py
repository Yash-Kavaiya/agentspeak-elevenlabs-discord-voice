"""WebSocket client for ElevenLabs Conversational AI."""

import asyncio
import base64
import json
import logging
from typing import Callable, Optional, Any, Dict
import websockets
from websockets.client import WebSocketClientProtocol

logger = logging.getLogger(__name__)


class ElevenLabsWebSocketClient:
    """
    WebSocket client for real-time communication with ElevenLabs Conversational AI.

    This provides low-level access to the ElevenLabs WebSocket API for
    real-time audio streaming in both directions.
    """

    BASE_URL = "wss://api.elevenlabs.io/v1/convai/conversation"

    def __init__(
        self,
        agent_id: str,
        api_key: Optional[str] = None,
        on_audio: Optional[Callable[[bytes], None]] = None,
        on_transcript: Optional[Callable[[str, str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_connected: Optional[Callable[[], None]] = None,
        on_disconnected: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize the WebSocket client.

        Args:
            agent_id: ElevenLabs agent ID
            api_key: Optional API key for private agents
            on_audio: Callback for received audio data
            on_transcript: Callback for transcripts (role, text)
            on_error: Callback for errors
            on_connected: Callback when connected
            on_disconnected: Callback when disconnected
        """
        self.agent_id = agent_id
        self.api_key = api_key
        self.on_audio = on_audio
        self.on_transcript = on_transcript
        self.on_error = on_error
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected

        self._ws: Optional[WebSocketClientProtocol] = None
        self._is_connected = False
        self._receive_task: Optional[asyncio.Task] = None
        self._conversation_id: Optional[str] = None

    @property
    def is_connected(self) -> bool:
        """Check if connected to ElevenLabs."""
        return self._is_connected

    @property
    def conversation_id(self) -> Optional[str]:
        """Get the current conversation ID."""
        return self._conversation_id

    async def connect(self) -> bool:
        """
        Connect to ElevenLabs WebSocket.

        Returns:
            True if connected successfully
        """
        try:
            url = f"{self.BASE_URL}?agent_id={self.agent_id}"

            headers = {}
            if self.api_key:
                headers["xi-api-key"] = self.api_key

            self._ws = await websockets.connect(
                url,
                additional_headers=headers if headers else None,
                ping_interval=20,
                ping_timeout=20,
            )

            self._is_connected = True
            logger.info(f"Connected to ElevenLabs agent: {self.agent_id}")

            # Start receive task
            self._receive_task = asyncio.create_task(self._receive_loop())

            if self.on_connected:
                self.on_connected()

            return True

        except Exception as e:
            logger.error(f"Failed to connect to ElevenLabs: {e}")
            if self.on_error:
                self.on_error(e)
            return False

    async def disconnect(self) -> None:
        """Disconnect from ElevenLabs WebSocket."""
        self._is_connected = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            await self._ws.close()
            self._ws = None

        if self.on_disconnected:
            self.on_disconnected()

        logger.info("Disconnected from ElevenLabs")

    async def send_audio(self, audio_data: bytes) -> None:
        """
        Send audio data to ElevenLabs.

        Args:
            audio_data: PCM audio bytes (16kHz, 16-bit, mono)
        """
        if not self._is_connected or not self._ws:
            return

        try:
            # Encode audio as base64
            audio_base64 = base64.b64encode(audio_data).decode("utf-8")

            message = {
                "type": "audio",
                "audio": audio_base64,
            }

            await self._ws.send(json.dumps(message))

        except Exception as e:
            logger.error(f"Error sending audio: {e}")
            if self.on_error:
                self.on_error(e)

    async def send_text(self, text: str) -> None:
        """
        Send text input to ElevenLabs (for text-based interaction).

        Args:
            text: Text message to send
        """
        if not self._is_connected or not self._ws:
            return

        try:
            message = {
                "type": "text",
                "text": text,
            }

            await self._ws.send(json.dumps(message))

        except Exception as e:
            logger.error(f"Error sending text: {e}")
            if self.on_error:
                self.on_error(e)

    async def interrupt(self) -> None:
        """Send interrupt signal to stop current agent response."""
        if not self._is_connected or not self._ws:
            return

        try:
            message = {"type": "interrupt"}
            await self._ws.send(json.dumps(message))
            logger.debug("Sent interrupt signal")
        except Exception as e:
            logger.error(f"Error sending interrupt: {e}")

    async def _receive_loop(self) -> None:
        """Main loop for receiving messages from ElevenLabs."""
        if not self._ws:
            return

        try:
            async for message in self._ws:
                await self._handle_message(message)
        except websockets.ConnectionClosed as e:
            logger.info(f"WebSocket connection closed: {e}")
        except asyncio.CancelledError:
            logger.debug("Receive loop cancelled")
        except Exception as e:
            logger.error(f"Error in receive loop: {e}")
            if self.on_error:
                self.on_error(e)
        finally:
            self._is_connected = False
            if self.on_disconnected:
                self.on_disconnected()

    async def _handle_message(self, raw_message: str) -> None:
        """
        Handle incoming WebSocket message.

        Args:
            raw_message: Raw JSON message string
        """
        try:
            message = json.loads(raw_message)
            msg_type = message.get("type", "")

            if msg_type == "audio":
                # Decode and pass audio to callback
                audio_base64 = message.get("audio", "")
                if audio_base64 and self.on_audio:
                    audio_data = base64.b64decode(audio_base64)
                    self.on_audio(audio_data)

            elif msg_type == "transcript":
                # Handle transcript (user speech recognition)
                role = message.get("role", "user")
                text = message.get("text", "")
                if text and self.on_transcript:
                    self.on_transcript(role, text)

            elif msg_type == "agent_response":
                # Agent's text response
                text = message.get("text", "")
                if text and self.on_transcript:
                    self.on_transcript("agent", text)

            elif msg_type == "conversation_initiation_metadata":
                # Store conversation ID
                self._conversation_id = message.get("conversation_id")
                logger.info(f"Conversation started: {self._conversation_id}")

            elif msg_type == "error":
                error_msg = message.get("message", "Unknown error")
                logger.error(f"ElevenLabs error: {error_msg}")
                if self.on_error:
                    self.on_error(Exception(error_msg))

            elif msg_type == "ping":
                # Respond to ping
                await self._ws.send(json.dumps({"type": "pong"}))

            else:
                logger.debug(f"Unhandled message type: {msg_type}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
