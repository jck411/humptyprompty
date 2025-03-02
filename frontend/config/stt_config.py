"""
Speech-to-Text (STT) configuration settings
"""
from typing import Dict, Any

STT_CONFIG: Dict[str, Any] = {
    "STT_ENABLED": True,
    "PROVIDER": "deepgram",  # Only provider available
    "DEEPGRAM_STT": {
        "LANGUAGE": "en-US",
        "MODEL": "nova-2",
        "SAMPLE_RATE": 16000,
        "SMART_FORMAT": True,
        "INTERIM_RESULTS": True,
        "ENCODING": "linear16",
        "CHANNELS": 1,
        "ENDPOINTING": True,
        "UTTERANCE_END_MS": 1000
    }
} 