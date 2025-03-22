# client_ws.py
import asyncio
import json
import logging
from PySide6.QtCore import QObject, Signal
import websockets
import sys

# Import the get_event_loop helper if it exists in main
try:
    # Try to import from main first
    from main import get_event_loop
    HAS_GLOBAL_LOOP = True
except ImportError:
    try:
        # If that fails, try to import from the current asyncio module
        from asyncio import get_event_loop
        HAS_GLOBAL_LOOP = True
    except ImportError:
        HAS_GLOBAL_LOOP = False
        logging.warning("Could not import get_event_loop from any source, falling back to default")

class AsyncWebSocketClient(QObject):
    message_received = Signal(str)
    connection_status = Signal(bool)
    audio_received = Signal(bytes)
    tts_state_changed = Signal(bool)
    stt_text_received = Signal(str)
    stt_state_received = Signal(bool)

    def __init__(self, host, port, path):
        super().__init__()
        self.server_url = f"ws://{host}:{port}{path}"
        self.ws = None
        self.running = True
        self.messages = []
        self.reconnect_delay = 1  # Start with 1 second delay
        self.max_reconnect_delay = 30  # Maximum delay in seconds
        self.connected = False
        self._connect_task = None

    def _get_loop(self):
        """Get the current event loop with fallbacks"""
        if not self.running:
            return None
            
        try:
            # Try to get the global loop from main
            if HAS_GLOBAL_LOOP:
                loop = get_event_loop()
                if loop and loop.is_running():
                    return loop
            
            # Fall back to current event loop
            try:
                return asyncio.get_event_loop()
            except RuntimeError:
                return None
        except Exception as e:
            logging.error(f"Error getting event loop: {e}")
            return None

    async def connect_ws(self):
        """Connect to the WebSocket server and start the message processing loop"""
        if not self.running:
            return
            
        try:
            logging.info(f"Attempting to connect to {self.server_url}")
            self.ws = await websockets.connect(self.server_url)
            self.connected = True
            self.connection_status.emit(True)
            # Reset reconnect delay on successful connection
            self.reconnect_delay = 1
            logging.info(f"Connected to {self.server_url}")
            
            # Process messages until connection is lost or running=False
            await self._process_messages()
        except Exception as e:
            logging.error(f"WebSocket connection error: {e}")
        finally:
            # Ensure we mark as disconnected when exiting
            self.connected = False
            self.connection_status.emit(False)
            logging.info("WebSocket connection closed")
            
            # Try to reconnect if we're still running
            if self.running:
                loop = self._get_loop()
                if loop:
                    try:
                        # Schedule reconnection after a delay with exponential backoff
                        logging.info(f"Scheduling reconnection in {self.reconnect_delay} seconds")
                        
                        # Try to get the running loop, but handle the case when there's no running loop
                        try:
                            current_loop = asyncio.get_running_loop()
                            current_loop.call_later(
                                self.reconnect_delay, 
                                lambda: asyncio.create_task(self.connect_ws())
                            )
                        except RuntimeError:
                            # No running event loop, use the loop we got from _get_loop
                            logging.warning("No running event loop, using fallback method for reconnection")
                            loop.call_later(
                                self.reconnect_delay,
                                lambda: self.start_connection()
                            )
                        
                        # Implement exponential backoff for reconnection
                        self.reconnect_delay = min(self.reconnect_delay * 1.5, self.max_reconnect_delay)
                    except Exception as e:
                        logging.error(f"Error scheduling reconnection: {e}")
    
    def start_connection(self):
        """Start the WebSocket connection in the background"""
        if not self.running:
            return
            
        loop = self._get_loop()
        if loop:
            try:
                # Only create a new task if we don't have one or the previous one is done
                if not self._connect_task or self._connect_task.done():
                    self._connect_task = asyncio.create_task(self.connect_ws())
                    logging.info("WebSocket connection task created")
            except Exception as e:
                logging.error(f"Failed to create connection task: {e}")
        else:
            logging.error("Could not get event loop to start WebSocket connection")
            
    async def _process_messages(self):
        """Process incoming messages from the WebSocket"""
        while self.running and self.ws:
            try:
                # Try to receive messages with a timeout
                # This ensures we can check running status regularly
                try:
                    message = await asyncio.wait_for(self.ws.recv(), timeout=0.5)
                except asyncio.TimeoutError:
                    # Check if we should still be running
                    if not self.running:
                        break
                    continue
                
                # Process the received message
                if isinstance(message, bytes):
                    if message.startswith(b'audio:'):
                        audio_data = message[len(b'audio:'):]
                        logging.debug(f"Received audio chunk of size: {len(audio_data)} bytes")
                        self.audio_received.emit(message)
                    else:
                        logging.debug("Received binary message without audio prefix")
                        self.audio_received.emit(b'audio:' + message)
                else:
                    try:
                        data = json.loads(message)
                        logging.debug(f"Received message: {data}")
                        
                        msg_type = data.get("type")
                        if msg_type == "stt":
                            stt_text = data.get("stt_text", "")
                            logging.debug(f"Processing STT text: {stt_text}")
                            self.stt_text_received.emit(stt_text)
                        elif msg_type == "stt_state":
                            is_listening = data.get("is_listening", False)
                            logging.debug(f"Updating STT state: listening = {is_listening}")
                            self.stt_state_received.emit(is_listening)
                        elif "content" in data:
                            logging.info(f"Received content: {data['content'][:50]}...")
                            self.message_received.emit(data["content"])
                        elif msg_type == "tts_state":
                            self.tts_state_changed.emit(data.get("enabled", False))
                        else:
                            logging.warning(f"Unknown message type: {data}")
                    except json.JSONDecodeError:
                        logging.error("Failed to parse JSON message")
                        logging.error(f"Raw message: {message}")
            except websockets.exceptions.ConnectionClosed:
                logging.info("WebSocket connection closed")
                break
            except Exception as e:
                if not self.running:
                    break
                logging.error(f"WebSocket recv error: {e}")
                await asyncio.sleep(0.1)

    async def send_message(self, user_text):
        """Send a message through the websocket if it's connected"""
        if not self.running:
            return False
            
        if not self.ws:
            logging.warning("WebSocket not connected, attempting to reconnect")
            self.start_connection()
            return False
            
        try:
            # Try sending - this will fail if connection is closed
            self.messages.append({"sender": "user", "text": user_text})
            message = {
                "action": "chat",
                "messages": self.messages
            }
            logging.info(f"Sending message: {user_text[:50]}...")
            await self.ws.send(json.dumps(message))
            return True
        except websockets.exceptions.ConnectionClosed:
            logging.error("Connection closed while trying to send message")
            self.connected = False
            self.connection_status.emit(False)
            return False
        except Exception as e:
            logging.error(f"Error sending message: {e}")
            return False

    def handle_assistant_message(self, full_text: str):
        if self.running:
            self.messages.append({"sender": "assistant", "text": full_text})
