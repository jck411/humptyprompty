#!/usr/bin/env python3
import os
from dotenv import load_dotenv

load_dotenv()

CONFIG = {
    "GENERAL_AUDIO": {
        "TTS_ENABLED": True,
        "TTS_PLAYBACK_LOCATION": "frontend",  # Always use frontend playback
        "STT_ENABLED": True,
        "STT_PROVIDER_LOCATION": "frontend",  # Now STT always works in the frontend
        "WAKEWORD_ENABLED": False,
        "PREVENT_FEEDBACK": True,  # Automatically pause STT during TTS playback
        "RESUME_DELAY_AFTER_TTS": 1.0,  # Seconds to wait before resuming STT after TTS
    },
    "STT_MODELS": {
        "PROVIDER": "deepgram",  # Only Deepgram is supported
        "DEEPGRAM_STT": {
            "LANGUAGE": "en-US",
            "MODEL": "nova-2",
            "SAMPLE_RATE": 16000,
            "SMART_FORMAT": True,
            "INTERIM_RESULTS": True,
            "ENCODING": "linear16",
            "CHANNELS": 1,
            "ENDPOINTING": True,
            "UTTERANCE_END_MS": 1000,
            "MIN_CONFIDENCE": 0.6,  # Minimum confidence threshold for accepting results
            "PUNCTUATE": True,
            "DIARIZE": False
        }
    },
    "AUDIO_SETTINGS": {
        "FORMAT": 16,
        "CHANNELS": 1,
        "RATE": 24000,
    }
}
