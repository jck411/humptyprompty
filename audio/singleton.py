import pyaudio
from config import log_startup, log_shutdown

class PyAudioSingleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = pyaudio.PyAudio()
            log_startup("PyAudio initialized.")
        return cls._instance

    @classmethod
    def terminate(cls):
        if cls._instance is not None:
            cls._instance.terminate()
            log_shutdown("PyAudio terminated.")
            cls._instance = None
