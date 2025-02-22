from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Optional, Any, Dict

class STTState(Enum):
    IDLE = auto()
    READY = auto()
    LISTENING = auto()
    PAUSED = auto()
    PROCESSING = auto()
    ERROR = auto()

class BaseSTTProvider(ABC):
    """Base class for all STT providers"""
    
    def __init__(self):
        self._state = STTState.IDLE

    @property
    def state(self) -> STTState:
        return self._state

    @property
    def is_listening(self) -> bool:
        return self._state == STTState.LISTENING

    @abstractmethod
    async def start_listening(self):
        """Start listening for audio input"""
        pass

    @abstractmethod
    async def stop_listening(self):
        """Stop listening for audio input"""
        pass

    @abstractmethod
    def pause_listening(self) -> None:
        """Pause speech recognition"""
        pass
    
    @abstractmethod
    def get_speech_nowait(self) -> Optional[str]:
        """Get recognized speech text without waiting"""
        pass
