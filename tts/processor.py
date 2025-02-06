import asyncio
from typing import Optional, Callable

from config import CONFIG, conditional_print, log_error, log_shutdown
from stt import stt_instance, broadcast_stt_state
from audio import create_audio_player

audio_player = create_audio_player()

def audio_player_sync(audio_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event):
    """
    Blocks on an asyncio.Queue in a background thread and plays PCM data.
    Checks `stop_event.is_set()` for an early stop.
    """
    try:
        audio_player.start_stream()
        while True:
            if stop_event.is_set():
                log_shutdown("TTS stop_event is set. Audio player will stop.")
                return

            future = asyncio.run_coroutine_threadsafe(audio_queue.get(), loop)
            audio_data = future.result()

            if audio_data is None:
                log_shutdown("audio_player_sync received None (end of TTS).")
                return

            try:
                audio_player.write_audio(audio_data)
            except Exception as e:
                log_error("Audio playback error", e)
                return
    except Exception as e:
        log_error("audio_player_sync encountered an error", e)
    finally:
        audio_player.stop_stream()

async def start_audio_player_async(audio_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event):
    await asyncio.to_thread(audio_player_sync, audio_queue, loop, stop_event)

async def process_streams(phrase_queue: asyncio.Queue, audio_queue: asyncio.Queue, stop_event: asyncio.Event):
    """
    Orchestrates TTS tasks + audio playback, with an external stop_event.
    """
    if not CONFIG["GENERAL_TTS"]["TTS_ENABLED"]:
        # Just drain phrase_queue if TTS is disabled
        while True:
            phrase = await phrase_queue.get()
            if phrase is None:
                break
        return

    try:
        provider = CONFIG["GENERAL_TTS"]["TTS_PROVIDER"].lower()
        if provider == "azure":
            from .azuretts import azure_text_to_speech_processor
            tts_processor = azure_text_to_speech_processor
            playback_rate = CONFIG["TTS_MODELS"]["AZURE_TTS"]["PLAYBACK_RATE"]
        elif provider == "openai":
            from .openaitts import openai_text_to_speech_processor
            tts_processor = openai_text_to_speech_processor
            playback_rate = CONFIG["TTS_MODELS"]["OPENAI_TTS"]["PLAYBACK_RATE"]
        else:
            raise ValueError(f"Unsupported TTS provider: {provider}")

        loop = asyncio.get_running_loop()

        stt_instance.pause_listening()
        conditional_print("STT paused before starting TTS.", "segment")

        tts_task = asyncio.create_task(tts_processor(phrase_queue, audio_queue, stop_event))
        audio_player_task = asyncio.create_task(start_audio_player_async(audio_queue, loop, stop_event))
        conditional_print("Started TTS and audio playback tasks.", "default")

        await asyncio.gather(tts_task, audio_player_task)

        stt_instance.start_listening()
        conditional_print("STT resumed after completing TTS.", "segment")
        # Broadcast the resumed state
        await broadcast_stt_state()

    except Exception as e:
        conditional_print(f"Error in process_streams: {e}", "default")
        stt_instance.start_listening()
        await broadcast_stt_state()
