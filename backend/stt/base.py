from abc import ABC, abstractmethod
from queue import Queue
from enum import Enum, auto

class STTState(Enum):
    READY = auto()
    IDLE = auto()
    LISTENING = auto()
    PAUSED = auto()
    ERROR = auto()

class BaseSTTProvider(ABC):
    def __init__(self):
        self._state = STTState.IDLE
        self.speech_queue = Queue()

    @abstractmethod
    def setup_recognizer(self) -> None:
        """
        Provider-specific recognizer setup.
        """
        pass

    @abstractmethod
    def _start_listening_impl(self) -> None:
        """
        Provider-specific logic to start listening.
        """
        pass

    @abstractmethod
    def _stop_listening_impl(self) -> None:
        """
        Provider-specific logic to stop listening.
        """
        pass

    @abstractmethod
    def _pause_listening_impl(self) -> None:
        """
        Provider-specific logic to pause listening.
        """
        pass

    async def start_listening(self):
        if self._state not in [STTState.IDLE, STTState.READY, STTState.PAUSED]:
            return
        try:
            self._start_listening_impl()
            self._state = STTState.LISTENING
        except Exception as e:
            print(f"Error starting listening: {e}")
            self._state = STTState.ERROR

    async def stop_listening(self):
        if self._state != STTState.LISTENING:
            return
        try:
            self._stop_listening_impl()
            self._state = STTState.IDLE
        except Exception as e:
            print(f"Error stopping listening: {e}")
            self._state = STTState.ERROR

    def pause_listening(self) -> None:
        if self._state == STTState.LISTENING:
            try:
                self._pause_listening_impl()
                self._state = STTState.PAUSED
                # Clear the queue
                while not self.speech_queue.empty():
                    self.speech_queue.get_nowait()
            except Exception as e:
                print(f"Error pausing listening: {e}")
                self._state = STTState.ERROR

    def get_speech_nowait(self):
        try:
            return self.speech_queue.get_nowait()
        except Exception:
            return None

    @property
    def is_listening(self) -> bool:
        return self._state == STTState.LISTENING

    @property
    def state(self):
        return self._state
