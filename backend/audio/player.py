import pyaudio
import threading
import logging
from backend.audio.singleton import PyAudioSingleton
from backend.config.config import CONFIG

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

    def stop_stream(self):
        with self.lock:
            if self.stream and self.is_playing:
                logger.debug("Stopping audio stream")
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
                self.is_playing = False

    def write_audio(self, data: bytes):
        with self.lock:
            if self.stream and self.is_playing:
                try:
                    logger.debug(f"Writing {len(data)} bytes to audio stream")
                    self.stream.write(data)
                except Exception as e:
                    logger.error(f"Error writing to audio stream: {e}")
                    raise

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
