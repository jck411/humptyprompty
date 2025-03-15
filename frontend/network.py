#!/usr/bin/env python3
import json
import asyncio
import aiohttp
import websockets
from PyQt6.QtCore import QObject, pyqtSignal
from frontend.config import SERVER_HOST, SERVER_PORT, WEBSOCKET_PATH, HTTP_BASE_URL, logger
from frontend.stt.config import STT_CONFIG
import concurrent.futures

class AsyncWebSocketClient(QObject):
    message_received = pyqtSignal(str)
    stt_text_received = pyqtSignal(str)
    stt_state_received = pyqtSignal(bool)
    connection_status = pyqtSignal(bool)
    audio_received = pyqtSignal(bytes)
    tts_state_changed = pyqtSignal(bool)
    generation_stopped = pyqtSignal()
    audio_stopped = pyqtSignal()

    def __init__(self, server_host=SERVER_HOST, server_port=SERVER_PORT, websocket_path=WEBSOCKET_PATH):
        super().__init__()
        self.server_host = server_host
        self.server_port = server_port
        self.websocket_path = websocket_path
        self.ws = None
        self.running = True
        self.messages = []
        self.http_base_url = HTTP_BASE_URL

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
                            elif msg_type == "tts_state":
                                is_enabled = data.get("tts_enabled", False)
                                logger.debug(f"Updating TTS state: enabled = {is_enabled}")
                                self.tts_state_changed.emit(is_enabled)
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
    
    async def toggle_tts(self):
        """Toggle text-to-speech on the server"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.http_base_url}/api/toggle-tts") as resp:
                    data = await resp.json()
                    tts_enabled = data.get("tts_enabled", False)
                    logger.info(f"TTS toggled, new state: {tts_enabled}")
                    self.tts_state_changed.emit(tts_enabled)
                    return tts_enabled
        except Exception as e:
            logger.error(f"Error toggling TTS: {e}")
            return None
    
    async def get_initial_tts_state(self):
        """Get the initial TTS state from the server"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.http_base_url}/api/config") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("tts_enabled", False)
                    else:
                        logger.error(f"Failed to get initial TTS state: {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"Error getting initial TTS state: {e}")
            return False
    
    async def get_all_initial_states(self):
        """Get all initial states from the server in a single request"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.http_base_url}/api/config") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"Got all initial states: {data}")
                        return data
                    else:
                        logger.error(f"Failed to get all initial states: {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting all initial states: {e}")
            return None
    
    async def stop_tts_and_generation(self):
        """Stop TTS and text generation on the server"""
        logger.info("Stopping TTS and generation")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.http_base_url}/api/stop-audio") as resp1:
                    resp1_data = await resp1.json()
                    logger.info(f"Stop TTS response: {resp1_data}")
                    self.audio_stopped.emit()
                
                async with session.post(f"{self.http_base_url}/api/stop-generation") as resp2:
                    resp2_data = await resp2.json()
                    logger.info(f"Stop generation response: {resp2_data}")
                    self.generation_stopped.emit()
                
                # After stopping generation, tell the server to use a fresh context next time
                # This prevents the stopped response from continuing on the next message
                if self.ws:
                    try:
                        await self.ws.send(json.dumps({"action": "reset-context"}))
                        logger.info("Sent reset-context request to server")
                    except Exception as e:
                        logger.error(f"Error sending reset-context: {e}")
                
                return True
        except Exception as e:
            logger.error(f"Error stopping TTS and generation on server: {e}")
            return False
    
    async def send_playback_complete(self):
        """Send playback-complete notification to the server"""
        if self.ws:
            try:
                await self.ws.send(json.dumps({"action": "playback-complete"}))
                logger.info("Sent playback-complete to server")
                return True
            except Exception as e:
                logger.error(f"Error sending playback-complete: {e}")
                return False
        return False
    
    def clear_messages(self):
        """Clear the message history"""
        self.messages.clear()
        logger.info("Message history cleared")
        
    async def _close_websocket(self):
        """Close the WebSocket connection"""
        if self.ws:
            try:
                await self.ws.close()
                logger.info("WebSocket connection closed")
            except Exception as e:
                logger.error(f"Error closing WebSocket connection: {e}")
            finally:
                self.ws = None
    
    def cleanup(self):
        """Clean up resources and close connections"""
        logger.info("Cleaning up AsyncWebSocketClient")
        self.running = False
        
        try:
            # Get the current event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're in a running event loop, use run_coroutine_threadsafe
                    future = asyncio.run_coroutine_threadsafe(self._close_websocket(), loop)
                    # Wait for a short time for the coroutine to complete
                    try:
                        future.result(timeout=1.0)
                    except (asyncio.TimeoutError, concurrent.futures.TimeoutError):
                        logger.warning("WebSocket cleanup timed out, but continuing shutdown")
                else:
                    # If loop exists but isn't running, use it
                    loop.run_until_complete(self._close_websocket())
            except RuntimeError:
                # If no event loop exists in this thread, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._close_websocket())
                loop.close()
        except Exception as e:
            logger.error(f"Error during WebSocketClient cleanup: {e}")
        
        logger.info("AsyncWebSocketClient cleanup complete")
