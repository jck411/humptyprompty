import os
import json
import asyncio
import threading
from queue import Queue
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence, Set

import uvicorn
# Remove since we no longer need PyAudio for backend playback
# import pyaudio
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
# Remove these imports since we're removing backend audio
# from backend.audio.singleton import PyAudioSingleton
from backend.tools.functions import get_tools, get_available_functions
from backend.tools.helpers import get_function_and_args
from backend.models.openaisdk import validate_messages_for_ws, stream_openai_completion
from backend.tts.processor import process_streams
from backend.endpoints.api import router as api_router
from backend.wakewords.detector import start_wake_word_thread
from backend.endpoints.state import TTS_STOP_EVENT, GEN_STOP_EVENT

from contextlib import asynccontextmanager

import asyncio
import json
import logging
from typing import Dict, Optional, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from backend.config.config import CONFIG
from backend.endpoints.state import GEN_STOP_EVENT, TTS_STOP_EVENT

# ------------------------------------------------------------------------------
# Global Initialization
# ------------------------------------------------------------------------------
load_dotenv()
client, DEPLOYMENT_NAME = setup_chat_client()

def shutdown():
    pass

# ------------------------------------------------------------------------------
# Global Variables
# ------------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# FastAPI App Setup
# ------------------------------------------------------------------------------
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

# ------------------------------------------------------------------------------
# WebSocket Endpoint
# ------------------------------------------------------------------------------
@app.websocket("/ws/chat")
async def unified_chat_websocket(websocket: WebSocket):
    await websocket.accept()
    print("New WebSocket connection established")

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "chat":
                print("\nProcessing new chat message...")
                print(f"TTS Enabled: {CONFIG['GENERAL_AUDIO']['TTS_ENABLED']}")
                
                # Clear events for the new chat.
                TTS_STOP_EVENT.clear()
                GEN_STOP_EVENT.clear()

                messages = data.get("messages", [])
                validated = await validate_messages_for_ws(messages)

                phrase_queue = asyncio.Queue()
                audio_queue = asyncio.Queue()

                process_streams_task = asyncio.create_task(process_streams(
                    phrase_queue, audio_queue, TTS_STOP_EVENT
                ))

                audio_forward_task = None
                if CONFIG["GENERAL_AUDIO"].get("TTS_ENABLED", False):
                    print("Setting up frontend audio forwarding...")
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
                        print(f"Sending content chunk to TTS: {content[:50]}...")
                        await websocket.send_json({"content": content})
                finally:
                    print("Chat stream finished, cleaning up...")
                    await phrase_queue.put(None)
                    await process_streams_task
                    if audio_forward_task:
                        await audio_forward_task
                    print("Cleanup completed")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()

# ------------------------------------------------------------------------------
# Audio Forwarding Function
# ------------------------------------------------------------------------------
async def forward_audio_to_websocket(
    audio_queue: asyncio.Queue, 
    websocket: WebSocket,
    stop_event: asyncio.Event
):
    try:
        while True:
            if stop_event.is_set():
                print("Audio forwarding stopped by stop event")
                await websocket.send_bytes(b'audio:')  # Send empty audio marker
                break

            try:
                audio_data = await audio_queue.get()
                if audio_data is None:
                    print("Received None in audio queue, sending audio end marker")
                    await websocket.send_bytes(b'audio:')
                    break
                # Prepend "audio:" if not already present.
                message = b'audio:' + audio_data if not audio_data.startswith(b'audio:') else audio_data
                await websocket.send_bytes(message)
            except Exception as e:
                print(f"Error forwarding audio to websocket: {e}")
                break
    except Exception as e:
        print(f"Forward audio task error: {e}")
    finally:
        try:
            await websocket.send_bytes(b'audio:')
        except Exception as e:
            print(f"Error sending final empty message: {e}")

# ------------------------------------------------------------------------------
# Include Additional API Routes & Run Uvicorn
# ------------------------------------------------------------------------------
app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
