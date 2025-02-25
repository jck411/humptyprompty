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
from backend.tools.functions import get_tools, get_available_functions
from backend.tools.helpers import get_function_and_args
from backend.models.openaisdk import validate_messages_for_ws, stream_openai_completion
from backend.tts.processor import process_streams, audio_player
from backend.endpoints.api import router as api_router
from backend.wakewords.detector import start_wake_word_thread
from backend.stt.azure_stt import stt_instance
from backend.endpoints.state import TTS_STOP_EVENT, GEN_STOP_EVENT

from contextlib import asynccontextmanager

# ------------------------------------------------------------------------------
# Global Initialization
# ------------------------------------------------------------------------------
load_dotenv()
client, DEPLOYMENT_NAME = setup_chat_client()
pyaudio_instance = PyAudioSingleton()

def shutdown():
    shutdown_audio(audio_player)

# Move handle_playback_complete before setup_audio_player
async def handle_playback_complete():
    """Callback for when audio playback completes"""
    print("Backend audio playback complete, resuming STT...")
    try:
        if CONFIG["GENERAL_AUDIO"]["STT_ENABLED"]:
            await stt_manager.start(update_global=False)
            await stt_manager.broadcast_state()
    except Exception as e:
        print(f"Error in playback complete handler: {e}")

async def setup_audio_player():
    """Set up audio player callback"""
    print("Setting up audio player callback...")
    audio_player.set_main_loop(asyncio.get_running_loop())
    audio_player.on_playback_complete = handle_playback_complete

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_wake_word_thread()
    await setup_audio_player()  # This now sets the main loop
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
# Centralized STT Manager
# ------------------------------------------------------------------------------
class STTManager:
    def __init__(self, config, stt_instance):
        self.config = config
        self.stt_instance = stt_instance
        # Set of websockets for state broadcasts.
        self.websocket_clients: Set[WebSocket] = set()
        # Maintain a mapping of websocket to its associated STT streaming task.
        self.stt_tasks: Dict[WebSocket, asyncio.Task] = {}

    async def start(self, update_global: bool = True):
        print("STTManager: Starting STT")
        if update_global:
            self.config["GENERAL_AUDIO"]["STT_ENABLED"] = True
        await self.stt_instance.start_listening()

    def pause(self, update_global: bool = True):
        print("STTManager: Pausing STT")
        self.stt_instance.pause_listening()
        if update_global:
            self.config["GENERAL_AUDIO"]["STT_ENABLED"] = False

    async def broadcast_state(self):
        message = {
            "type": "stt_state",
            "is_listening": self.stt_instance.is_listening,
            "is_enabled": self.config["GENERAL_AUDIO"]["STT_ENABLED"]
        }
        print(f"Broadcasting STT state: {message}")  # Add this debug line
        failed_ws = set()
        for ws in self.websocket_clients:
            try:
                await ws.send_json(message)
            except Exception as e:
                print(f"STTManager: Error broadcasting state: {e}")
                failed_ws.add(ws)
        self.websocket_clients.difference_update(failed_ws)

    async def stream_stt(self, websocket: WebSocket):
        print("STTManager: Starting STT stream for a websocket")
        try:
            while True:
                if not self.config["GENERAL_AUDIO"]["STT_ENABLED"]:
                    print("STTManager: STT disabled, waiting...")
                    await asyncio.sleep(0.5)
                    continue

                if not self.stt_instance.is_listening:
                    await asyncio.sleep(0.1)
                    continue

                try:
                    recognized_text = self.stt_instance.get_speech_nowait()
                    if recognized_text:
                        # Remove "(interim)" prefix for cleaner output
                        if recognized_text.startswith("(interim) "):
                            recognized_text = recognized_text[10:]
                        message = {"type": "stt", "stt_text": recognized_text}
                        try:
                            await websocket.send_json(message)
                        except Exception as e:
                            print(f"STTManager: Error sending STT message: {e}")
                            break
                except Exception as e:
                    print(f"STTManager: Error getting speech: {e}")
                    await asyncio.sleep(0.1)
                    continue

                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            print("STTManager: STT stream task cancelled")
            raise
        except Exception as e:
            print(f"STTManager: Unexpected error in STT stream: {e}")
            raise

    async def cleanup(self, websocket: WebSocket):
        print("STTManager: Cleaning up for a websocket")
        if websocket in self.stt_tasks:
            task = self.stt_tasks[websocket]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self.stt_tasks[websocket]
        self.pause(update_global=True)
        await self.broadcast_state()
        try:
            await websocket.send_json({"is_listening": False})
        except Exception as e:
            print(f"STTManager: Error sending cleanup state: {e}")

# Instantiate the STTManager
stt_manager = STTManager(CONFIG, stt_instance)

# ------------------------------------------------------------------------------
# WebSocket Endpoint
# ------------------------------------------------------------------------------
@app.websocket("/ws/chat")
async def unified_chat_websocket(websocket: WebSocket):
    await websocket.accept()
    stt_manager.websocket_clients.add(websocket)
    
    # Start the STT streaming task for this websocket
    stt_task = asyncio.create_task(stt_manager.stream_stt(websocket))
    stt_manager.stt_tasks[websocket] = stt_task

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            
            if action in ["start-stt", "pause-stt"]:
                if action == "start-stt":
                    await stt_manager.start(update_global=True)
                elif action == "pause-stt":
                    stt_manager.pause(update_global=True)
                await stt_manager.broadcast_state()

            elif action == "playback-complete":
                # Resume STT only if globally enabled.
                if not CONFIG["GENERAL_AUDIO"]["STT_ENABLED"]:
                    print("Server: Global STT is disabled; not resuming listening after playback complete.")
                else:
                    if CONFIG["GENERAL_AUDIO"].get("TTS_ENABLED", False):
                        if CONFIG["GENERAL_AUDIO"]["TTS_PLAYBACK_LOCATION"] == "frontend":
                            print("Server: Received frontend playback-complete message, resuming STT...")
                            await stt_manager.start(update_global=False)
                        else:
                            print("Server: Ignoring playback-complete message (backend playback mode)")
                    else:
                        if not stt_instance.is_listening:
                            print("Server: TTS is off but STT is not listening; resuming STT listening...")
                            await stt_manager.start(update_global=False)
                        else:
                            print("Server: TTS is off and STT is already listening.")
                    await stt_manager.broadcast_state()

            elif action == "chat":
                print("\nProcessing new chat message...")
                print(f"TTS Enabled: {CONFIG['GENERAL_AUDIO']['TTS_ENABLED']}")
                print(f"TTS Location: {CONFIG['GENERAL_AUDIO']['TTS_PLAYBACK_LOCATION']}")
                
                # Clear events for the new chat.
                TTS_STOP_EVENT.clear()
                GEN_STOP_EVENT.clear()

                messages = data.get("messages", [])
                validated = await validate_messages_for_ws(messages)

                phrase_queue = asyncio.Queue()
                audio_queue = asyncio.Queue()

                # For a chat, if TTS is enabled, pause STT temporarily without changing global flag.
                if CONFIG["GENERAL_AUDIO"].get("TTS_ENABLED", False):
                    stt_manager.pause(update_global=False)
                    await stt_manager.broadcast_state()
                else:
                    print("TTS is off; leaving STT listening state unchanged.")

                process_streams_task = asyncio.create_task(process_streams(
                    phrase_queue, audio_queue, TTS_STOP_EVENT
                ))

                audio_forward_task = None
                if (CONFIG["GENERAL_AUDIO"]["TTS_PLAYBACK_LOCATION"] == "frontend" and 
                    CONFIG["GENERAL_AUDIO"].get("TTS_ENABLED", False)):
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
        await stt_manager.cleanup(websocket)
        stt_manager.websocket_clients.discard(websocket)
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
