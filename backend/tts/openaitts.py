import os
import asyncio
import openai
from typing import Optional

class OpenAITTS:
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "tts-1"
        self.voice = "alloy"
        self.speed = 1.0
        self.response_format = "pcm"
        self.chunk_size = 1024

    async def stream_to_audio(self, text):
        if not text.strip():
            return
        
        try:
            async with self.client.audio.speech.with_streaming_response.create(
                model=self.model,
                voice=self.voice,
                input=text.strip(),
                speed=self.speed,
                response_format=self.response_format
            ) as response:
                async for audio_chunk in response.iter_bytes(self.chunk_size):
                    yield audio_chunk
                yield b'\x00' * self.chunk_size
        except Exception:
            yield None

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
