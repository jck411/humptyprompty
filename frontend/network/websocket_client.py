"""
WebSocket client for the frontend application.
"""
import json
import asyncio
import aiohttp
import websockets
from PyQt6.QtCore import QObject, pyqtSignal
from frontend.config.config import SERVER_CONFIG
from frontend.utils.logger import get_logger

logger = get_logger(__name__)

class AsyncWebSocketClient(QObject):
    """
    Asynchronous WebSocket client for communication with the backend server.
    """
    # Signals for communication with the UI
    message_received = pyqtSignal(str)
    stt_text_received = pyqtSignal(str)
    stt_state_received = pyqtSignal(bool)
    connection_status = pyqtSignal(bool)
    audio_received = pyqtSignal(bytes)
    tts_state_changed = pyqtSignal(bool)

    def __init__(self):
        """Initialize the WebSocket client."""
        super().__init__()
        self.ws = None
        self.running = True
        self.messages = []

    async def connect(self):
        """
        Connect to the WebSocket server.
        """
        ws_url = f"ws://{SERVER_CONFIG['host']}:{SERVER_CONFIG['port']}{SERVER_CONFIG['websocket_path']}"
        try:
            self.ws = await websockets.connect(ws_url)
            self.connection_status.emit(True)
            logger.info(f"Connected to {ws_url}")

            while self.running:
                try:
                    message = await self.ws.recv()
                    await self._process_message(message)
                except Exception as e:
                    logger.error(f"WebSocket message processing error: {e}")
                    await asyncio.sleep(0.1)
                    continue
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
        finally:
            self.connection_status.emit(False)

    async def _process_message(self, message):
        """
        Process a message received from the WebSocket.
        
        Args:
            message: The received message.
        """
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

    async def send_message(self, message):
        """
        Send a message to the WebSocket server.
        
        Args:
            message: The message to send.
        """
        if self.ws:
            self.messages.append({"sender": "user", "text": message})
            await self.ws.send(json.dumps({
                "action": "chat",
                "messages": self.messages
            }))

    def handle_assistant_message(self, message):
        """
        Handle a message from the assistant.
        
        Args:
            message: The assistant's message.
        """
        self.messages.append({"sender": "assistant", "text": message})

    async def toggle_tts_async(self):
        """
        Toggle the text-to-speech functionality.
        
        Returns:
            The new TTS state.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{SERVER_CONFIG['http_base_url']()}/api/toggle-tts") as resp:
                    data = await resp.json()
                    tts_enabled = data.get("tts_enabled", False)
                    
                if not tts_enabled:
                    async with session.post(f"{SERVER_CONFIG['http_base_url']()}/api/stop-tts") as stop_resp:
                        await stop_resp.json()
                
                return tts_enabled
        except Exception as e:
            logger.error(f"Error toggling TTS: {e}")
            return None

    async def stop_tts_and_generation_async(self):
        """
        Stop TTS and text generation.
        """
        logger.info("Stop button pressed - stopping TTS and generation")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{SERVER_CONFIG['http_base_url']()}/api/stop-tts") as resp1:
                    resp1_data = await resp1.json()
                    logger.info(f"Stop TTS response: {resp1_data}")
                async with session.post(f"{SERVER_CONFIG['http_base_url']()}/api/stop-generation") as resp2:
                    resp2_data = await resp2.json()
                    logger.info(f"Stop generation response: {resp2_data}")
        except Exception as e:
            logger.error(f"Error stopping TTS and generation on server: {e}")

    async def get_initial_tts_state(self):
        """
        Get the initial TTS state from the server.
        
        Returns:
            The initial TTS state.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{SERVER_CONFIG['http_base_url']()}/api/toggle-tts") as resp:
                    data = await resp.json()
                    return data.get("tts_enabled", False)
        except Exception as e:
            logger.error(f"Error getting initial TTS state: {e}")
            return False
