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

from backend.config.config import (
    CONFIG,
    setup_chat_client,
    conditional_print,
    log_error,
    log_startup,
    log_shutdown
)

from backend.audio.singleton import PyAudioSingleton
from backend.audio.lifecycle import shutdown_audio
from backend.stt.azure_stt import stt_instance, broadcast_stt_state, connected_websockets

# Fix: Import `get_tools` and `get_available_functions` from `functions.py`, not `helpers.py`
from backend.tools.functions import get_tools, get_available_functions

# Fix: Keep `get_function_and_args` from `helpers.py`, as it is correctly defined there
from backend.tools.helpers import get_function_and_args


from backend.models.openaisdk import validate_messages_for_ws, stream_openai_completion
from backend.tts.processor import process_streams, audio_player
from backend.endpoints.api import router as api_router


load_dotenv()

# ========================= SELECT CHAT PROVIDER =========================
client, DEPLOYMENT_NAME = setup_chat_client()

# =========== Singleton PyAudio + AudioPlayer ===========
pyaudio_instance = PyAudioSingleton()

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

                # Start audio forwarding task
                audio_forward_task = asyncio.create_task(forward_audio_to_websocket(
                    audio_queue, websocket, TTS_STOP_EVENT
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
                    await audio_forward_task

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

# Add this new function to forward audio data
async def forward_audio_to_websocket(audio_queue: asyncio.Queue, 
                                   websocket: WebSocket,
                                   stop_event: asyncio.Event):
    """Forward audio data from the queue to the WebSocket client."""
    try:
        while not stop_event.is_set():
            try:
                audio_data = await audio_queue.get()
                if audio_data is None:
                    break
                
                # Prefix audio data with 'audio:' marker
                message = b'audio:' + audio_data
                await websocket.send_bytes(message)
                
            except Exception as e:
                log_error("Error forwarding audio", e)
                break
    except Exception as e:
        log_error("Audio forwarding task error", e)

# =========== Use FastAPI's built-in shutdown event ===========
@app.on_event("shutdown")
def shutdown_event():
    """
    This hook is called by FastAPI (and thus by Uvicorn) when the server is shutting down.
    It's a good place to do final cleanup, close connections, etc.
    """
    shutdown()

# =========== Include Routers & Run ===========
app.include_router(api_router)

# ============== BACKGROUND WAKE WORD THREAD ==============

from backend.wakewords.detector import start_wake_word_thread

# =========== Startup Event ===========
@app.on_event("startup")
def start_wake_word_thread_handler():
    start_wake_word_thread()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)