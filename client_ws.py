import logging
from PySide6.QtCore import QObject, Signal
import asyncio
import websockets
import json

# Add logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__) 

class AsyncWebSocketClient(QObject):
    message_received = Signal(str)
    connection_status = Signal(bool)
    audio_received = Signal(bytes)
    tts_state_changed = Signal(bool)
    stt_state_received = Signal(bool)  # Add this signal for STT state changes 

    async def connect(self):
        while self.running:  # Add reconnection loop
            try:
                self.ws = await websockets.connect(self.server_url)
                self.connection_status.emit(True)
                logger.info(f"Connected to {self.server_url}")

                while self.running:
                    try:
                        message = await self.ws.recv()
                        if isinstance(message, bytes):
                            if message.startswith(b'audio:'):
                                logger.debug(f"Received audio chunk of size: {len(message[6:])} bytes")
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
                                    logger.debug(f"Processing STT text: {stt_text}")
                                elif msg_type == "stt_state":
                                    is_listening = data.get("is_listening", False)
                                    logger.debug(f"Updating STT state: listening = {is_listening}")
                                    self.stt_state_received.emit(is_listening)
                                elif "content" in data:
                                    self.message_received.emit(data["content"])
                                elif msg_type == "tts_state":
                                    enabled = data.get("enabled", False)
                                    logger.debug(f"TTS state changed: {enabled}")
                                    self.tts_state_changed.emit(enabled)
                                else:
                                    logger.warning(f"Unknown message type: {data}")
                            except json.JSONDecodeError:
                                logger.error("Failed to parse JSON message")
                                logger.error(f"Raw message: {message}")
                    except websockets.exceptions.ConnectionClosed:
                        logger.error("WebSocket connection closed")
                        break
                    except Exception as e:
                        logger.error(f"WebSocket message processing error: {e}")
                        await asyncio.sleep(0.1)
                        continue
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
                await asyncio.sleep(5)  # Wait before reconnecting
            finally:
                self.connection_status.emit(False)
                if self.ws:
                    await self.ws.close() 

    async def send_message(self, user_text):
        """Send a user message to the server (includes conversation history)."""
        if not self.ws:
            logger.error("Cannot send message - WebSocket not connected")
            return
        
        try:
            self.messages.append({"sender": "user", "text": user_text})
            await self.ws.send(json.dumps({
                "action": "chat",
                "messages": self.messages
            }))
            logger.debug(f"Sent message: {user_text}")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.messages.pop()  # Remove failed message from history 