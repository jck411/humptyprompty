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
from backend.stt.provider import stt_instance
from backend.endpoints.state import TTS_STOP_EVENT, GEN_STOP_EVENT

from contextlib import asynccontextmanager

import asyncio
import json
import logging
from typing import Dict, Optional, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from backend.config.config import CONFIG
from backend.stt.provider import stt_instance, create_stt_instance
from backend.endpoints.api import router
from backend.endpoints.state import GEN_STOP_EVENT, TTS_STOP_EVENT

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
            # Always broadcast state regardless of playback location
            await stt_manager.broadcast_state()
    except Exception as e:
        print(f"Error in playback complete handler: {e}")

async def setup_audio_player():
    """Set up audio player callback"""
    print("Setting up audio player callback...")
    audio_player.set_main_loop(asyncio.get_running_loop())
    audio_player.on_playback_complete = handle_playback_complete

# ------------------------------------------------------------------------------
# Global Variables
# ------------------------------------------------------------------------------
logger = logging.getLogger(__name__)
# Global reference to STTManager instance
stt_manager: Optional['STTManager'] = None

# ------------------------------------------------------------------------------
# Initialization Functions
# ------------------------------------------------------------------------------
def create_stt_manager():
    global stt_manager
    stt_manager = STTManager(CONFIG, stt_instance)
    return stt_manager

# ------------------------------------------------------------------------------
# Centralized STT Manager (Revised with Thread-Safe Shared Data Structures)
# ------------------------------------------------------------------------------
class STTManager:
    def __init__(self, config, stt_instance):
        self.config = config
        self._stt_instance = stt_instance  # Make this private
        # Set of websockets for state broadcasts, protected by an async lock
        self.websocket_clients: Set[WebSocket] = set()
        self.websocket_clients_lock = asyncio.Lock()
        # Internal event to track whether STT is active
        self._listening_event = asyncio.Event()
        # A single task that awaits new speech results
        self._listen_task: Optional[asyncio.Task] = None
        # Create asyncio Queue for speech results
        self._speech_queue = asyncio.Queue()
        # Start the queue monitoring task
        self._queue_monitor_task = None

    @property
    def stt_instance(self):
        return self._stt_instance

    @stt_instance.setter
    def stt_instance(self, new_instance):
        """Safely update the STT instance"""
        was_listening = self._stt_instance.is_listening
        self._stt_instance = new_instance
        if was_listening:
            asyncio.create_task(self.start(update_global=False))

    async def _monitor_speech_queue(self):
        """
        Non-blocking task that monitors the speech queue and transfers items
        to the asyncio queue for processing.
        """
        try:
            while True:
                if not self._listening_event.is_set():
                    await asyncio.sleep(0.1)
                    continue
                
                # Check if there's any data in the speech queue, without blocking
                try:
                    # Use a very short timeout to avoid blocking
                    if not self.stt_instance.speech_queue.empty():
                        recognized_text = self.stt_instance.speech_queue.get_nowait()
                        if recognized_text is not None:
                            await self._speech_queue.put(recognized_text)
                except Exception as e:
                    print(f"STTManager: Error checking speech queue: {e}")
                
                await asyncio.sleep(0.01)  # Short sleep to prevent tight loop
        except asyncio.CancelledError:
            print("STTManager: Queue monitor task cancelled")
        except Exception as e:
            print(f"STTManager: Exception in queue monitor: {e}")

    async def _speech_listener(self):
        """
        Awaits new speech results from the asyncio queue and
        broadcasts them immediately to all connected websockets.
        """
        try:
            while self._listening_event.is_set():
                try:
                    # Use asyncio.wait_for to add a timeout
                    recognized_text = await asyncio.wait_for(
                        self._speech_queue.get(), 
                        timeout=0.1
                    )
                    
                    # Immediately process and broadcast final results
                    if recognized_text.startswith("[final] "):
                        text = recognized_text[8:]
                        await self._broadcast_speech(text)
                    
                except asyncio.TimeoutError:
                    # Just continue the loop - this is expected behavior
                    continue
                except Exception as e:
                    print(f"STTManager: Error processing speech result: {e}")
                    await asyncio.sleep(0.01)  # Prevent tight loop on error
                    
        except asyncio.CancelledError:
            print("STTManager: Speech listener task cancelled")
        except Exception as e:
            print(f"STTManager: Exception in speech listener: {e}")
        finally:
            print("STTManager: Speech listener task ending")

    async def _send_json(self, ws: WebSocket, message: Dict):
        await ws.send_json(message)

    async def _broadcast_speech(self, recognized_text: str):
        """
        Broadcasts the recognized speech to all websocket clients immediately.
        """
        message = {
            "type": "stt",
            "stt_text": recognized_text
        }
        print(f"\nBroadcasting STT message: {message}")
        async with self.websocket_clients_lock:
            ws_list = list(self.websocket_clients)
        tasks = [self._send_json(ws, message) for ws in ws_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for ws, result in zip(ws_list, results):
            if isinstance(result, Exception):
                print(f"STTManager: Error broadcasting speech to websocket: {result}")
                async with self.websocket_clients_lock:
                    self.websocket_clients.discard(ws)

    async def start(self, update_global: bool = True):
        """
        Starts STT listening by calling the underlying provider and setting
        the internal event. Also ensures the speech listener task is running.
        """
        print("STTManager: Starting STT")
        
        # Set the event first to ensure no transcriptions are missed
        self._listening_event.set()
        
        # Start the queue monitor task if it's not running
        if self._queue_monitor_task is None or self._queue_monitor_task.done():
            self._queue_monitor_task = asyncio.create_task(self._monitor_speech_queue())
        
        # Start the speech listener task before starting recognition
        if self._listen_task is None or self._listen_task.done():
            self._listen_task = asyncio.create_task(self._speech_listener())
        
        try:
            await self.stt_instance.start_listening()
        except Exception as e:
            print(f"STTManager: Error starting stt_instance: {e}")
            self._listening_event.clear()
            if self._listen_task:
                self._listen_task.cancel()
            return

        if update_global:
            self.config["GENERAL_AUDIO"]["STT_ENABLED"] = True
        
        # Broadcast state immediately after successful start
        await self.broadcast_state()

    def pause(self, update_global: bool = True):
        """
        Pauses STT listening by calling the underlying provider and clearing the
        internal event. Also cancels the listener task.
        """
        print("STTManager: Pausing STT")
        try:
            self.stt_instance.pause_listening()
        except Exception as e:
            print(f"STTManager: Error pausing stt_instance: {e}")

        if update_global:
            self.config["GENERAL_AUDIO"]["STT_ENABLED"] = False
        
        # Clear the event to stop the listener task cleanly
        self._listening_event.clear()

    async def broadcast_state(self):
        """
        Broadcasts the current STT state to all connected websockets.
        """
        message = {
            "type": "stt_state",
            "is_listening": self.stt_instance.is_listening,
            "is_enabled": self.config["GENERAL_AUDIO"]["STT_ENABLED"]
        }
        print(f"Broadcasting STT state: {message}")
        async with self.websocket_clients_lock:
            ws_list = list(self.websocket_clients)
        tasks = [self._send_json(ws, message) for ws in ws_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for ws, result in zip(ws_list, results):
            if isinstance(result, Exception):
                print(f"STTManager: Error broadcasting state: {result}")
                async with self.websocket_clients_lock:
                    self.websocket_clients.discard(ws)

    async def cleanup(self, websocket: WebSocket):
        """
        Cleans up resources associated with a disconnected websocket and
        updates the global state.
        """
        print("STTManager: Cleaning up for a websocket")
        is_empty = False
        async with self.websocket_clients_lock:
            self.websocket_clients.discard(websocket)
            is_empty = not self.websocket_clients
        if is_empty:  # If this was the last client
            self.pause(update_global=True)
        await self.broadcast_state()
        try:
            await websocket.send_json({"is_listening": False})
        except Exception as e:
            print(f"STTManager: Error sending cleanup state: {e}")

    async def stop(self):
        """
        Stops the STT manager by clearing the listening event and cancelling
        the listener task.
        """
        print("STTManager: Stopping STT")
        self._listening_event.clear()
        
        # Cancel queue monitor task
        if self._queue_monitor_task and not self._queue_monitor_task.done():
            self._queue_monitor_task.cancel()
            try:
                await self._queue_monitor_task
            except asyncio.CancelledError:
                print("STTManager: Queue monitor task cancelled successfully")
                
        # Cancel speech listener task
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                print("STTManager: Listen task cancelled successfully")

# ------------------------------------------------------------------------------
# FastAPI App Setup
# ------------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_stt_manager()  # Create STT manager instance
    start_wake_word_thread()
    await setup_audio_player()  # This now sets the main loop
    yield
    # Ensure STT tasks are stopped before shutdown
    await stt_manager.stop()
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
    async with stt_manager.websocket_clients_lock:
        stt_manager.websocket_clients.add(websocket)

    # Send initial STT state
    await stt_manager.broadcast_state()

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
                # Only handle playback complete for frontend playback
                if CONFIG["GENERAL_AUDIO"]["TTS_PLAYBACK_LOCATION"] == "frontend":
                    print("Server: Received frontend playback-complete message, resuming STT...")
                    await handle_playback_complete()
                else:
                    print("Server: Ignoring playback-complete message (backend playback mode)")

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
