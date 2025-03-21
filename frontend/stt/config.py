"""
Speech-to-Text (STT) configuration settings
"""
from typing import Dict, Any

STT_CONFIG: Dict[str, Any] = {
    'enabled': False,  # Global switch to enable/disable STT (if True, will start automatically on initialization)
    'use_keepalive': True,  # Whether to use KeepAlive for pausing/resuming during TTS, this is renewed every 5 seconds during TTS
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
    
    # Connection settings not related to tts but to silence timeout
    'keepalive': True,  # Enable KeepAlive in the Deepgram connection
    'keepalive_timeout': 15  # Seconds before the connection times out when in KeepAlive mode
}
