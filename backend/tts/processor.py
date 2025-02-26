import asyncio
import logging
from typing import Optional, Callable

from backend.config.config import CONFIG
from backend.audio.player import create_audio_player
from backend.stt.azure_stt import stt_instance

logger = logging.getLogger(__name__)

audio_player = create_audio_player()

async def audio_player_sync(audio_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event):
    """
    Non-blocking audio playback function that processes audio data from the queue
    without blocking the main event loop.
    
    This is a replacement for the original blocking implementation.
    """
    try:
        logger.debug("Starting audio stream")
        audio_player.start_stream()
        
        while True:
            if stop_event.is_set():
                logger.debug("Stop event set, exiting audio player")
                break
                
            try:
                # Wait for data with a timeout to keep the function non-blocking
                audio_data = await asyncio.wait_for(audio_queue.get(), timeout=0.1)
                
                if audio_data is None:
                    logger.debug("Received None audio data, exiting audio player")
                    break
                    
                # Write audio data in small executor task to avoid blocking
                def write_audio():
                    try:
                        audio_player.write_audio(audio_data)
                        return True
                    except Exception as e:
                        logger.error(f"Error writing to audio stream: {e}")
                        return False
                
                # Use run_in_executor for potentially blocking audio operations
                await loop.run_in_executor(None, write_audio)
                
            except asyncio.TimeoutError:
                # This is expected behavior - just check stop event and continue
                continue
            except Exception as e:
                logger.error(f"Error in audio player: {e}")
                break
                
    except Exception as e:
        logger.error(f"Audio player error: {e}")
    finally:
        logger.debug("Stopping audio stream")
        # Use run_in_executor for potentially blocking audio operations
        await loop.run_in_executor(None, audio_player.stop_stream)
        
        # Call playback complete callback to handle STT resumption and state broadcasting
        if audio_player.on_playback_complete:
            # No need for run_coroutine_threadsafe since we're already in an async function
            await audio_player.on_playback_complete()

async def start_audio_player_async(audio_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event):
    """
    Directly handles audio playback asynchronously without spawning a new thread.
    This improves responsiveness and eliminates blocking calls.
    """
    await audio_player_sync(audio_queue, loop, stop_event)

def format_audio_message(audio_data: bytes) -> bytes:
    """Ensures consistent audio message formatting with the 'audio:' prefix"""
    if audio_data is None:
        return b'audio:'  # End of stream marker
    return b'audio:' + audio_data if not audio_data.startswith(b'audio:') else audio_data

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

        # If using backend playback, handle audio playback here
        if CONFIG["GENERAL_AUDIO"]["TTS_PLAYBACK_LOCATION"] == "backend":
            logger.debug("Using backend playback")
            try:
                audio_task = asyncio.create_task(
                    start_audio_player_async(audio_queue, asyncio.get_running_loop(), stop_event)
                )
                await asyncio.gather(tts_task, audio_task)
            except Exception as e:
                logger.error(f"Error in backend playback: {e}")
            finally:
                # Let the audio_player handle STT resumption through its completion callback
                pass
        else:
            logger.debug("Using frontend playback")
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
