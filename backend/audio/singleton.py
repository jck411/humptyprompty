import pyaudio

class PyAudioSingleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = pyaudio.PyAudio()
        return cls._instance

    @classmethod
    def terminate(cls):
        if cls._instance is not None:
            cls._instance.terminate()
            cls._instance = None
