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

# Global WebSocket connections set
connected_websockets: Set[WebSocket] = set()

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

class STTWebSocketHandler:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.stt_task: Optional[asyncio.Task] = None

    async def handle_stt_control(self, action: str, update_global: bool = True) -> None:
        """
        Centralizes all STT control logic.
        
        When update_global is True (as with user toggle actions), the global STT flag is updated.
        When update_global is False (as with temporary pauses during TTS playback), the global flag remains unchanged.
        """
        print(f"\nSTT WebSocket Handler: Control action '{action}' requested (update_global={update_global})")
        
        try:
            if action == "start-stt":
                if update_global:
                    CONFIG["GENERAL_AUDIO"]["STT_ENABLED"] = True
                await stt_instance.start_listening()
            elif action == "pause-stt":
                stt_instance.pause_listening()
                if update_global:
                    CONFIG["GENERAL_AUDIO"]["STT_ENABLED"] = False
            
            # Always broadcast state after control actions
            await self._broadcast_state()
            print(f"STT WebSocket Handler: Control action '{action}' completed")
        except Exception as e:
            print(f"STT WebSocket Handler: Error during control action: {e}")
    
    async def start_stt_stream(self) -> None:
        """
        Initializes STT streaming if Azure provider is configured and STT is globally enabled.
        """
        if (CONFIG["STT_MODELS"]["PROVIDER"] == "azure" and 
            CONFIG["GENERAL_AUDIO"]["STT_ENABLED"]):
            self.stt_task = asyncio.create_task(self._stream_stt())
    
    async def _stream_stt(self) -> None:
        """Handles STT streaming to client"""
        print("\nSTT WebSocket Handler: Starting STT stream...")
        try:
            while True:
                if not CONFIG["GENERAL_AUDIO"]["STT_ENABLED"]:
                    print("STT WebSocket Handler: STT disabled, waiting...")
                    await asyncio.sleep(0.5)  # Check less frequently when disabled
                    continue

                if not stt_instance.is_listening:
                    await asyncio.sleep(0.1)  # Brief pause when not listening
                    continue

                try:
                    recognized_text = stt_instance.get_speech_nowait()
                    if recognized_text:
                        # Remove "(interim)" prefix if present for cleaner UI
                        if recognized_text.startswith("(interim) "):
                            recognized_text = recognized_text[10:]
                            
                        message = {
                            "type": "stt",
                            "stt_text": recognized_text
                        }
                        print(f"STT WebSocket Handler: Sending text to client: {message}")
                        try:
                            await self.websocket.send_json(message)
                        except Exception as e:
                            print(f"STT WebSocket Handler: Error sending text: {e}")
                            if "Connection is closed" in str(e):
                                break
                except Exception as e:
                    print(f"STT WebSocket Handler: Error getting speech: {e}")
                    await asyncio.sleep(0.1)
                    continue

                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            print("STT WebSocket Handler: Stream task cancelled")
            raise
        except Exception as e:
            print(f"STT WebSocket Handler: Unexpected error in stream: {e}")
            raise
    
    async def _broadcast_state(self) -> None:
        """Broadcasts STT state to all connected clients"""
        message = {
            "type": "stt_state",
            "is_listening": stt_instance.is_listening,
            "is_enabled": CONFIG["GENERAL_AUDIO"]["STT_ENABLED"]
        }
        failed_ws = set()
        for websocket in connected_websockets:
            try:
                await websocket.send_json(message)
            except Exception:
                failed_ws.add(websocket)
        connected_websockets.difference_update(failed_ws)
    
    async def cleanup(self) -> None:
        """Handles cleanup of STT resources on WebSocket disconnect"""
        print("\nSTT WebSocket Handler: Starting cleanup...")
        if self.stt_task:
            print("STT WebSocket Handler: Cancelling STT stream task")
            self.stt_task.cancel()
            try:
                await self.stt_task
            except asyncio.CancelledError:
                pass
            
        print("STT WebSocket Handler: Pausing STT")
        stt_instance.pause_listening()
        await self._broadcast_state()
        try:
            await self.websocket.send_json({"is_listening": False})
        except Exception as e:
            print(f"STT WebSocket Handler: Error during cleanup: {e}")

@app.websocket("/ws/chat")
async def unified_chat_websocket(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.add(websocket)
    
    handler = STTWebSocketHandler(websocket)
    await handler.start_stt_stream()

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action in ["start-stt", "pause-stt"]:
                # User toggle: update the global state.
                await handler.handle_stt_control(action)
            elif action == "playback-complete":
                # Only resume STT listening if STT is globally enabled.
                if not CONFIG["GENERAL_AUDIO"]["STT_ENABLED"]:
                    print("Server: Global STT is disabled; not resuming listening after playback complete.")
                else:
                    if CONFIG["GENERAL_AUDIO"].get("TTS_ENABLED", False):
                        if CONFIG["GENERAL_AUDIO"]["TTS_PLAYBACK_LOCATION"] == "frontend":
                            print("Server: Received frontend playback-complete message, resuming STT...")
                            await handler.handle_stt_control("start-stt", update_global=False)
                        else:
                            print("Server: Ignoring playback-complete message (backend playback mode)")
                    else:
                        if not stt_instance.is_listening:
                            print("Server: TTS is off but STT is not listening; resuming STT listening...")
                            await handler.handle_stt_control("start-stt", update_global=False)
                        else:
                            print("Server: TTS is off and STT is already listening.")
            elif action == "chat":
                print("\nProcessing new chat message...")
                print(f"TTS Enabled: {CONFIG['GENERAL_AUDIO']['TTS_ENABLED']}")
                print(f"TTS Location: {CONFIG['GENERAL_AUDIO']['TTS_PLAYBACK_LOCATION']}")
                
                # Clear events to start fresh for the new chat.
                TTS_STOP_EVENT.clear()
                GEN_STOP_EVENT.clear()

                messages = data.get("messages", [])
                validated = await validate_messages_for_ws(messages)

                phrase_queue = asyncio.Queue()
                audio_queue = asyncio.Queue()

                # For a chat, if TTS is enabled, temporarily pause STT without changing the global flag.
                if CONFIG["GENERAL_AUDIO"].get("TTS_ENABLED", False):
                    await handler.handle_stt_control("pause-stt", update_global=False)
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
    except Exception:
        pass
    finally:
        await handler.cleanup()
        connected_websockets.discard(websocket)
        await websocket.close()

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
                    # Send an empty audio marker to signal end of stream
                    print("Received None in audio queue, sending audio end marker")
                    await websocket.send_bytes(b'audio:')
                    break
                # Ensure proper message format with audio: prefix
                message = b'audio:' + audio_data if not audio_data.startswith(b'audio:') else audio_data
                await websocket.send_bytes(message)
            except Exception as e:
                print(f"Error forwarding audio to websocket: {e}")
                break
    except Exception as e:
        print(f"Forward audio task error: {e}")
    finally:
        # Ensure we always send the end marker
        try:
            await websocket.send_bytes(b'audio:')
        except Exception as e:
            print(f"Error sending final empty message: {e}")

app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
