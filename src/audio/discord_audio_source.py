"""Discord audio source for playing Gemini audio."""

import io
import logging
from typing import Optional
import discord
from .audio_buffer import AudioBuffer

logger = logging.getLogger(__name__)


class GeminiAudioSource(discord.AudioSource):
    """
    Audio source that streams Gemini audio to Discord.

    This reads PCM audio data from a buffer and provides it to Discord
    for playback in voice channels.
    """

    # Discord expects 48kHz, 16-bit stereo PCM
    SAMPLE_RATE = 48000
    CHANNELS = 2
    SAMPLE_WIDTH = 2  # 16-bit = 2 bytes
    FRAME_SIZE = 3840  # 20ms of audio at 48kHz stereo (960 samples * 2 channels * 2 bytes)

    def __init__(self, buffer: AudioBuffer):
        """
        Initialize the audio source.

        Args:
            buffer: AudioBuffer to read audio data from
        """
        super().__init__()  # Properly initialize parent class
        self._buffer = buffer
        self._is_playing = True
        self._remaining_data = b""

    def read(self) -> bytes:
        """
        Read 20ms of audio data for Discord.

        Returns:
            PCM audio bytes (3840 bytes for 20ms at 48kHz stereo)
        """
        if not self._is_playing:
            return b""

        # Combine remaining data with new data from buffer
        data = self._remaining_data

        # Keep reading until we have enough for a frame
        chunks_read = 0
        while len(data) < self.FRAME_SIZE:
            chunk = self._buffer.get()
            if chunk is None:
                break
            chunks_read += 1
            data += chunk

        if len(data) == 0:
            # Return silence if no data available
            return b"\x00" * self.FRAME_SIZE

        if len(data) >= self.FRAME_SIZE:
            # Return exactly one frame
            frame = data[:self.FRAME_SIZE]
            self._remaining_data = data[self.FRAME_SIZE:]
            if chunks_read > 0:
                logger.debug(f"Audio source: read {len(frame)} bytes from {chunks_read} chunks, remaining: {len(self._remaining_data)}")
            return frame
        else:
            # Pad with silence if not enough data
            logger.debug(f"Audio source: padding {len(data)} bytes with silence")
            self._remaining_data = b""
            return data + b"\x00" * (self.FRAME_SIZE - len(data))

    def is_opus(self) -> bool:
        """Return False since we're providing PCM audio."""
        return False

    def cleanup(self) -> None:
        """Clean up resources."""
        self._is_playing = False
        self._buffer.clear()
        self._remaining_data = b""

    def stop(self) -> None:
        """Stop the audio source."""
        self._is_playing = False

    def resume(self) -> None:
        """Resume the audio source."""
        self._is_playing = True


class StreamingAudioSource(discord.AudioSource):
    """
    Streaming audio source that reads from an async generator.

    Useful for real-time audio streaming from Gemini WebSocket.
    """

    FRAME_SIZE = 3840

    def __init__(self):
        """Initialize the streaming audio source."""
        self._buffer = io.BytesIO()
        self._is_playing = True
        self._lock = __import__("threading").Lock()

    def write(self, data: bytes) -> None:
        """
        Write audio data to the stream.

        Args:
            data: Audio bytes to write
        """
        with self._lock:
            pos = self._buffer.tell()
            self._buffer.seek(0, 2)  # Seek to end
            self._buffer.write(data)
            self._buffer.seek(pos)  # Restore position

    def read(self) -> bytes:
        """Read 20ms of audio data."""
        if not self._is_playing:
            return b""

        with self._lock:
            data = self._buffer.read(self.FRAME_SIZE)

        if len(data) == 0:
            return b"\x00" * self.FRAME_SIZE

        if len(data) < self.FRAME_SIZE:
            return data + b"\x00" * (self.FRAME_SIZE - len(data))

        return data

    def is_opus(self) -> bool:
        """Return False since we're providing PCM audio."""
        return False

    def cleanup(self) -> None:
        """Clean up resources."""
        self._is_playing = False
        with self._lock:
            self._buffer.close()

    def stop(self) -> None:
        """Stop playback."""
        self._is_playing = False
