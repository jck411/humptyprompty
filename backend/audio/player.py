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
        self.pyaudio = pyaudio_instance
        self.playback_rate = playback_rate
        self.channels = channels
        self.format = format
        self.stream = None
        self.lock = threading.Lock()
        self.is_playing = False
        self.on_playback_complete: Optional[Callable] = None
        self._buffer_count = 0
        self._last_chunk = False
        self.executor = ThreadPoolExecutor(max_workers=1)
        self._main_loop = None

    def start_stream(self):
        with self.lock:
            if not self.is_playing:
                logger.debug(f"Starting audio stream with rate={self.playback_rate}, channels={self.channels}, format={self.format}")
                self.stream = self.pyaudio.open(
                    format=self.format,
                    channels=self.channels,
                    rate=self.playback_rate,
                    output=True,
                    frames_per_buffer=1024
                )
                self.is_playing = True
                self._buffer_count = 0
                self._last_chunk = False

    def stop_stream(self):
        with self.lock:
            if self.stream and self.is_playing:
                logger.debug("Stopping audio stream")
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
                self.is_playing = False
                # Notify completion when stream is explicitly stopped
                self._notify_completion()

    def write_audio(self, data: bytes):
        with self.lock:
            if self.stream and self.is_playing:
                try:
                    logger.debug(f"Writing {len(data)} bytes to audio stream")
                    self.stream.write(data)
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
        if self.on_playback_complete and callable(self.on_playback_complete):
            logger.debug("Notifying playback completion")
            if self._main_loop is None:
                logger.error("Main loop not set - cannot send completion notification")
                return
                
            async def _run_callback():
                try:
                    await self.on_playback_complete()
                except Exception as e:
                    logger.error(f"Error in completion callback: {e}")

            future = asyncio.run_coroutine_threadsafe(_run_callback(), self._main_loop)
            future.add_done_callback(lambda f: logger.debug("Completion callback finished"))

def create_audio_player():
    """Factory function to create an AudioPlayer instance with the singleton PyAudio."""
    # Convert bits to pyaudio format
    format_map = {
        8: pyaudio.paInt8,
        16: pyaudio.paInt16,
        24: pyaudio.paInt24,
        32: pyaudio.paInt32,
    }
    format_bits = CONFIG["AUDIO_SETTINGS"]["FORMAT"]
    format_value = format_map.get(format_bits, pyaudio.paInt16)
    
    logger.debug(f"Creating audio player with format={format_bits}bits, rate={CONFIG['AUDIO_SETTINGS']['RATE']}")
    
    return AudioPlayer(
        PyAudioSingleton(),
        playback_rate=CONFIG["AUDIO_SETTINGS"]["RATE"],
        channels=CONFIG["AUDIO_SETTINGS"]["CHANNELS"],
        format=format_value
    )
