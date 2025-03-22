# chat_backend.py
import asyncio
import aiohttp
import json
import logging
from PySide6.QtCore import QObject, Signal, Slot
from stt.deepgram_stt import DeepgramSTT
from client_ws import AsyncWebSocketClient
from config import SERVER_HOST, SERVER_PORT, WEBSOCKET_PATH, HTTP_BASE_URL

class ChatBackend(QObject):
    newUserMessage = Signal(str)            # Used to update the chat area with a user message
    assistantTextUpdated = Signal(str)      # Emitted as assistant response tokens arrive
    assistantResponseComplete = Signal()    # Signaled when the assistant's reply is complete
    sttEnabledChanged = Signal(bool)        # Emitted when the STT state changes
    ttsEnabledChanged = Signal(bool)        # Emitted when the TTS state changes

    def __init__(self):
        super().__init__()
        self.stt = DeepgramSTT()
        self.ws_client = AsyncWebSocketClient(SERVER_HOST, SERVER_PORT, WEBSOCKET_PATH)
        self.tts_enabled = False
        self._assistant_text_in_progress = ""
        self._assistant_active = False
        self._ws_task = None
        self._init_completed = False

        self.stt.complete_utterance_received.connect(self.on_stt_complete)
        self.stt.state_changed.connect(self.on_stt_state_change)

        self.ws_client.message_received.connect(self.on_assistant_token)
        self.ws_client.connection_status.connect(self.on_connection_status)
        self.ws_client.tts_state_changed.connect(self.on_server_tts_update)
        self.ws_client.stt_text_received.connect(self.on_stt_text)
        self.ws_client.stt_state_received.connect(self.on_stt_state)

        logging.info("ChatBackend initialized.")
        
    async def initialize(self):
        """Initialize async components after the event loop is running"""
        logging.info("Starting ChatBackend initialization")
        
        # Start the WebSocket connection
        self.ws_client.start_connection()
        logging.info("WebSocket connection started")
        
        # Wait briefly to ensure connection is established
        for _ in range(5):  # Try up to 5 times with 1 second intervals
            if self.ws_client.connected:
                logging.info("WebSocket connection established")
                break
            logging.info("Waiting for WebSocket connection...")
            await asyncio.sleep(1.0)
        
        # Only try to initialize TTS if we're connected
        if self.ws_client.connected:
            # Initialize TTS state
            try:
                await self._init_tts_state()
            except Exception as e:
                logging.error(f"Error during TTS initialization: {e}")
        else:
            logging.warning("WebSocket not connected, scheduling delayed TTS initialization")
            # Schedule delayed initialization
            asyncio.create_task(self._delayed_tts_init())
        
        self._init_completed = True
        logging.info("ChatBackend initialization completed")

    async def _delayed_tts_init(self):
        """Retry TTS initialization after waiting for WebSocket connection with improved retry logic"""
        retry_count = 0
        max_retries = 5  # Increased from 3 to 5 for more attempts
        retry_delay = 2.0  # Start with 2 second delay
        
        while retry_count < max_retries and not self.ws_client.connected:
            logging.info(f"Waiting for WebSocket connection before TTS init (attempt {retry_count+1}/{max_retries})")
            
            # Try to restart connection if it's not already connected
            if not self.ws_client.connected:
                self.ws_client.start_connection()
                
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 1.5, 8.0)  # Exponential backoff up to 8 seconds
            retry_count += 1
            
        if self.ws_client.connected:
            logging.info("WebSocket connected, initializing TTS state")
            try:
                await self._init_tts_state()
            except Exception as e:
                logging.error(f"Error during delayed TTS initialization: {e}")
        else:
            logging.error("Failed to establish WebSocket connection for TTS initialization after multiple attempts")
            # We'll let the connection event trigger TTS init when connection is eventually established
            
            # Schedule another attempt with a longer delay as a last resort
            asyncio.get_running_loop().call_later(
                10.0,  # Try again after 10 seconds
                lambda: asyncio.create_task(self._init_tts_state()) if self.ws_client.connected else None
            )

    @Slot()
    def toggleSTT(self):
        self.stt.toggle()

    @Slot()
    def toggleTTS(self):
        # Use threading instead of asyncio.create_task to avoid event loop issues
        import threading
        def run_toggle_tts():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._toggle_tts_async())
            loop.close()
        
        toggle_thread = threading.Thread(target=run_toggle_tts)
        toggle_thread.daemon = True
        toggle_thread.start()

    @Slot(str)
    def sendMessage(self, text):
        text = text.strip()
        if not text:
            return
        if self._assistant_active:
            self.finalizeAssistantResponse()
        self.newUserMessage.emit(text)
        
        # Use threading instead of asyncio.create_task to avoid event loop issues
        import threading
        def run_send_message():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._send_message_with_retry(text))
            loop.close()
        
        send_thread = threading.Thread(target=run_send_message)
        send_thread.daemon = True
        send_thread.start()

    async def _send_message_with_retry(self, text, max_retries=5):
        """Send message with retry logic if WebSocket is not connected"""
        retries = 0
        retry_delay = 1.0  # Start with 1 second delay
        
        while retries < max_retries:
            # First check if we're connected
            if not self.ws_client.connected:
                logging.warning(f"WebSocket not connected, waiting for connection (attempt {retries+1}/{max_retries})")
                # Try to restart connection
                self.ws_client.start_connection()
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, 5.0)  # Exponential backoff up to 5 seconds
                retries += 1
                continue
                
            # Try to send the message
            try:
                result = await self.ws_client.send_message(text)
                if result:
                    logging.info(f"Message sent successfully: {text[:30]}...")
                    return True
                
                # If send_message returned False but no exception, wait and retry
                logging.warning(f"Failed to send message, retrying... (attempt {retries+1}/{max_retries})")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, 5.0)  # Exponential backoff up to 5 seconds
                retries += 1
            except Exception as e:
                logging.error(f"Error in send_message_with_retry: {e}")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, 5.0)  # Exponential backoff up to 5 seconds
                retries += 1
            
        logging.error(f"Failed to send message after {max_retries} attempts")
        return False

    @Slot()
    def clearChat(self):
        self.ws_client.messages.clear()
        self._assistant_text_in_progress = ""
        self._assistant_active = False
        self.newUserMessage.emit("")  # Signal to clear the chat area in QML
        logging.info("Chat history cleared.")

    @Slot()
    def stopAll(self):
        # Use threading instead of asyncio.create_task to avoid event loop issues
        import threading
        def run_stop_all():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._stop_tts_and_generation_async())
            loop.close()
        
        stop_thread = threading.Thread(target=run_stop_all)
        stop_thread.daemon = True
        stop_thread.start()

    def finalizeAssistantResponse(self):
        if self._assistant_active:
            self.ws_client.handle_assistant_message(self._assistant_text_in_progress)
            self._assistant_text_in_progress = ""
            self._assistant_active = False
            self.assistantResponseComplete.emit()

    def on_stt_complete(self, utterance: str):
        if utterance.strip():
            self.sendMessage(utterance)

    def on_stt_state_change(self, enabled: bool):
        self.sttEnabledChanged.emit(enabled)
        logging.info(f"STT state: {enabled}")

    def on_stt_text(self, text: str):
        # Handle STT text from the server
        logging.info(f"Received STT text from server: {text}")
        # You can process this text as needed

    def on_stt_state(self, enabled: bool):
        # Handle STT state changes from the server
        logging.info(f"Received STT state from server: {enabled}")
        # You can update UI accordingly

    def on_assistant_token(self, token: str):
        logging.debug(f"Received assistant token: {token[:30]}...")
        if not self._assistant_active:
            self._assistant_active = True
            self._assistant_text_in_progress = ""
        self._assistant_text_in_progress += token
        self.assistantTextUpdated.emit(self._assistant_text_in_progress)

    def on_server_tts_update(self, enabled: bool):
        self.tts_enabled = enabled
        self.ttsEnabledChanged.emit(enabled)
        logging.info(f"TTS state: {enabled}")

    def on_connection_status(self, connected: bool):
        logging.info(f"WebSocket connected: {connected}")
        
        if connected:
            # Connection established or restored
            if self._init_completed:
                # If initialization is complete, we're likely reconnecting after a disconnect
                logging.info("Connection restored, reinitializing TTS state")
                
                # Use threading instead of asyncio.create_task to avoid event loop issues
                import threading
                def run_init_tts():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self._init_tts_state())
                    loop.close()
                
                init_thread = threading.Thread(target=run_init_tts)
                init_thread.daemon = True
                init_thread.start()
                
                # If we have any pending messages in the UI, we might want to resend them
                # This would be a good place to implement message recovery logic
        else:
            # Connection lost
            logging.warning("WebSocket connection lost, will attempt to reconnect automatically")
            # The reconnection is handled by the WebSocket client's connect_ws method

    async def _toggle_tts_async(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{HTTP_BASE_URL}/api/toggle-tts") as resp:
                    data = await resp.json()
                    self.tts_enabled = data.get("tts_enabled", not self.tts_enabled)
                    self.ttsEnabledChanged.emit(self.tts_enabled)
        except Exception as e:
            logging.error(f"Error toggling TTS: {e}")

    async def _stop_tts_and_generation_async(self):
        try:
            logging.info("Stopping TTS and generation...")
            async with aiohttp.ClientSession() as session:
                # Stop audio first
                try:
                    await session.post(f"{HTTP_BASE_URL}/api/stop-audio")
                    logging.info("Stop audio request sent")
                except Exception as e:
                    logging.error(f"Error stopping audio: {e}")
                
                # Then stop generation
                try:
                    await session.post(f"{HTTP_BASE_URL}/api/stop-generation")
                    logging.info("Stop generation request sent")
                except Exception as e:
                    logging.error(f"Error stopping generation: {e}")
        except Exception as e:
            logging.error(f"Error stopping generation: {e}")
        
        logging.info("Finalizing assistant response.")
        self.finalizeAssistantResponse()

    async def _init_tts_state(self):
        """Initialize the TTS state by fetching it from the server with retry logic"""
        max_retries = 3
        retry_count = 0
        retry_delay = 1.0
        
        while retry_count < max_retries:
            try:
                # Try the direct endpoint first
                logging.info(f"Initializing TTS state (attempt {retry_count+1}/{max_retries})")
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(f"{HTTP_BASE_URL}/api/tts-state", timeout=3.0) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                self.tts_enabled = data.get("tts_enabled", False)
                                self.ttsEnabledChanged.emit(self.tts_enabled)
                                logging.info(f"TTS state initialized to: {self.tts_enabled}")
                                return
                    except aiohttp.ClientError as e:
                        logging.warning(f"Could not get TTS state directly: {e}")
                    
                    # Wait a bit before trying the toggle approach to reduce server load
                    await asyncio.sleep(0.5)
                    
                    # Fall back to single toggle to just get the current state
                    try:
                        async with session.post(f"{HTTP_BASE_URL}/api/toggle-tts", timeout=3.0) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                self.tts_enabled = data.get("tts_enabled", False)
                                self.ttsEnabledChanged.emit(self.tts_enabled)
                                logging.info(f"TTS state initialized to: {self.tts_enabled} (via toggle)")
                                return
                    except aiohttp.ClientError as e:
                        logging.error(f"Failed to initialize TTS state via toggle: {e}")
                        
            except Exception as e:
                logging.error(f"Error fetching TTS state: {e}")
            
            # If we get here, both methods failed, so retry after a delay
            retry_count += 1
            if retry_count < max_retries:
                logging.warning(f"Retrying TTS state initialization in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, 5.0)  # Exponential backoff up to 5 seconds
            
        # Default to disabled if all methods fail after max retries
        self.tts_enabled = False
        self.ttsEnabledChanged.emit(self.tts_enabled)
        logging.warning("Using default TTS state: disabled after all retry attempts failed")
