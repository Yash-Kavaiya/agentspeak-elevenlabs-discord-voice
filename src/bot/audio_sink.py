"""Audio sink for receiving Discord voice audio."""

import logging
from typing import Callable, Optional, Dict
import discord

logger = logging.getLogger(__name__)

# Try to import voice receive extension
try:
    from discord.ext import voice_recv

    HAS_VOICE_RECV = True
except ImportError:
    HAS_VOICE_RECV = False
    logger.warning("discord-ext-voice-recv not installed. Voice receiving disabled.")


if HAS_VOICE_RECV:

    class GeminiAudioSink(voice_recv.AudioSink):
        """
        Audio sink that captures Discord voice audio and sends it to Gemini.

        Uses discord-ext-voice-recv for capturing user audio from voice channels.
        """

        def __init__(
            self,
            on_audio: Callable[[bytes, int], None],
            target_user_id: Optional[int] = None,
        ):
            super().__init__()
            self.on_audio = on_audio
            self.target_user_id = target_user_id
            self._active_users: Dict[int, bool] = {}

        def wants_opus(self) -> bool:
            """Return False to receive decoded PCM audio directly."""
            return False

        def write(self, user: discord.User, data: voice_recv.VoiceData) -> None:
            """
            Called when audio data is received.

            Args:
                user: Discord user who sent the audio
                data: Voice data container with PCM audio
            """
            if user is None:
                return

            # Filter by target user if specified
            if self.target_user_id and user.id != self.target_user_id:
                return

            try:
                # Get PCM audio data
                # When wants_opus() returns False, data.pcm contains decoded PCM
                pcm_data = None

                # Try different ways to get PCM data
                if hasattr(data, 'pcm') and data.pcm:
                    pcm_data = data.pcm
                elif hasattr(data, 'data') and data.data:
                    pcm_data = data.data

                if pcm_data and len(pcm_data) > 0:
                    logger.debug(f"Received {len(pcm_data)} bytes of audio from {user.name}")
                    self.on_audio(pcm_data, user.id)

            except Exception as e:
                logger.error(f"Error processing audio from {user}: {e}")

        def cleanup(self) -> None:
            """Clean up resources."""
            self._active_users.clear()

else:

    class GeminiAudioSink:
        """Fallback class when voice_recv is not available."""

        def __init__(
            self,
            on_audio: Callable[[bytes, int], None],
            target_user_id: Optional[int] = None,
        ):
            """
            Initialize the audio sink.

            Args:
                on_audio: Callback function(audio_data, user_id)
                target_user_id: Optional specific user to listen to
            """
            self.on_audio = on_audio
            self.target_user_id = target_user_id
            self._active_users: Dict[int, bool] = {}

        def wants_opus(self) -> bool:
            """Return False since we're using a fallback mode."""
            return False

        def write(self, user, data) -> None:
            """Fallback write - not functional without voice_recv."""
            pass

        def cleanup(self) -> None:
            """Clean up resources."""
            self._active_users.clear()




class SimpleAudioSink:
    """
    Simple audio sink implementation without discord-ext-voice-recv.

    This is a fallback that works with basic discord.py but has limited functionality.
    """

    def __init__(self, on_audio: Callable[[bytes, int], None]):
        """
        Initialize the simple audio sink.

        Args:
            on_audio: Callback function(audio_data, user_id)
        """
        self.on_audio = on_audio
        self._buffer = b""

    def write(self, data: bytes, user_id: int = 0) -> None:
        """
        Write audio data.

        Args:
            data: PCM audio bytes
            user_id: User ID (default 0 if unknown)
        """
        self.on_audio(data, user_id)

    def cleanup(self) -> None:
        """Clean up resources."""
        self._buffer = b""


def create_audio_sink(
    on_audio: Callable[[bytes, int], None],
    target_user_id: Optional[int] = None,
):
    """
    Factory function to create the appropriate audio sink.

    Args:
        on_audio: Callback function for audio data
        target_user_id: Optional specific user to listen to

    Returns:
        Audio sink instance
    """
    if HAS_VOICE_RECV:
        return GeminiAudioSink(on_audio, target_user_id)
    else:
        logger.warning("Using simple audio sink (limited functionality)")
        return SimpleAudioSink(on_audio)
