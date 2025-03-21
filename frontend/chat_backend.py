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

        self.stt.complete_utterance_received.connect(self.on_stt_complete)
        self.stt.state_changed.connect(self.on_stt_state_change)

        self.ws_client.message_received.connect(self.on_assistant_token)
        self.ws_client.connection_status.connect(self.on_connection_status)
        self.ws_client.tts_state_changed.connect(self.on_server_tts_update)

        logging.info("ChatBackend initialized.")
        
    async def initialize(self):
        """Initialize async components after the event loop is running"""
        await self.ws_client.connect_ws()
        await self._init_tts_state()

    @Slot()
    def toggleSTT(self):
        self.stt.toggle()

    @Slot()
    def toggleTTS(self):
        asyncio.create_task(self._toggle_tts_async())

    @Slot(str)
    def sendMessage(self, text):
        text = text.strip()
        if not text:
            return
        if self._assistant_active:
            self.finalizeAssistantResponse()
        self.newUserMessage.emit(text)
        asyncio.create_task(self.ws_client.send_message(text))

    @Slot()
    def clearChat(self):
        self.ws_client.messages.clear()
        self._assistant_text_in_progress = ""
        self._assistant_active = False
        self.newUserMessage.emit("")  # Signal to clear the chat area in QML
        logging.info("Chat history cleared.")

    @Slot()
    def stopAll(self):
        asyncio.create_task(self._stop_tts_and_generation_async())

    def finalizeAssistantResponse(self):
        if self._assistant_active:
            self.ws_client.handle_assistant_message(self._assistant_text_in_progress)
            self._assistant_text_in_progress = ""
            self._assistant_active = False
            self.assistantResponseComplete.emit()

    def on_stt_complete(self, utterance: str):
        if utterance.strip():
            self.assistantTextUpdated.emit(utterance)

    def on_stt_state_change(self, enabled: bool):
        self.sttEnabledChanged.emit(enabled)
        logging.info(f"STT state: {enabled}")

    def on_assistant_token(self, token: str):
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
            async with aiohttp.ClientSession() as session:
                await session.post(f"{HTTP_BASE_URL}/api/stop-audio")
                await session.post(f"{HTTP_BASE_URL}/api/stop-generation")
        except Exception as e:
            logging.error(f"Error stopping generation: {e}")
        logging.info("Stopping TTS and finalizing assistant response.")
        self.finalizeAssistantResponse()

    async def _init_tts_state(self):
        try:
            # Instead of getting the state from a GET endpoint, we'll use the response
            # from the toggle-tts endpoint which returns the current state after toggling
            # We'll toggle twice to get the state without changing it
            async with aiohttp.ClientSession() as session:
                # First toggle
                async with session.post(f"{HTTP_BASE_URL}/api/toggle-tts") as resp:
                    data = await resp.json()
                    current_state = data.get("tts_enabled", False)
                
                # Toggle back to original state
                async with session.post(f"{HTTP_BASE_URL}/api/toggle-tts") as resp:
                    data = await resp.json()
                    self.tts_enabled = data.get("tts_enabled", False)
                    self.ttsEnabledChanged.emit(self.tts_enabled)
                    
                # Verify we're back to the original state
                if current_state != self.tts_enabled:
                    logging.info(f"TTS state initialized to: {self.tts_enabled}")
        except Exception as e:
            logging.error(f"Error fetching TTS state: {e}")
            self.tts_enabled = False
            self.ttsEnabledChanged.emit(self.tts_enabled)
