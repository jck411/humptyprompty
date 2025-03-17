#!/usr/bin/env python3
import json
import asyncio
import aiohttp
import websockets
from PyQt6.QtCore import QObject, pyqtSignal
from frontend.config import SERVER_HOST, SERVER_PORT, WEBSOCKET_PATH, HTTP_BASE_URL, logger
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
        
        # Task registry to track pending tasks
        self._pending_tasks = set()

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
        
    def _register_task(self, task):
        """Add a task to the pending tasks set and set up its cleanup callback."""
        self._pending_tasks.add(task)
        task.add_done_callback(self._remove_task)
        return task
    
    def _remove_task(self, task):
        """Remove a completed task from the pending tasks set."""
        self._pending_tasks.discard(task)
    
    def _cancel_all_pending_tasks(self):
        """Cancel all pending tasks."""
        cancelled_count = 0
        for task in list(self._pending_tasks):  # Create a copy of the set before iterating
            if not task.done():
                logger.debug(f"Cancelling task: {task}")
                task.cancel()
                cancelled_count += 1
        
        if cancelled_count > 0:
            logger.info(f"Cancelled {cancelled_count} pending tasks")
        
    async def _close_websocket(self):
        """Safely close the WebSocket connection"""
        websocket = self.ws
        if websocket:
            try:
                await websocket.close()
                logger.info("WebSocket connection closed properly")
            except Exception as e:
                logger.error(f"Error closing WebSocket connection: {e}")
    
    def cleanup(self):
        """Clean up resources and close connections"""
        logger.info("Cleaning up AsyncWebSocketClient")
        
        # Mark as not running to prevent new operations
        self.running = False
        
        # Store current websocket reference and clear it immediately to prevent new operations
        websocket = self.ws
        self.ws = None
        
        # Only proceed with cleanup if there was an active websocket
        if websocket:
            logger.info("Closing WebSocket connection")
            try:
                # Get the current event loop or create a new one
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If in a running event loop, create a task and register it for tracking
                        close_task = self._register_task(asyncio.create_task(self._close_websocket()))
                        
                        # Add a callback to log completion
                        close_task.add_done_callback(
                            lambda t: logger.debug(f"WebSocket close task completed: {t.cancelled()=}, {t.exception() if not t.cancelled() and t.done() else None}")
                        )
                        
                        # Create a Future that will be completed when the close task is done
                        future = asyncio.run_coroutine_threadsafe(self._wait_for_task_completion(close_task), loop)
                        
                        # Wait with a timeout to ensure we don't block indefinitely
                        try:
                            # Use 3 seconds timeout to give more time for graceful shutdown
                            future.result(timeout=3.0)
                        except (asyncio.TimeoutError, concurrent.futures.TimeoutError):
                            logger.warning("WebSocket close operation timed out, but continuing shutdown")
                        except Exception as e:
                            logger.error(f"Error waiting for WebSocket close task: {e}")
                    else:
                        # If loop exists but isn't running, use it to run the coroutine to completion
                        loop.run_until_complete(self._close_websocket())
                except RuntimeError:
                    # If no event loop exists, create a temporary one
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self._close_websocket())
                    loop.close()
            except Exception as e:
                logger.error(f"Error during WebSocket cleanup: {e}")
        
        # Wait a brief moment to allow any in-progress operations to complete
        try:
            if asyncio.get_event_loop().is_running():
                # Create a wait task and wait for it with timeout
                sleep_task = self._register_task(asyncio.create_task(asyncio.sleep(0.5)))
                try:
                    # Run in current event loop if it's running
                    loop = asyncio.get_event_loop()
                    future = asyncio.run_coroutine_threadsafe(self._wait_for_task_completion(sleep_task), loop)
                    future.result(timeout=0.6)  # Slightly longer than the sleep
                except Exception:
                    # If we can't wait properly, it's acceptable to continue
                    pass
        except Exception:
            # Ignore any errors in this sleep phase - it's just a best effort
            pass
            
        # Cancel any remaining pending tasks
        self._cancel_all_pending_tasks()
        logger.info("AsyncWebSocketClient cleanup complete")
        
    async def _wait_for_task_completion(self, task):
        """Wait for a task to complete and handle any exceptions."""
        try:
            await task
        except asyncio.CancelledError:
            logger.debug("Task was cancelled")
        except Exception as e:
            logger.error(f"Task failed with exception: {e}")
