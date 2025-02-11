#!/usr/bin/env python3
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
        "TTS_ENABLED": False
    },
    "PROCESSING_PIPELINE": {
        "USE_SEGMENTATION": True,
        "DELIMITERS": ["\n", ". ", "? ", "! ", "* "],
        "CHARACTER_MAXIMUM": 50, # will only segment for the initial characters listed here, the rest will just stream
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
        "FRONTEND_PLAYBACK": True
    },
    "LOGGING": {
        "PRINT_SEGMENTS": True,
        "PRINT_TOOL_CALLS": False,
         "PRINT_FUNCTION_CALLS": False

    },
    "STT_SETTINGS": {
        "LOCATION": "backend",  # Use "backend" for Azure STT or "frontend" for browser-based STT
        "BACKEND_STT": {
            "PROVIDER": "azure",
            "LANGUAGE": "en-US",
            "CONTINUOUS_RECOGNITION": True,
            "PROFANITY_OPTION": "raw",
            "AUTO_PUNCTUATION": True,
            "INTERIM_RESULTS": False
        },
        "FRONTEND_STT": {
            "PROVIDER": "browser",
            "LANGUAGE": "en-US",
            "CONTINUOUS_RECOGNITION": True,
            "INTERIM_RESULTS": True,
            "MAX_ALTERNATIVES": 1,
            "AUTO_START": False
        }
    }
}

def setup_chat_client():
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
