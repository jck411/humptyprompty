import asyncio
from typing import Optional, Callable

from backend.config.config import CONFIG
from backend.stt.azure_stt import stt_instance, broadcast_stt_state
from backend.audio.player import create_audio_player

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
                return

            future = asyncio.run_coroutine_threadsafe(audio_queue.get(), loop)
            audio_data = future.result()

            if audio_data is None:
                return

            try:
                audio_player.write_audio(audio_data)
            except Exception:
                return
    except Exception:
        pass
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
            from backend.tts.azuretts import azure_text_to_speech_processor
            tts_processor = azure_text_to_speech_processor
            playback_rate = CONFIG["TTS_MODELS"]["AZURE_TTS"]["PLAYBACK_RATE"]
        elif provider == "openai":
            from backend.tts.openaitts import openai_text_to_speech_processor
            tts_processor = openai_text_to_speech_processor
            playback_rate = CONFIG["TTS_MODELS"]["OPENAI_TTS"]["PLAYBACK_RATE"]
        else:
            raise ValueError(f"Unsupported TTS provider: {provider}")

        loop = asyncio.get_running_loop()

        stt_instance.pause_listening()

        tts_task = asyncio.create_task(tts_processor(phrase_queue, audio_queue, stop_event))
        
        # Only start local audio playback if frontend playback is disabled
        if not CONFIG["AUDIO_PLAYBACK_CONFIG"]["FRONTEND_PLAYBACK"]:
            audio_player_task = asyncio.create_task(
                start_audio_player_async(audio_queue, loop, stop_event)
            )
            await asyncio.gather(tts_task, audio_player_task)
        else:
            await tts_task

        stt_instance.start_listening()
        await broadcast_stt_state()

    except Exception:
        stt_instance.start_listening()
        await broadcast_stt_state()
