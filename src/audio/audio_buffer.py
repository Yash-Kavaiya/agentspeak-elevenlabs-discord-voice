"""Thread-safe audio buffer for managing audio chunks."""

import asyncio
import threading
from collections import deque
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class AudioBuffer:
    """Thread-safe buffer for audio data with async support."""

    def __init__(self, max_size: int = 1000):
        """
        Initialize the audio buffer.

        Args:
            max_size: Maximum number of chunks to store
        """
        self._buffer: deque = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._event = asyncio.Event()
        self._closed = False

    def put(self, data: bytes) -> None:
        """
        Add audio data to the buffer.

        Args:
            data: Audio bytes to add
        """
        with self._lock:
            if not self._closed:
                self._buffer.append(data)
                # Signal that data is available
                try:
                    loop = asyncio.get_running_loop()
                    loop.call_soon_threadsafe(self._event.set)
                except RuntimeError:
                    pass

    def get(self) -> Optional[bytes]:
        """
        Get audio data from the buffer (non-blocking).

        Returns:
            Audio bytes or None if buffer is empty
        """
        with self._lock:
            if self._buffer:
                return self._buffer.popleft()
            return None

    def get_all(self) -> bytes:
        """
        Get all audio data from the buffer.

        Returns:
            Combined audio bytes
        """
        with self._lock:
            data = b"".join(self._buffer)
            self._buffer.clear()
            return data

    async def get_async(self, timeout: float = 0.1) -> Optional[bytes]:
        """
        Async get with timeout.

        Args:
            timeout: Maximum time to wait for data

        Returns:
            Audio bytes or None if timeout
        """
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout)
            self._event.clear()
            return self.get()
        except asyncio.TimeoutError:
            return self.get()

    def clear(self) -> None:
        """Clear all data from the buffer."""
        with self._lock:
            self._buffer.clear()
            self._event.clear()

    def close(self) -> None:
        """Close the buffer."""
        self._closed = True
        self.clear()

    @property
    def size(self) -> int:
        """Get current buffer size."""
        with self._lock:
            return len(self._buffer)

    @property
    def is_empty(self) -> bool:
        """Check if buffer is empty."""
        with self._lock:
            return len(self._buffer) == 0
