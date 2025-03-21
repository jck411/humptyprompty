# client_ws.py
import asyncio
import json
import logging
from PySide6.QtCore import QObject, Signal
import websockets

class AsyncWebSocketClient(QObject):
    message_received = Signal(str)
    connection_status = Signal(bool)
    audio_received = Signal(bytes)
    tts_state_changed = Signal(bool)

    def __init__(self, host, port, path):
        super().__init__()
        self.server_url = f"ws://{host}:{port}{path}"
        self.ws = None
        self.running = True
        self.messages = []

    async def connect_ws(self):
        """Connect to the WebSocket server and start the message processing loop"""
        try:
            self.ws = await websockets.connect(self.server_url)
            self.connection_status.emit(True)
            logging.info(f"Connected to {self.server_url}")
            
            # Start a background task for message processing
            asyncio.create_task(self._process_messages())
            return True
        except Exception as e:
            logging.error(f"WebSocket connection error: {e}")
            self.connection_status.emit(False)
            return False
            
    async def _process_messages(self):
        """Process incoming messages from the WebSocket"""
        while self.running and self.ws:
            try:
                message = await self.ws.recv()
                if isinstance(message, bytes):
                    if message.startswith(b'audio:'):
                        self.audio_received.emit(message)
                    else:
                        self.audio_received.emit(b'audio:' + message)
                else:
                    data = json.loads(message)
                    if data.get("type") == "stt":
                        pass
                    elif data.get("type") == "stt_state":
                        pass
                    elif "content" in data:
                        self.message_received.emit(data["content"])
                    elif data.get("type") == "tts_state":
                        self.tts_state_changed.emit(data.get("enabled", False))
                    else:
                        logging.warning(f"Unknown message type: {data}")
            except Exception as e:
                logging.error(f"WebSocket recv error: {e}")
                await asyncio.sleep(0.1)
                if not self.ws.open:
                    self.connection_status.emit(False)
                    break

    async def send_message(self, user_text):
        if self.ws:
            self.messages.append({"sender": "user", "text": user_text})
            await self.ws.send(json.dumps({
                "action": "chat",
                "messages": self.messages
            }))

    def handle_assistant_message(self, full_text: str):
        self.messages.append({"sender": "assistant", "text": full_text})
