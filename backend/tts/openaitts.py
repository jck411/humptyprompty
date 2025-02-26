import os
import asyncio
import openai
from typing import Optional
from ..config.config import CONFIG

class OpenAITTS:
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = CONFIG["TTS_MODELS"]["OPENAI_TTS"]["TTS_MODEL"]
        self.voice = CONFIG["TTS_MODELS"]["OPENAI_TTS"]["TTS_VOICE"]
        self.speed = CONFIG["TTS_MODELS"]["OPENAI_TTS"]["TTS_SPEED"]
        self.response_format = CONFIG["TTS_MODELS"]["OPENAI_TTS"]["AUDIO_RESPONSE_FORMAT"]
        self.chunk_size = CONFIG["TTS_MODELS"]["OPENAI_TTS"]["TTS_CHUNK_SIZE"]

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
        model = CONFIG["TTS_MODELS"]["OPENAI_TTS"]["TTS_MODEL"]
        voice = CONFIG["TTS_MODELS"]["OPENAI_TTS"]["TTS_VOICE"]
        speed = CONFIG["TTS_MODELS"]["OPENAI_TTS"]["TTS_SPEED"]
        response_format = CONFIG["TTS_MODELS"]["OPENAI_TTS"]["AUDIO_RESPONSE_FORMAT"]
        chunk_size = CONFIG["TTS_MODELS"]["OPENAI_TTS"]["TTS_CHUNK_SIZE"]
        buffer_size = CONFIG["TTS_MODELS"]["OPENAI_TTS"]["BUFFER_SIZE"]
    except KeyError:
        await audio_queue.put(None)
        return

    try:
        audio_buffer = bytearray()
        
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
                            
                        # Add chunk to buffer
                        audio_buffer.extend(audio_chunk)
                        
                        # When buffer reaches threshold, send it
                        if len(audio_buffer) >= buffer_size:
                            await audio_queue.put(bytes(audio_buffer))
                            audio_buffer.clear()
                    
                    # Send any remaining buffered audio
                    if audio_buffer:
                        await audio_queue.put(bytes(audio_buffer))
                        audio_buffer.clear()
                        
                    # Add a small silence gap between phrases
                    await audio_queue.put(b'\x00' * chunk_size)
                    
            except Exception as e:
                print(f"Error in OpenAI TTS streaming: {e}")
                await audio_queue.put(None)
                return

    except Exception as e:
        print(f"Error in OpenAI TTS processor: {e}")
        await audio_queue.put(None)
