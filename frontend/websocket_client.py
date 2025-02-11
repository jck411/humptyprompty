import json
import logging
import asyncio
import aiohttp
import websockets
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

class WebSocketClient(QThread):
    message_received = pyqtSignal(str)
    stt_text_received = pyqtSignal(str)
    connection_status = pyqtSignal(bool)
    audio_received = pyqtSignal(bytes)  # PCM audio data
    tts_state_changed = pyqtSignal(bool)  # Signal for TTS state changes

    def __init__(self, server_host, server_port, websocket_path, http_base_url):
        super().__init__()
        self.server_host = server_host
        self.server_port = server_port
        self.websocket_path = websocket_path
        self.http_base_url = http_base_url
        self.ws = None
        self.running = True
        self.messages = []

    async def connect(self):
        ws_url = f"ws://{self.server_host}:{self.server_port}{self.websocket_path}"
        try:
            self.ws = await websockets.connect(ws_url)
            self.connection_status.emit(True)
            logger.info(f"Frontend: WebSocket connected to {ws_url}")

            # Get initial TTS state when WebSocket connects
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{self.http_base_url}/api/toggle-tts") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            self.tts_state_changed.emit(data.get("tts_enabled", False))
            except Exception as e:
                logger.error(f"Error getting initial TTS state: {e}")

            while self.running:
                try:
                    message = await self.ws.recv()
                    if isinstance(message, bytes):
                        # Remove the 'audio:' prefix if present
                        prefix = b'audio:'
                        if message.startswith(prefix):
                            audio_data = message[len(prefix):]
                        else:
                            audio_data = message
                        logger.info(f"Frontend: Received binary message of size: {len(audio_data)} bytes")
                        self.audio_received.emit(audio_data)
                    else:
                        logger.info(f"Frontend: Received text message: {message[:100]}...")
                        try:
                            data = json.loads(message)
                            if "content" in data:
                                self.message_received.emit(data["content"])
                            elif "stt_text" in data:
                                self.stt_text_received.emit(data["stt_text"])
                        except json.JSONDecodeError:
                            logger.error(f"Frontend: Failed to parse JSON message: {message}")
                except websockets.exceptions.ConnectionClosed:
                    logger.info("Frontend: WebSocket connection closed")
                    break
                except Exception as e:
                    logger.error(f"Frontend: Error processing WebSocket message: {e}")
                    break
        except Exception as e:
            logger.error(f"Frontend: WebSocket connection error: {e}")
        finally:
            self.connection_status.emit(False)

    async def send_message(self, message):
        if self.ws:
            self.messages.append({
                "sender": "user",
                "text": message
            })
            await self.ws.send(json.dumps({
                "action": "chat",
                "messages": self.messages
            }))

    async def send_playback_complete(self):
        """Sends a notification to the backend indicating that TTS playback has finished."""
        if self.ws:
            await self.ws.send(json.dumps({"action": "playback-complete"}))

    def handle_assistant_message(self, message):
        self.messages.append({
            "sender": "assistant",
            "text": message
        })

    def run(self):
        asyncio.run(self.connect())