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

        # Azure-specific validation
        if self.provider == "azure":
            required_fields = ["LANGUAGE", "CONTINUOUS_RECOGNITION"]
            for field in required_fields:
                if field not in self.settings:
                    raise ValueError(f"Missing required field for Azure STT: {field}")

        # Add validation for other providers as they are implemented
        # elif self.provider == "other_provider":
        #     pass
