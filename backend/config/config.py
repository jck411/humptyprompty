import os
import openai
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

CONFIG: Dict[str, Any] = {
    "API_SETTINGS": {
        "API_HOST": "openai"
    },
    "API_SERVICES": {
        "openai": {
            "BASE_URL": "https://api.openai.com/v1",
            "MODEL": "gpt-4o-mini"
        },
        "openrouter": {
            "BASE_URL": "https://openrouter.ai/api/v1",
            "MODEL": "meta-llama/llama-3.1-70b-instruct"
        },
    },

    "GENERAL_TTS": {
        "TTS_PROVIDER": "azure",
        "TTS_ENABLED": True
    },

    "PROCESSING_PIPELINE": {
        "USE_SEGMENTATION": True,
        "DELIMITERS": ["\n", ". ", "? ", "! ", "* "],
        "CHARACTER_MAXIMUM": 50,
    },
    
    "TTS_MODELS": {
        "OPENAI_TTS": {
            "TTS_CHUNK_SIZE": 1024,
            "TTS_SPEED": 1.0,
            "TTS_VOICE": "alloy",
            "TTS_MODEL": "tts-1",
            "AUDIO_RESPONSE_FORMAT": "pcm",
            "AUDIO_FORMAT_RATES": {
                "pcm": 24000,
                "mp3": 44100,
                "wav": 48000
            },
            "PLAYBACK_RATE": 24000
        },
        "AZURE_TTS": {
            "TTS_SPEED": "0%",
            "TTS_VOICE": "en-US-KaiNeural",
            "SPEECH_SYNTHESIS_RATE": "0%",
            "AUDIO_FORMAT": "Raw24Khz16BitMonoPcm",
            "AUDIO_FORMAT_RATES": {
                "Raw8Khz16BitMonoPcm": 8000,
                "Raw16Khz16BitMonoPcm": 16000,
                "Raw24Khz16BitMonoPcm": 24000,
                "Raw44100Hz16BitMonoPcm": 44100,
                "Raw48Khz16BitMonoPcm": 48000
            },
            "PLAYBACK_RATE": 24000,
            "ENABLE_PROFANITY_FILTER": False,
            "STABILITY": 0,
            "PROSODY": {
                "rate": "1.0",
                "pitch": "0%",
                "volume": "default"
            }
        }
    },
    "AUDIO_PLAYBACK_CONFIG": {
        "FORMAT": 16,
        "CHANNELS": 1,
        "RATE": 24000,
        "FRONTEND_PLAYBACK": True  # Add this flag to control frontend playback
    },
    "LOGGING": {
        "PRINT_ENABLED": True,
        "PRINT_SEGMENTS": True,
        "PRINT_TOOL_CALLS": True,
        "PRINT_FUNCTION_CALLS": True
    }
}

def conditional_print(message: str, print_type: str = "default") -> None:
    """
    Print messages based on configuration settings.
    
    Args:
        message (str): The message to print
        print_type (str): Type of message ('segment', 'tool_call', 'function_call', or 'default')
    """
    if print_type == "segment" and CONFIG["LOGGING"]["PRINT_SEGMENTS"]:
        print(f"[SEGMENT] {message}")
    elif print_type == "tool_call" and CONFIG["LOGGING"]["PRINT_TOOL_CALLS"]:
        print(f"[TOOL CALL] {message}")
    elif print_type == "function_call" and CONFIG["LOGGING"]["PRINT_FUNCTION_CALLS"]:
        print(f"[FUNCTION CALL] {message}")
    elif CONFIG["LOGGING"]["PRINT_ENABLED"]:
        print(f"[INFO] {message}")

def log_error(message: str, error: Optional[Exception] = None) -> None:
    """Log error messages with optional exception details."""
    error_msg = f"[ERROR] {message}"
    if error:
        error_msg += f": {str(error)}"
    print(error_msg)

def log_startup(message: str) -> None:
    """Log startup-related messages."""
    print(f"[STARTUP] {message}")

def log_shutdown(message: str) -> None:
    """Log shutdown-related messages."""
    print(f"[SHUTDOWN] {message}")

def setup_chat_client():
    """Initialize and return the appropriate chat client based on configuration."""
    api_host = CONFIG["API_SETTINGS"]["API_HOST"].lower()

    if api_host == "openai":
        client = openai.AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=CONFIG["API_SERVICES"]["openai"]["BASE_URL"]
        )
        deployment_name = CONFIG["API_SERVICES"]["openai"]["MODEL"]

    elif api_host == "openrouter":
        client = openai.AsyncOpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url=CONFIG["API_SERVICES"]["openrouter"]["BASE_URL"]
        )
        deployment_name = CONFIG["API_SERVICES"]["openrouter"]["MODEL"]
    
    else:
        raise ValueError(f"Unsupported API_HOST: {api_host}")

    return client, deployment_name
