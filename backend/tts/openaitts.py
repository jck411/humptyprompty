import os
import asyncio
import openai
from typing import Optional

from backend.config.config import CONFIG, conditional_print

async def openai_text_to_speech_processor(phrase_queue: asyncio.Queue,
                                        audio_queue: asyncio.Queue,
                                        stop_event: asyncio.Event,
                                        openai_client: Optional[openai.AsyncOpenAI] = None):
    """
    Reads phrases from phrase_queue, calls OpenAI TTS streaming,
    and pushes audio chunks to audio_queue.
    """
    openai_client = openai_client or openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    try:
        model = CONFIG["TTS_MODELS"]["OPENAI_TTS"]["TTS_MODEL"]
        voice = CONFIG["TTS_MODELS"]["OPENAI_TTS"]["TTS_VOICE"]
        speed = CONFIG["TTS_MODELS"]["OPENAI_TTS"]["TTS_SPEED"]
        response_format = CONFIG["TTS_MODELS"]["OPENAI_TTS"]["AUDIO_RESPONSE_FORMAT"]
        chunk_size = CONFIG["TTS_MODELS"]["OPENAI_TTS"]["TTS_CHUNK_SIZE"]
    except KeyError as e:
        conditional_print(f"Missing OpenAI TTS config: {e}", "default")
        await audio_queue.put(None)
        return

    try:
        while True:
            if stop_event.is_set():
                conditional_print("OpenAI TTS stop_event is set. Exiting TTS loop.", "default")
                await audio_queue.put(None)
                return

            phrase = await phrase_queue.get()
            if phrase is None:
                conditional_print("OpenAI TTS received stop signal (None).", "default")
                await audio_queue.put(None)
                return

            stripped_phrase = phrase.strip()
            if not stripped_phrase:
                continue

            try:
                async with openai_client.audio.speech.with_streaming_response.create(
                    model=model,
                    voice=voice,
                    input=stripped_phrase,
                    speed=speed,
                    response_format=response_format
                ) as response:
                    async for audio_chunk in response.iter_bytes(chunk_size):
                        if stop_event.is_set():
                            conditional_print("OpenAI TTS stop_event triggered mid-stream.", "default")
                            break
                        await audio_queue.put(audio_chunk)

                # Add a small buffer of silence between chunks
                await audio_queue.put(b'\x00' * chunk_size)
                conditional_print("OpenAI TTS synthesis completed for phrase.", "default")

            except Exception as e:
                conditional_print(f"OpenAI TTS error: {e}", "default")
                await audio_queue.put(None)
                return

    except Exception as e:
        conditional_print(f"OpenAI TTS general error: {e}", "default")
        await audio_queue.put(None)
