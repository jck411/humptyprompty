"""
Consolidated configuration settings for the frontend application.
"""
from typing import Dict, Any
import os
import logging

# -----------------------------------------------------------------------------
#                           LOGGING CONFIGURATION
# -----------------------------------------------------------------------------
LOG_CONFIG = {
    'level': logging.INFO,
    'format': "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    'date_format': "%Y-%m-%d %H:%M:%S",
    'file': None,  # Set to a path to enable file logging
}

# -----------------------------------------------------------------------------
#                           SERVER CONFIGURATION
# -----------------------------------------------------------------------------
SERVER_CONFIG = {
    'host': "127.0.0.1",
    'port': 8000,
    'websocket_path': "/ws/chat",
    'http_base_url': lambda: f"http://{SERVER_CONFIG['host']}:{SERVER_CONFIG['port']}"
}

# -----------------------------------------------------------------------------
#                           UI CONFIGURATION
# -----------------------------------------------------------------------------
# Dark theme colors
DARK_COLORS = {
    "background": "#1a1b26", 
    "user_bubble": "#3b4261", 
    "assistant_bubble": "transparent", 
    "text_primary": "#a9b1d6", 
    "text_secondary": "#565f89", 
    "button_primary": "#7aa2f7", 
    "button_hover": "#3d59a1", 
    "button_pressed": "#2ac3de", 
    "input_background": "#24283b", 
    "input_border": "#414868"      
}

# Light theme colors
LIGHT_COLORS = {
    "background": "#E8EEF5",
    "user_bubble": "#D0D7E1", 
    "assistant_bubble": "#F7F9FB", 
    "text_primary": "#1C1E21", 
    "text_secondary": "#65676B", 
    "button_primary": "#0D8BD9", 
    "button_hover": "#0A6CA8", 
    "button_pressed": "#084E7A", 
    "input_background": "#FFFFFF", 
    "input_border": "#D3D7DC"       
}

UI_CONFIG = {
    'default_theme': 'dark',
    'window_title': "Modern Chat Interface",
    'min_width': 800,
    'min_height': 600,
    'colors': {
        'dark': DARK_COLORS,
        'light': LIGHT_COLORS
    },
    'font_family': 'DejaVu Sans, sans-serif',
    'font_size': {
        'normal': 14,
        'button': 13
    }
}

# -----------------------------------------------------------------------------
#                           AUDIO CONFIGURATION
# -----------------------------------------------------------------------------
AUDIO_CONFIG = {
    'channels': 1,
    'sample_rate': 24000,
    'sample_format': 'Int16',  # For QAudioFormat
    'block_size': 4000,
    'dtype': 'float32',  # Used by sounddevice
    'volume': 1.0
}

# -----------------------------------------------------------------------------
#                           STT CONFIGURATION
# -----------------------------------------------------------------------------
STT_CONFIG = {
    'enabled': True,  # Global switch to enable/disable STT
    'auto_start': True,  # Whether to start STT automatically on initialization
    'provider': 'deepgram',  # Only provider available
    'deepgram': {
        'language': 'en-US',
        'model': 'nova-2',
        'sample_rate': 16000,
        'smart_format': True,
        'interim_results': True,
        'encoding': 'linear16',
        'channels': 1,
        'endpointing': True,
        'utterance_end_ms': 1000,
        # Additional features (disabled by default)
        'punctuate': False,      # Add punctuation automatically
        'diarize': False,       # Enable speaker diarization
        'numerals': False,      # Convert numbers to digits
        'profanity_filter': False,  # Filter profanity
        'keywords': [],         # Detect specific keywords
        'replace': []         # Replace words
    }
}

# -----------------------------------------------------------------------------
#                           ENVIRONMENT VARIABLES
# -----------------------------------------------------------------------------
def get_env_var(name: str, default: Any = None) -> Any:
    """Get an environment variable or return a default value."""
    return os.environ.get(name, default)

# Load environment variables if needed
def load_env_vars():
    """Load environment variables from .env file if dotenv is available."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        return True
    except ImportError:
        return False
