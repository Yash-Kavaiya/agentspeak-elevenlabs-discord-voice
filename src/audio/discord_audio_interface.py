"""Custom audio interface bridging Discord voice with ElevenLabs Conversational AI."""

import asyncio
import logging
import struct
import threading
from typing import Callable, Optional, Any
from .audio_buffer import AudioBuffer

logger = logging.getLogger(__name__)


class DiscordAudioInterface:
    """
    Custom audio interface for ElevenLabs Conversational AI that works with Discord.

    This interface captures audio from Discord voice channels and sends it to
    ElevenLabs, while also receiving audio responses and playing them back.
    """

    # ElevenLabs expects 16kHz, 16-bit mono PCM
    ELEVENLABS_SAMPLE_RATE = 16000
    ELEVENLABS_CHANNELS = 1
    ELEVENLABS_SAMPLE_WIDTH = 2

    # Discord provides 48kHz, 16-bit stereo PCM
    DISCORD_SAMPLE_RATE = 48000
    DISCORD_CHANNELS = 2
    DISCORD_SAMPLE_WIDTH = 2

    def __init__(self):
        """Initialize the Discord audio interface."""
        self._input_callback: Optional[Callable] = None
        self._output_buffer = AudioBuffer(max_size=500)
        self._input_buffer = AudioBuffer(max_size=500)
        self._is_running = False
        self._output_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, input_callback: Callable[[bytes], None]) -> None:
        """
        Start the audio interface.

        Args:
            input_callback: Callback function that receives audio input
        """
        self._input_callback = input_callback
        self._is_running = True
        logger.info("Discord audio interface started")

    def stop(self) -> None:
        """Stop the audio interface."""
        self._is_running = False
        self._input_buffer.close()
        self._output_buffer.close()
        logger.info("Discord audio interface stopped")

    def output(self, audio: bytes) -> None:
        """
        Receive audio from ElevenLabs and buffer it for Discord playback.

        Args:
            audio: PCM audio bytes from ElevenLabs (16kHz mono)
        """
        if not self._is_running:
            return

        # Convert from 16kHz mono to 48kHz stereo for Discord
        converted_audio = self._convert_to_discord_format(audio)
        self._output_buffer.put(converted_audio)

    def interrupt(self) -> None:
        """Interrupt current audio output (e.g., when user starts speaking)."""
        self._output_buffer.clear()
        logger.debug("Audio output interrupted")

    def receive_discord_audio(self, pcm_data: bytes, user_id: int) -> None:
        """
        Receive audio from Discord and send to ElevenLabs.

        Args:
            pcm_data: PCM audio bytes from Discord (48kHz stereo)
            user_id: Discord user ID who sent the audio
        """
        if not self._is_running or not self._input_callback:
            return

        # Convert from 48kHz stereo to 16kHz mono for ElevenLabs
        converted_audio = self._convert_to_elevenlabs_format(pcm_data)

        # Send to ElevenLabs via callback
        try:
            self._input_callback(converted_audio)
        except Exception as e:
            logger.error(f"Error sending audio to ElevenLabs: {e}")

    def get_output_buffer(self) -> AudioBuffer:
        """Get the output buffer for Discord playback."""
        return self._output_buffer

    def _convert_to_discord_format(self, audio: bytes) -> bytes:
        """
        Convert ElevenLabs audio format to Discord format.

        ElevenLabs: 16kHz, 16-bit, mono
        Discord: 48kHz, 16-bit, stereo

        Args:
            audio: Input audio bytes

        Returns:
            Converted audio bytes
        """
        if len(audio) == 0:
            return b""

        # Parse 16-bit samples
        num_samples = len(audio) // 2
        samples = struct.unpack(f"<{num_samples}h", audio)

        # Upsample 16kHz -> 48kHz (3x) using simple linear interpolation
        upsampled = []
        for i in range(len(samples) - 1):
            upsampled.append(samples[i])
            # Interpolate 2 samples between each original sample
            diff = samples[i + 1] - samples[i]
            upsampled.append(int(samples[i] + diff / 3))
            upsampled.append(int(samples[i] + 2 * diff / 3))
        if samples:
            upsampled.append(samples[-1])

        # Convert mono to stereo (duplicate channel)
        stereo = []
        for sample in upsampled:
            stereo.append(sample)  # Left
            stereo.append(sample)  # Right

        # Pack back to bytes
        return struct.pack(f"<{len(stereo)}h", *stereo)

    def _convert_to_elevenlabs_format(self, audio: bytes) -> bytes:
        """
        Convert Discord audio format to ElevenLabs format.

        Discord: 48kHz, 16-bit, stereo
        ElevenLabs: 16kHz, 16-bit, mono

        Args:
            audio: Input audio bytes

        Returns:
            Converted audio bytes
        """
        if len(audio) == 0:
            return b""

        # Parse 16-bit stereo samples
        num_samples = len(audio) // 4  # 4 bytes per stereo sample
        stereo_samples = struct.unpack(f"<{num_samples * 2}h", audio)

        # Convert stereo to mono (average channels)
        mono_samples = []
        for i in range(0, len(stereo_samples), 2):
            left = stereo_samples[i]
            right = stereo_samples[i + 1] if i + 1 < len(stereo_samples) else left
            mono_samples.append((left + right) // 2)

        # Downsample 48kHz -> 16kHz (take every 3rd sample)
        downsampled = mono_samples[::3]

        # Pack back to bytes
        return struct.pack(f"<{len(downsampled)}h", *downsampled)


class AsyncDiscordAudioInterface(DiscordAudioInterface):
    """Async version of DiscordAudioInterface for use with asyncio."""

    def __init__(self):
        """Initialize the async Discord audio interface."""
        super().__init__()
        self._audio_queue: asyncio.Queue = asyncio.Queue()

    async def start_async(self, input_callback: Callable[[bytes], None]) -> None:
        """
        Start the audio interface asynchronously.

        Args:
            input_callback: Callback function that receives audio input
        """
        self._input_callback = input_callback
        self._is_running = True
        self._loop = asyncio.get_running_loop()
        logger.info("Async Discord audio interface started")

    async def receive_discord_audio_async(self, pcm_data: bytes, user_id: int) -> None:
        """
        Receive audio from Discord asynchronously.

        Args:
            pcm_data: PCM audio bytes from Discord
            user_id: Discord user ID
        """
        if not self._is_running:
            return

        # Convert and send to ElevenLabs
        converted_audio = self._convert_to_elevenlabs_format(pcm_data)
        await self._audio_queue.put(converted_audio)

        if self._input_callback:
            try:
                self._input_callback(converted_audio)
            except Exception as e:
                logger.error(f"Error in async audio callback: {e}")

    async def get_output_audio_async(self) -> Optional[bytes]:
        """Get output audio asynchronously."""
        return await self._output_buffer.get_async()
