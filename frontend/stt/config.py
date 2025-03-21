# stt/config.py
from typing import Dict, Any

STT_CONFIG: Dict[str, Any] = {
    'enabled': True,
    'auto_start': True,
    'use_keepalive': True,
}

AUDIO_CONFIG = {
    'channels': 1,
    'sample_rate': 16000,
    'block_size': 4000,
    'dtype': 'float32',
}

DEEPGRAM_CONFIG = {
    'language': 'en-US',
    'model': 'nova-3',
    'encoding': 'linear16',
    'channels': 1,
    'sample_rate': 16000,
    'smart_format': True,
    'interim_results': True,
    'endpointing': 500,
    'punctuate': True,
    'filler_words': True,
    'vad_events': True,
    'keepalive': True,
    'keepalive_timeout': 30
}
