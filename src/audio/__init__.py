"""Audio processing modules for Discord-ElevenLabs integration."""

from .discord_audio_interface import DiscordAudioInterface
from .audio_buffer import AudioBuffer
from .discord_audio_source import ElevenLabsAudioSource

__all__ = ["DiscordAudioInterface", "AudioBuffer", "ElevenLabsAudioSource"]
