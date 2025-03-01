import asyncio
import logging
from typing import Optional, Callable

from backend.config.config import CONFIG
from backend.stt.provider import stt_instance

logger = logging.getLogger(__name__)

def format_audio_message(audio_data: bytes) -> bytes:
    """Ensures consistent audio message formatting with the 'audio:' prefix"""
    if audio_data is None:
        return b'audio:'  # End of stream marker
    return b'audio:' + audio_data if not audio_data.startswith(b'audio:') else audio_data

async def process_streams(phrase_queue: asyncio.Queue, audio_queue: asyncio.Queue, stop_event: asyncio.Event):
    """
    Orchestrates TTS tasks, with an external stop_event.
    Ensures that a termination signal is sent to the audio_queue.
    """
    logger.debug(f"TTS enabled: {CONFIG['GENERAL_AUDIO']['TTS_ENABLED']}")
    logger.debug(f"TTS provider: {CONFIG['TTS_MODELS']['PROVIDER']}")
    
    if not CONFIG["GENERAL_AUDIO"]["TTS_ENABLED"]:
        logger.debug("TTS is disabled, draining phrase queue")
        while True:
            phrase = await phrase_queue.get()
            if phrase is None:
                break
        await audio_queue.put(None)
        return

    try:
        provider = CONFIG["TTS_MODELS"]["PROVIDER"].lower()
        if provider == "azure":
            from backend.tts.azuretts import azure_text_to_speech_processor
            tts_task = azure_text_to_speech_processor(phrase_queue, audio_queue, stop_event)
        elif provider == "openai":
            from backend.tts.openaitts import openai_text_to_speech_processor
            tts_task = openai_text_to_speech_processor(phrase_queue, audio_queue, stop_event)
        else:
            logger.error(f"Unknown TTS provider: {provider}")
            return

        # Process TTS and send audio to frontend
        logger.debug("Processing TTS for frontend playback")
        await tts_task

    except Exception as e:
        logger.error(f"Error in process_streams: {e}")
    finally:
        # Signal termination
        logger.debug("Signaling audio queue termination")
        await audio_queue.put(None)

from backend.tts.azuretts import AzureTTS
from backend.tts.openaitts import OpenAITTS

class AudioProcessor:
    def __init__(self):
        self.azure_tts = AzureTTS()
        self.openai_tts = OpenAITTS()
