#!/usr/bin/env python3
import json
import asyncio
import aiohttp
import websockets
from PyQt6.QtCore import QObject, pyqtSignal
from frontend.config import SERVER_HOST, SERVER_PORT, WEBSOCKET_PATH, HTTP_BASE_URL, logger
from frontend.stt.config import STT_CONFIG
import concurrent.futures

async def send_with_timeout(method, url, timeout=10, **kwargs):
    """
    Send HTTP request with consistent timeout and error handling.
    
    Args:
        method: HTTP method ('get', 'post', etc.)
        url: Target URL
        timeout: Timeout in seconds (default: 10)
        **kwargs: Additional arguments to pass to the request
        
    Returns:
        Response data or None on error
        
    Example usage:
        data = await send_with_timeout('get', f"{base_url}/api/config")
        if data:
            # Process successful response
    """
    try:
        async with aiohttp.ClientSession() as session:
            request_method = getattr(session, method.lower())
            async with request_method(
                url, 
                timeout=aiohttp.ClientTimeout(total=timeout),
                **kwargs
            ) as resp:
                if resp.status == 200:
                    try:
                        return await resp.json()
                    except Exception as e:
                        logger.error(f"Error parsing JSON response from {url}: {e}")
                        return None
                else:
                    logger.error(f"HTTP error: {resp.status} for {url}")
                    return None
    except asyncio.TimeoutError:
        logger.error(f"Request to {url} timed out after {timeout}s")
        return None
    except aiohttp.ClientError as e:
        logger.error(f"Client error in HTTP request to {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in HTTP request to {url}: {e}")
        return None

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
        
        # Set up message type handlers
        self.message_handlers = {
            "stt": self._handle_stt_message,
            "stt_state": self._handle_stt_state_message,
            "tts_state": self._handle_tts_state_message,
            "context_reset": self._handle_context_reset_message,
        }

    async def connect(self):
        ws_url = f"ws://{self.server_host}:{self.server_port}{self.websocket_path}"
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
        """Process an incoming WebSocket message"""
        # Handle binary messages
        if isinstance(message, bytes):
            self._process_binary_message(message)
            return
            
        # Handle text messages
        try:
            data = json.loads(message)
            logger.debug(f"Received message: {data}")
            
            # Dispatch to appropriate handler based on message type
            msg_type = data.get("type")
            if msg_type in self.message_handlers:
                self.message_handlers[msg_type](data)
            elif "content" in data:
                self.message_received.emit(data["content"])
            else:
                logger.warning(f"Unknown message type: {data}")
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON message")
            logger.error(f"Raw message: {message}")
    
    def _process_binary_message(self, message):
        """Process binary messages (typically audio data)"""
        if message.startswith(b'audio:'):
            audio_data = message[len(b'audio:'):]
            logger.debug(f"Received audio chunk of size: {len(audio_data)} bytes")
            self.audio_received.emit(message)
        else:
            logger.warning("Received binary message without audio prefix")
            self.audio_received.emit(b'audio:' + message)
    
    def _handle_stt_message(self, data):
        """Handle speech-to-text messages"""
        stt_text = data.get("stt_text", "")
        logger.debug(f"Processing STT text immediately: {stt_text}")
        self.stt_text_received.emit(stt_text)
    
    def _handle_stt_state_message(self, data):
        """Handle speech-to-text state updates"""
        is_listening = data.get("is_listening", False)
        logger.debug(f"Updating STT state: listening = {is_listening}")
        self.stt_state_received.emit(is_listening)
    
    def _handle_tts_state_message(self, data):
        """Handle text-to-speech state updates"""
        is_enabled = data.get("tts_enabled", False)
        logger.debug(f"Updating TTS state: enabled = {is_enabled}")
        self.tts_state_changed.emit(is_enabled)
        
    def _handle_context_reset_message(self, data):
        """Handle context reset confirmation from server"""
        status = data.get("status", "")
        logger.info(f"Context reset confirmation received with status: {status}")
        # No action needed beyond logging as this is just a confirmation

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
        data = await send_with_timeout('post', f"{self.http_base_url}/api/toggle-tts")
        if data:
            tts_enabled = data.get("tts_enabled", False)
            logger.info(f"TTS toggled, new state: {tts_enabled}")
            self.tts_state_changed.emit(tts_enabled)
            return tts_enabled
        return None
    
    async def get_initial_tts_state(self):
        """Get the initial TTS state from the server"""
        data = await send_with_timeout('get', f"{self.http_base_url}/api/config")
        if data:
            return data.get("tts_enabled", False)
        return False
    
    async def get_all_initial_states(self):
        """Get all initial states from the server in a single request"""
        data = await send_with_timeout('get', f"{self.http_base_url}/api/config")
        if data:
            logger.info(f"Got all initial states: {data}")
            return data
        return None
    
    async def stop_tts_and_generation(self):
        """Stop TTS and text generation on the server"""
        logger.info("Stopping TTS and generation")
        
        # Stop audio
        resp1_data = await send_with_timeout('post', f"{self.http_base_url}/api/stop-audio")
        if resp1_data:
            logger.info(f"Stop TTS response: {resp1_data}")
            self.audio_stopped.emit()
        
        # Stop generation
        resp2_data = await send_with_timeout('post', f"{self.http_base_url}/api/stop-generation")
        if resp2_data:
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
        
        return resp1_data is not None and resp2_data is not None
    
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
