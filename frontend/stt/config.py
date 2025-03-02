"""
Configuration settings for Deepgram STT and audio capture.
"""

# Global STT settings
STT_CONFIG = {
    'enabled': True,  # Global switch to enable/disable STT
    'auto_start': True,  # Whether to start STT automatically on initialization
}

# Audio capture configuration
AUDIO_CONFIG = {
    'channels': 1,
    'sample_rate': 16000,
    'block_size': 4000,
    'dtype': 'float32'  # Used by sounddevice
}

# Deepgram configuration
DEEPGRAM_CONFIG = {
    # Core settings
    'language': 'en-US',
    'model': 'nova-2',
    
    # Audio settings
    'encoding': 'linear16',
    'channels': AUDIO_CONFIG['channels'],
    'sample_rate': AUDIO_CONFIG['sample_rate'],
    
    # Transcription settings
    'smart_format': True,
    'interim_results': True,
    'endpointing': True,
    'utterance_end_ms': 1000,
    
    # Additional features (commented out by default)
    # 'punctuate': True,      # Add punctuation
    # 'diarize': False,       # Speaker diarization
    # 'numerals': False,      # Convert numbers to digits
    # 'profanity_filter': False,  # Filter profanity
    # 'keywords': [],         # Keywords to detect
    # 'replace': [],         # Word replacements
} 