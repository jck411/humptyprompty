import asyncio
import logging
from typing import Optional, Callable

from backend.config.config import CONFIG
from backend.stt.azure_stt import stt_instance, broadcast_stt_state
from backend.audio.player import create_audio_player

logger = logging.getLogger(__name__)

audio_player = create_audio_player()

def audio_player_sync(audio_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event):
    """
    Blocks on an asyncio.Queue in a background thread and plays PCM data.
    Checks `stop_event.is_set()` for an early stop.
    """
    try:
        logger.debug("Starting audio stream")
        audio_player.start_stream()
        while True:
            if stop_event.is_set():
                logger.debug("Stop event set, exiting audio player")
                return

            future = asyncio.run_coroutine_threadsafe(audio_queue.get(), loop)
            audio_data = future.result()

            if audio_data is None:
                logger.debug("Received None audio data, exiting audio player")
                return

            try:
                logger.debug(f"Writing {len(audio_data)} bytes to audio stream")
                audio_player.write_audio(audio_data)
            except Exception as e:
                logger.error(f"Error writing to audio stream: {e}")
                return
    except Exception as e:
        logger.error(f"Error in audio player: {e}")
    finally:
        logger.debug("Stopping audio stream")
        audio_player.stop_stream()

async def start_audio_player_async(audio_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event):
    await asyncio.to_thread(audio_player_sync, audio_queue, loop, stop_event)

#!/usr/bin/env python3
import asyncio
from backend.config.config import CONFIG
from backend.stt.azure_stt import stt_instance, broadcast_stt_state
from backend.audio.player import create_audio_player

audio_player = create_audio_player()

async def start_audio_player_async(audio_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event):
    await asyncio.to_thread(audio_player_sync, audio_queue, loop, stop_event)

async def process_streams(phrase_queue: asyncio.Queue, audio_queue: asyncio.Queue, stop_event: asyncio.Event):
    """
    Orchestrates TTS tasks + audio playback, with an external stop_event.
    Ensures that a termination signal is sent to the audio_queue in both frontend and backend playback modes.
    """
    logger.debug(f"TTS enabled: {CONFIG['GENERAL_AUDIO']['TTS_ENABLED']}")
    logger.debug(f"TTS playback location: {CONFIG['GENERAL_AUDIO']['TTS_PLAYBACK_LOCATION']}")
    logger.debug(f"TTS provider: {CONFIG['TTS_MODELS']['PROVIDER']}")
    
    if not CONFIG["GENERAL_AUDIO"]["TTS_ENABLED"]:
        logger.debug("TTS is disabled, draining phrase queue")
        # If TTS is disabled, just drain the phrase_queue...
        while True:
            phrase = await phrase_queue.get()
            if phrase is None:
                break
        # …and signal termination to any audio forwarders.
        await audio_queue.put(None)
        return

    try:
        provider = CONFIG["TTS_MODELS"]["PROVIDER"].lower()
        if provider == "azure":
            from backend.tts.azuretts import azure_text_to_speech_processor
            tts_processor = azure_text_to_speech_processor
        elif provider == "openai":
            from backend.tts.openaitts import openai_text_to_speech_processor
            tts_processor = openai_text_to_speech_processor
        else:
            raise ValueError(f"Unsupported TTS provider: {provider}")

        loop = asyncio.get_running_loop()
        logger.debug("Pausing STT")
        stt_instance.pause_listening()

        # Start the TTS processor – it will write audio chunks into audio_queue.
        logger.debug("Starting TTS processor")
        tts_task = asyncio.create_task(tts_processor(phrase_queue, audio_queue, stop_event))
        
        if CONFIG["GENERAL_AUDIO"]["TTS_PLAYBACK_LOCATION"] == "backend":
            logger.debug("Starting backend audio playback")
            # When backend playback is enabled, start local audio playback.
            from backend.tts.processor import start_audio_player_async
            audio_player_task = asyncio.create_task(start_audio_player_async(audio_queue, loop, stop_event))
            await asyncio.gather(tts_task, audio_player_task)
        else:
            logger.debug("Using frontend playback")
            # When using frontend playback, just run the TTS task.
            await tts_task

        logger.debug("Resuming STT")
        stt_instance.start_listening()
        await broadcast_stt_state()

    except Exception as e:
        logger.error(f"Error in process_streams: {e}")
        stt_instance.start_listening()
        await broadcast_stt_state()
    finally:
        # *** IMPORTANT: Always signal termination to the audio_queue ***
        logger.debug("Signaling audio queue termination")
        await audio_queue.put(None)

from backend.config.config import CONFIG
from backend.tts.azuretts import AzureTTS
from backend.tts.openaitts import OpenAITTS

class AudioProcessor:
    def __init__(self):
        self.audio_player = create_audio_player()

    async def process_text_to_speech(self, text: str, queue: asyncio.Queue, stop_event: asyncio.Event):
        try:
            if CONFIG["TTS_MODELS"]["PROVIDER"].lower() == "azure":
                tts = AzureTTS()
            else:
                tts = OpenAITTS()

            async for chunk in tts.stream_to_audio(text):
                if stop_event.is_set():
                    break
                if chunk:
                    await queue.put(chunk)
                    # Only do playback if we're in backend mode
                    if CONFIG["GENERAL_AUDIO"]["TTS_PLAYBACK_LOCATION"] == "backend":
                        self.audio_player.write_audio(chunk)
        except Exception:
            pass

