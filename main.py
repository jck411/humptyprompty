import os
import json
import asyncio
import signal
import threading
import requests  
import openai
import inspect
import re
from datetime import datetime
from queue import Queue
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Sequence, Tuple, Union, Set

import uvicorn
import pyaudio
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
import pytz
from timezonefinder import TimezoneFinder

from fastapi import FastAPI, HTTPException, APIRouter, WebSocket, WebSocketDisconnect, Request, Response, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import pvporcupine
import struct

from config import (
    CONFIG,
    setup_chat_client,
    conditional_print,
    log_error,
    log_startup,
    log_shutdown
)

from audio import create_audio_player, PyAudioSingleton, shutdown_audio
from stt import stt_instance, broadcast_stt_state, connected_websockets
from tools import get_tools, get_available_functions, get_function_and_args
from models.openaisdk import validate_messages_for_ws, stream_openai_completion

load_dotenv()

# ========================= SELECT CHAT PROVIDER =========================
client, DEPLOYMENT_NAME = setup_chat_client()

# =========== Singleton PyAudio + AudioPlayer ===========
pyaudio_instance = PyAudioSingleton()

audio_player = create_audio_player()

# =========== Global Stop Events ===========
TTS_STOP_EVENT = asyncio.Event()
GEN_STOP_EVENT = asyncio.Event()

# ------------ Shutdown Handler ------------
def shutdown():
    """
    Gracefully close streams and terminate services.
    """
    log_shutdown("Shutting down server...")
    shutdown_audio(audio_player)
    log_shutdown("Shutdown complete.")

# =========== Tools & Function Calls ===========

# =========== Audio Player & TTS ===========
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

class PushAudioOutputStreamCallback(speechsdk.audio.PushAudioOutputStreamCallback):
    def __init__(self, audio_queue: asyncio.Queue, stop_event: asyncio.Event):
        super().__init__()
        self.audio_queue = audio_queue
        self.stop_event = stop_event
        self.loop = asyncio.get_event_loop()

    def write(self, data: memoryview) -> int:
        if self.stop_event.is_set():
            return 0
        self.loop.call_soon_threadsafe(self.audio_queue.put_nowait, data.tobytes())
        return len(data)

    def close(self):
        self.loop.call_soon_threadsafe(self.audio_queue.put_nowait, None)

def create_ssml(phrase: str, voice: str, prosody: dict) -> str:
    return f"""
<speak version='1.0' xml:lang='en-US'>
    <voice name='{voice}'>
        <prosody rate='{prosody["rate"]}' pitch='{prosody["pitch"]}' volume='{prosody["volume"]}'>
            {phrase}
        </prosody>
    </voice>
</speak>
"""

async def azure_text_to_speech_processor(phrase_queue: asyncio.Queue,
                                         audio_queue: asyncio.Queue,
                                         stop_event: asyncio.Event):
    """
    Continuously read text from phrase_queue, convert to speech with Azure TTS,
    and push PCM data into audio_queue. Stops early if stop_event is set.
    """
    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=os.getenv("AZURE_SPEECH_KEY"),
            region=os.getenv("AZURE_SPEECH_REGION")
        )
        prosody = CONFIG["TTS_MODELS"]["AZURE_TTS"]["PROSODY"]
        voice = CONFIG["TTS_MODELS"]["AZURE_TTS"]["TTS_VOICE"]
        audio_format = getattr(
            speechsdk.SpeechSynthesisOutputFormat,
            CONFIG["TTS_MODELS"]["AZURE_TTS"]["AUDIO_FORMAT"]
        )
        speech_config.set_speech_synthesis_output_format(audio_format)
        conditional_print("Azure TTS configured successfully.", "default")

        while True:
            if stop_event.is_set():
                conditional_print("Azure TTS stop_event is set. Exiting TTS loop.", "default")
                await audio_queue.put(None)
                return

            phrase = await phrase_queue.get()
            if phrase is None or phrase.strip() == "":
                await audio_queue.put(None)
                conditional_print("Azure TTS received stop signal (None).", "default")
                return

            try:
                ssml_phrase = create_ssml(phrase, voice, prosody)
                push_stream_callback = PushAudioOutputStreamCallback(audio_queue, stop_event)
                push_stream = speechsdk.audio.PushAudioOutputStream(push_stream_callback)
                audio_cfg = speechsdk.audio.AudioOutputConfig(stream=push_stream)

                synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_cfg)
                result_future = synthesizer.speak_ssml_async(ssml_phrase)
                conditional_print(f"Azure TTS synthesizing phrase: {phrase}", "default")
                await asyncio.get_event_loop().run_in_executor(None, result_future.get)
                conditional_print("Azure TTS synthesis completed.", "default")

            except Exception as e:
                conditional_print(f"Azure TTS error: {e}", "default")
                await audio_queue.put(None)
                return

    except Exception as e:
        conditional_print(f"Azure TTS config error: {e}", "default")
        await audio_queue.put(None)

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
            tts_processor = azure_text_to_speech_processor
            playback_rate = CONFIG["TTS_MODELS"]["AZURE_TTS"]["PLAYBACK_RATE"]
        elif provider == "openai":
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

# =========== Streaming Chat Logic ===========

# =========== FastAPI Setup ===========
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
router = APIRouter()

@app.options("/api/options")
async def openai_options():
    return Response(status_code=200)

# ---- Wakeword start stt Endpoint ----
@app.post("/api/start-stt")
async def start_stt_endpoint():
    """
    If STT is currently paused, this starts listening again.
    Otherwise it does nothing.
    """
    if not stt_instance.is_listening:
        stt_instance.start_listening()
        await broadcast_stt_state()
    return {"detail": "STT is now ON."}

# ---- Pause stt Endpoint ----
@app.post("/api/pause-stt")
async def pause_stt_endpoint():
    """
    If STT is currently listening, this pauses it.
    Otherwise it does nothing.
    """
    if stt_instance.is_listening:
        stt_instance.pause_listening()
        await broadcast_stt_state()
    return {"detail": "STT is now OFF."}

# ---- Audio Playback Toggle Endpoint ----
@app.post("/api/toggle-audio")
async def toggle_audio_playback():
    try:
        if audio_player.is_playing:
            audio_player.stop_stream()
            return {"audio_playing": False}
        else:
            audio_player.start_stream()
            return {"audio_playing": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle audio playback: {str(e)}")

# ---- TTS Toggle Endpoint ----
@app.post("/api/toggle-tts")
async def toggle_tts():
    try:
        current_status = CONFIG["GENERAL_TTS"]["TTS_ENABLED"]
        CONFIG["GENERAL_TTS"]["TTS_ENABLED"] = not current_status
        await broadcast_stt_state()  # Optional: If TTS state affects is_listening
        return {"tts_enabled": CONFIG["GENERAL_TTS"]["TTS_ENABLED"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle TTS: {str(e)}")

# ---- Stop TTS Endpoint ----
@app.post("/api/stop-tts")
async def stop_tts():
    """
    Manually set the global TTS_STOP_EVENT.
    Any ongoing TTS/audio streaming will stop soon after it checks the event.
    """
    TTS_STOP_EVENT.set()
    return {"detail": "TTS stop event triggered. Ongoing TTS tasks should exit soon."}

# ---- Stop Text Generation Endpoint ----
@app.post("/api/stop-generation")
async def stop_generation():
    """
    Manually set the global GEN_STOP_EVENT.
    Any ongoing streaming text generation will stop soon after it checks the event.
    """
    GEN_STOP_EVENT.set()
    return {"detail": "Generation stop event triggered. Ongoing text generation will exit soon."}

# ---- Unified WebSocket Endpoint ----
async def stream_stt_to_client(websocket: WebSocket):
    while True:
        recognized_text = stt_instance.get_speech_nowait()
        if recognized_text:
            await websocket.send_json({"stt_text": recognized_text})
        await asyncio.sleep(0.05)

@app.websocket("/ws/chat")
async def unified_chat_websocket(websocket: WebSocket):
    await websocket.accept()
    log_startup("Client connected to /ws/chat")
    connected_websockets.add(websocket)

    # Start a background task that streams recognized STT text
    stt_task = asyncio.create_task(stream_stt_to_client(websocket))

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "start-stt":
                stt_instance.start_listening()
                await broadcast_stt_state()

            elif action == "pause-stt":
                stt_instance.pause_listening()
                await broadcast_stt_state()

            elif action == "chat":
                # Clear any old stop events
                TTS_STOP_EVENT.clear()
                GEN_STOP_EVENT.clear()

                messages = data.get("messages", [])
                validated = await validate_messages_for_ws(messages)

                phrase_queue = asyncio.Queue()
                audio_queue = asyncio.Queue()

                stt_instance.pause_listening()
                await broadcast_stt_state()
                conditional_print("STT paused before processing chat.", "segment")

                # Launch TTS and audio processing
                process_streams_task = asyncio.create_task(process_streams(
                    phrase_queue, audio_queue, TTS_STOP_EVENT
                ))

                # Stream the chat completion
                try:
                    async for content in stream_openai_completion(
                        client, 
                        DEPLOYMENT_NAME, 
                        validated, 
                        phrase_queue,
                        GEN_STOP_EVENT
                    ):
                        if GEN_STOP_EVENT.is_set():
                            conditional_print("GEN_STOP_EVENT is set, halting chat streaming to client.", "default")
                            break
                        await websocket.send_json({"content": content})
                finally:
                    # Signal end of TTS text
                    await phrase_queue.put(None)
                    await process_streams_task

                    # Resume STT after TTS
                    stt_instance.start_listening()
                    await broadcast_stt_state()
                    conditional_print("STT resumed after processing chat.", "segment")

    except WebSocketDisconnect:
        log_shutdown("Client disconnected from /ws/chat")
    except Exception as e:
        log_error("WebSocket error in unified_chat_websocket", e)
    finally:
        stt_task.cancel()
        connected_websockets.discard(websocket)
        stt_instance.pause_listening()
        await broadcast_stt_state()
        await websocket.send_json({"is_listening": False})
        await websocket.close()

# =========== Use FastAPI's built-in shutdown event ===========
@app.on_event("shutdown")
def shutdown_event():
    """
    This hook is called by FastAPI (and thus by Uvicorn) when the server is shutting down.
    It's a good place to do final cleanup, close connections, etc.
    """
    shutdown()

# =========== Include Routers & Run ===========
app.include_router(router)

# ============== BACKGROUND WAKE WORD THREAD ==============

from wakewords.detector import start_wake_word_thread

# =========== Startup Event ===========
@app.on_event("startup")
def start_wake_word_thread_handler():
    start_wake_word_thread()

if __name__ == '__main__':
    # Let uvicorn handle Ctrl+C and signals cleanly.
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # Set to True if you want auto-reload in development
    )