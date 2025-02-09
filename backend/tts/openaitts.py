import os
import asyncio
import openai
from typing import Optional

async def openai_text_to_speech_processor(phrase_queue: asyncio.Queue,
                                          audio_queue: asyncio.Queue,
                                          stop_event: asyncio.Event,
                                          openai_client: Optional[openai.AsyncOpenAI] = None):
    openai_client = openai_client or openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    try:
        model = "tts-1"
        voice = "alloy"
        speed = 1.0
        response_format = "pcm"
        chunk_size = 1024
    except KeyError:
        await audio_queue.put(None)
        return

    try:
        while True:
            if stop_event.is_set():
                await audio_queue.put(None)
                return

            phrase = await phrase_queue.get()
            if phrase is None:
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
                            break
                        await audio_queue.put(audio_chunk)
                await audio_queue.put(b'\x00' * chunk_size)
            except Exception:
                await audio_queue.put(None)
                return

    except Exception:
        await audio_queue.put(None)
