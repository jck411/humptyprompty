"""
Speech-to-Text (STT) configuration settings
"""
from typing import Dict, Any

STT_CONFIG: Dict[str, Any] = {
    'enabled': False,  # Global switch to enable/disable STT
    'auto_start': False,  # Whether to start STT automatically on initialization
    'use_keepalive': False,  # Whether to use KeepAlive for pausing/resuming during TTS
    'inactivity_timeout': 5,  # Automatically turn off STT after N seconds of no transcription
}

# Audio capture configuration
AUDIO_CONFIG = {
    'channels': 1,
    'sample_rate': 16000,
    'block_size': 4000,
    'dtype': 'float32',  # Used by sounddevice
}

# Deepgram configuration
DEEPGRAM_CONFIG = {
    # Core settings
    'language': 'en-US',
    'model': 'nova-3',
    
    # Audio settings
    'encoding': 'linear16',
    'channels': 1,
    'sample_rate': 16000,
    
    # Transcription settings
    'smart_format': True,
    'interim_results': True,
    'endpointing': 500,
    'punctuate': True,
    'filler_words': True,
    'vad_events': True,
    
    # Connection settings
    'keepalive': True,  # Enable KeepAlive in the Deepgram connection
    'keepalive_timeout': 5  # Seconds before the connection times out when in KeepAlive mode
}
