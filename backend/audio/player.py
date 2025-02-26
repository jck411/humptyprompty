import pyaudio
import threading
import logging
import asyncio
from typing import Callable, Optional
from backend.audio.singleton import PyAudioSingleton
from backend.config.config import CONFIG
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class AudioPlayer:
    def __init__(self, pyaudio_instance, playback_rate=24000, channels=1, format=pyaudio.paInt16):
        """
        Initialize an audio player using PyAudio.
        
        Args:
            pyaudio_instance: PyAudio instance to use
            playback_rate: Sample rate in Hz
            channels: Number of audio channels
            format: Audio format (from PyAudio constants)
        """
        self.pa = pyaudio_instance
        self.playback_rate = playback_rate
        self.channels = channels
        self.format = format
        
        self.stream = None
        self.is_playing = False
        self.lock = threading.RLock()
        
        self._buffer_count = 0
        self._last_chunk = False
        self._main_loop = None
        self.on_playback_complete = None

    def start_stream(self):
        """
        Start the PyAudio stream for playback.
        """
        with self.lock:
            if self.stream is None:
                try:
                    self.stream = self.pa.open(
                        format=self.format,
                        channels=self.channels,
                        rate=self.playback_rate,
                        output=True,
                        frames_per_buffer=1024
                    )
                    logger.debug("Audio stream created")
                    
                    self.is_playing = True
                    self._buffer_count = 0
                    self._last_chunk = False
                    
                    logger.info("Audio playback stream started")
                except Exception as e:
                    logger.error(f"Failed to create audio stream: {e}")
                    self.is_playing = False

    def stop_stream(self):
        """
        Stop the PyAudio stream.
        """
        with self.lock:
            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                    logger.debug("Audio stream stopped and closed")
                except Exception as e:
                    logger.error(f"Error stopping audio stream: {e}")
                finally:
                    self.stream = None
                    self.is_playing = False

    def write_audio(self, data: bytes):
        """
        Write audio data to the stream without blocking the main thread.
        Uses a buffered approach to avoid blocking and ensure smooth playback.
        
        Args:
            data: PCM audio data
        """
        with self.lock:
            if self.stream and self.is_playing:
                try:
                    # Use larger chunk size for more efficient processing
                    CHUNK_SIZE = 8192  # Aligned with TTS chunk size for optimal performance
                    
                    # Process audio in optimal-sized chunks
                    for i in range(0, len(data), CHUNK_SIZE):
                        chunk = data[i:i+CHUNK_SIZE]
                        if chunk:
                            # Write chunk directly to stream
                            self.stream.write(chunk, num_frames=len(chunk)//2)
                    
                    self._buffer_count += 1
                    
                    # If this was marked as the last chunk and we've written it
                    if self._last_chunk:
                        logger.debug("Last audio chunk processed, notifying completion")
                        self._notify_completion()
                        self._last_chunk = False
                        
                except Exception as e:
                    logger.error(f"Error writing to audio stream: {e}")
                    raise

    def mark_last_chunk(self):
        """Mark the next chunk as the last one in the stream"""
        self._last_chunk = True

    def set_main_loop(self, loop: asyncio.AbstractEventLoop):
        """Set the main event loop for async callbacks"""
        self._main_loop = loop

    def _notify_completion(self):
        """Helper method to handle completion notification"""
        if self._main_loop and self.on_playback_complete:
            if asyncio.iscoroutinefunction(self.on_playback_complete):
                self._main_loop.create_task(self.on_playback_complete())


def create_audio_player():
    """
    Create and return a singleton AudioPlayer instance.
    Note: This expects PyAudioSingleton to be initialized elsewhere.
    """
    from backend.audio.singleton import PyAudioSingleton
    pa_instance = PyAudioSingleton()
    return AudioPlayer(pa_instance)
