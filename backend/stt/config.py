from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class STTConfig:
    """Configuration class for STT providers"""
    provider: str
    settings: Dict[str, Any]
    enabled: bool = True

    def __post_init__(self):
        self.validate_settings()

    def validate_settings(self) -> None:
        """Validate provider-specific settings"""
        if not self.provider:
            raise ValueError("STT provider must be specified")
        
        if not isinstance(self.settings, dict):
            raise ValueError("Settings must be a dictionary")

        # Only validate Deepgram settings since it's the only provider we're using
        if self.provider != "deepgram":
            raise ValueError("Only Deepgram STT provider is supported")
            
        # Deepgram-specific validation
        required_fields = ["LANGUAGE", "MODEL", "SAMPLE_RATE"]
        for field in required_fields:
            if field not in self.settings:
                raise ValueError(f"Missing required field for Deepgram STT: {field}")
