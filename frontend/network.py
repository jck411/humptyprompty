#!/usr/bin/env python3
import json
import asyncio
import aiohttp
import websockets
from PyQt6.QtCore import QObject, pyqtSignal
from frontend.config import SERVER_HOST, SERVER_PORT, WEBSOCKET_PATH, logger

class AsyncWebSocketClient(QObject):
    message_received = pyqtSignal(str)
    stt_text_received = pyqtSignal(str)
    stt_state_received = pyqtSignal(bool)
    connection_status = pyqtSignal(bool)
    audio_received = pyqtSignal(bytes)
    tts_state_changed = pyqtSignal(bool)

    def __init__(self, server_host=SERVER_HOST, server_port=SERVER_PORT, websocket_path=WEBSOCKET_PATH):
        super().__init__()
        self.server_host = server_host
        self.server_port = server_port
        self.websocket_path = websocket_path
        self.ws = None
        self.running = True
        self.messages = []

    async def connect(self):
        ws_url = f"ws://{self.server_host}:{self.server_port}{self.websocket_path}"
        try:
            self.ws = await websockets.connect(ws_url)
            self.connection_status.emit(True)
            logger.info(f"Connected to {ws_url}")

            while self.running:
                try:
                    message = await self.ws.recv()
                    if isinstance(message, bytes):
                        if message.startswith(b'audio:'):
                            audio_data = message[len(b'audio:'):]
                            logger.debug(f"Received audio chunk of size: {len(audio_data)} bytes")
                            self.audio_received.emit(message)
                        else:
                            logger.warning("Received binary message without audio prefix")
                            self.audio_received.emit(b'audio:' + message)
                    else:
                        try:
                            data = json.loads(message)
                            logger.debug(f"Received message: {data}")
                            msg_type = data.get("type")
                            if msg_type == "stt":
                                stt_text = data.get("stt_text", "")
                                logger.debug(f"Processing STT text immediately: {stt_text}")
                                self.stt_text_received.emit(stt_text)
                            elif msg_type == "stt_state":
                                is_listening = data.get("is_listening", False)
                                logger.debug(f"Updating STT state: listening = {is_listening}")
                                self.stt_state_received.emit(is_listening)
                            elif "content" in data:
                                self.message_received.emit(data["content"])
                            else:
                                logger.warning(f"Unknown message type: {data}")
                        except json.JSONDecodeError:
                            logger.error("Failed to parse JSON message")
                            logger.error(f"Raw message: {message}")
                except Exception as e:
                    logger.error(f"WebSocket message processing error: {e}")
                    await asyncio.sleep(0.1)
                    continue
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
        finally:
            self.connection_status.emit(False)

    async def send_message(self, message):
        if self.ws:
            self.messages.append({"sender": "user", "text": message})
            await self.ws.send(json.dumps({
                "action": "chat",
                "messages": self.messages
            }))

    def handle_assistant_message(self, message):
        self.messages.append({"sender": "assistant", "text": message})
