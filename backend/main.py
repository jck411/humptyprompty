import os
import json
import asyncio
import threading
from queue import Queue
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence, Set

import uvicorn
import pyaudio
from dotenv import load_dotenv
import openai
import re
from datetime import datetime

from fastapi import FastAPI, HTTPException, APIRouter, WebSocket, WebSocketDisconnect, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import pvporcupine
import struct

from backend.config.config import CONFIG, setup_chat_client
from backend.audio.singleton import PyAudioSingleton
from backend.audio.lifecycle import shutdown_audio
from backend.stt.azure_stt import stt_instance, broadcast_stt_state, connected_websockets
from backend.tools.functions import get_tools, get_available_functions
from backend.tools.helpers import get_function_and_args
from backend.models.openaisdk import validate_messages_for_ws, stream_openai_completion
from backend.tts.processor import process_streams, audio_player
from backend.endpoints.api import router as api_router
from backend.wakewords.detector import start_wake_word_thread
# Import the global events from the state module
from backend.endpoints.state import TTS_STOP_EVENT, GEN_STOP_EVENT

from contextlib import asynccontextmanager

load_dotenv()

client, DEPLOYMENT_NAME = setup_chat_client()

pyaudio_instance = PyAudioSingleton()

def shutdown():
    shutdown_audio(audio_player)

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_wake_word_thread()
    yield
    shutdown()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def stream_stt_to_client(websocket: WebSocket):
    while True:
        recognized_text = stt_instance.get_speech_nowait()
        if recognized_text:
            await websocket.send_json({"stt_text": recognized_text})
        await asyncio.sleep(0.05)

@app.websocket("/ws/chat")
async def unified_chat_websocket(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.add(websocket)

    # Only start STT streaming if Azure STT is the selected provider
    stt_task = None
    if CONFIG["STT_MODELS"]["PROVIDER"] == "azure":
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
                # Clear events to start fresh for the new chat.
                TTS_STOP_EVENT.clear()
                GEN_STOP_EVENT.clear()

                messages = data.get("messages", [])
                validated = await validate_messages_for_ws(messages)

                phrase_queue = asyncio.Queue()
                audio_queue = asyncio.Queue()

                stt_instance.pause_listening()
                await broadcast_stt_state()

                process_streams_task = asyncio.create_task(process_streams(
                    phrase_queue, audio_queue, TTS_STOP_EVENT
                ))

                audio_forward_task = None
                if CONFIG["GENERAL_AUDIO"]["TTS_PLAYBACK_LOCATION"] == "frontend":
                    audio_forward_task = asyncio.create_task(forward_audio_to_websocket(
                        audio_queue, websocket, TTS_STOP_EVENT
                    ))

                try:
                    async for content in stream_openai_completion(
                        client, 
                        DEPLOYMENT_NAME, 
                        validated, 
                        phrase_queue,
                        GEN_STOP_EVENT
                    ):
                        if GEN_STOP_EVENT.is_set():
                            break
                        await websocket.send_json({"content": content})
                finally:
                    await phrase_queue.put(None)
                    await process_streams_task
                    if audio_forward_task:
                        await audio_forward_task
            
            elif action == "playback-complete":
                # Received a notification from the client that TTS playback has finished.
                stt_instance.start_listening()
                await broadcast_stt_state()

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if stt_task:
            stt_task.cancel()
        connected_websockets.discard(websocket)
        stt_instance.pause_listening()
        await broadcast_stt_state()
        # If the websocket is still open, send a final state.
        try:
            await websocket.send_json({"is_listening": False})
        except Exception:
            pass
        await websocket.close()

async def forward_audio_to_websocket(
    audio_queue: asyncio.Queue, 
    websocket: WebSocket,
    stop_event: asyncio.Event
):
    try:
        while True:
            if stop_event.is_set():
                break
                
            try:
                audio_data = await audio_queue.get()
                if audio_data is None:
                    break
                message = b'audio:' + audio_data
                await websocket.send_bytes(message)
            except Exception:
                break
    except Exception:
        pass

app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
