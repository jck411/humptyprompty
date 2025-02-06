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

from audio import PyAudioSingleton, shutdown_audio
from stt import stt_instance, broadcast_stt_state, connected_websockets
from tools import get_tools, get_available_functions, get_function_and_args
from models.openaisdk import validate_messages_for_ws, stream_openai_completion
from tts.processor import process_streams, audio_player

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