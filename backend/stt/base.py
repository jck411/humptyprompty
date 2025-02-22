from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

class STTState(Enum):
    INITIALIZING = "initializing"
    READY = "ready"
    LISTENING = "listening"
    PAUSED = "paused"
    ERROR = "error"

class BaseSTTProvider(ABC):
    """Base class for all STT providers"""
    
    @abstractmethod
    def start_listening(self) -> None:
        """Start listening for speech input"""
        pass
    
    @abstractmethod
    def pause_listening(self) -> None:
        """Pause speech recognition"""
        pass
    
    @abstractmethod
    def get_speech_nowait(self) -> Optional[str]:
        """Get recognized speech text without waiting"""
        pass
    
    @property
    @abstractmethod
    def is_listening(self) -> bool:
        """Check if the provider is currently listening"""
        pass

    @property
    @abstractmethod
    def state(self) -> STTState:
        """Get the current state of the STT provider"""
        pass
