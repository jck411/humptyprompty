# chat_backend.py
from PySide6.QtCore import QObject, Signal, Slot
from frontend.stt.deepgram_stt import DeepgramSTT
from frontend.client_ws import AsyncWebSocketClient
import asyncio, aiohttp, logging

class ChatBackend(QObject):
    # Signals to update QML UI
    newUserMessage = Signal(str)            # Emit when a new user message is sent (for UI to display)
    assistantTextUpdated = Signal(str)      # Emit updated assistant text (partial or complete) 
    assistantResponseComplete = Signal()    # Emit when assistant response is finalized
    sttEnabledChanged = Signal(bool)        # Emit when STT enabled state toggles (for UI toggle state)
    ttsEnabledChanged = Signal(bool)        # Emit when TTS enabled state toggles

    def __init__(self):
        super().__init__()
        # Instantiate STT and WebSocket client
        self.stt = DeepgramSTT()
        self.ws_client = AsyncWebSocketClient(SERVER_HOST, SERVER_PORT, WEBSOCKET_PATH)
        self.tts_enabled = False  # will be updated from server response
        # Maintain partial assistant text state
        self._assistant_text_in_progress = ""
        self._assistant_active = False

        # Connect STT signals to backend slots
        self.stt.complete_utterance_received.connect(self.on_stt_complete)  # final transcript to input
        self.stt.state_changed.connect(self.on_stt_state_change)

        # Connect WebSocket signals to backend slots
        self.ws_client.message_received.connect(self.on_assistant_token)
        self.ws_client.connection_status.connect(self.on_connection_status)  # optional: for logging or title
        self.ws_client.audio_received.connect(self.on_audio_chunk)
        self.ws_client.tts_state_changed.connect(self.on_server_tts_update)

        # Start asynchronous tasks: connect to WebSocket and audio consumer
        asyncio.create_task(self.ws_client.connect())
        asyncio.create_task(self.audio_consumer_loop())
        logging.info("ChatBackend initialized and WebSocket connecting...")

        # (Optional) initialize TTS state from server
        asyncio.create_task(self._init_tts_state())

    @Slot()
    def toggleSTT(self):
        """Toggle the speech-to-text on/off."""
        self.stt.toggle()
        # state_changed signal from STT will update UI via on_stt_state_change

    @Slot()
    def toggleTTS(self):
        """Toggle TTS (text-to-speech) on the server via an HTTP call."""
        asyncio.create_task(self._toggle_tts_async())

    @Slot()
    def sendMessage(self, text):
        """Send a user message to the server (and display it in UI)."""
        text = text.strip()
        if not text:
            return
        # Finalize any ongoing assistant response before sending new message
        if self._assistant_active:
            self.finalizeAssistantResponse()
        # Emit signal to QML to display the user's message
        self.newUserMessage.emit(text)
        # Send the message via WebSocket
        asyncio.create_task(self.ws_client.send_message(text))
        # Clear the input field in QML (handled in QML after calling this slot)

    @Slot()
    def clearChat(self):
        """Clear chat history and reset state."""
        # Reset conversation history and state
        self.ws_client.messages.clear()
        self._assistant_text_in_progress = ""
        self._assistant_active = False
        # (Optionally stop any ongoing TTS or STT)
        # Emit signal to QML to clear the UI chat area
        # (We can reuse the same signal for now by sending an empty history or instruct via a separate signal)
        self.newUserMessage.emit("")  # (In QML, treat this as a command to clear chat if text is empty)
        logging.info("Chat history cleared.")

    @Slot()
    def stopAll(self):
        """Stop text generation and TTS playback (triggered by 'Stop' button)."""
        asyncio.create_task(self._stop_tts_and_generation_async())

    def finalizeAssistantResponse(self):
        """Finalize the in-progress assistant response (called before new user message or on manual stop)."""
        if self._assistant_active:
            # Record the complete assistant utterance in history
            self.ws_client.handle_assistant_message(self._assistant_text_in_progress)
            # Reset state
            self._assistant_text_in_progress = ""
            self._assistant_active = False
            # Notify QML that the assistant message is complete (to finalize UI bubble)
            self.assistantResponseComplete.emit()

    # --- Signal handlers (not QML-invokable, so no @Slot needed) ---
    def on_stt_complete(self, utterance: str):
        """Handler for final STT transcription: populate text input with the transcribed utterance."""
        if utterance.strip():
            # Emit a signal or directly set a property for QML to update input field
            # Here, we emit assistantTextUpdated as a means to set input (QML will detect target is input field)
            self.assistantTextUpdated.emit(utterance)  # we will handle this in QML InputBar to set text

    def on_stt_state_change(self, enabled: bool):
        """Update UI when STT listening state changes."""
        self.sttEnabledChanged.emit(enabled)
        logging.info(f"STT enabled state: {enabled}")

    def on_assistant_token(self, token: str):
        """Handle streaming assistant response tokens from server."""
        # On first token of a new response, create a new assistant bubble in UI
        if not self._assistant_active:
            self._assistant_active = True
            self._assistant_text_in_progress = ""
        # Append token and emit updated text
        self._assistant_text_in_progress += token
        self.assistantTextUpdated.emit(self._assistant_text_in_progress)

    def on_server_tts_update(self, enabled: bool):
        """Handle TTS state update from server (if any)."""
        self.tts_enabled = enabled
        self.ttsEnabledChanged.emit(enabled)
        logging.info(f"TTS enabled state: {enabled}")

    def on_connection_status(self, connected: bool):
        """Update application title or status on connection changes (handled in QML)."""
        # We can emit a signal or just log; QML will catch this via wsClient if exposed
        logging.info(f"WebSocket connected: {connected}")

    def on_audio_chunk(self, pcm_data: bytes):
        """Handle incoming audio for TTS – play via QAudioSink and manage STT pause/resume."""
        if pcm_data == b'audio:' or len(pcm_data) == 0:
            # End of TTS audio stream
            self.audio_queue.put_nowait(None)
            self.audio_device.mark_end_of_stream()
            if self.stt.is_enabled and self.tts_audio_playing:
                asyncio.create_task(self._resume_stt_after_tts())
            self.tts_audio_playing = False
        else:
            # If first audio chunk, pause STT (keepalive mode)
            if not self.tts_audio_playing:
                self.tts_audio_playing = True
                if self.stt.is_enabled:
                    logging.info("Pausing STT due to TTS playback")
                    self.stt.set_paused(True)
            # Strip "audio:" prefix if present and add to audio playback queue
            prefix = b'audio:'
            if pcm_data.startswith(prefix):
                pcm_data = pcm_data[len(prefix):]
            self.audio_queue.put_nowait(pcm_data)

    # --- Asynchronous helper methods ---
    async def _toggle_tts_async(self):
        """Async helper to call server API for toggling TTS."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{HTTP_BASE_URL}/api/toggle-tts") as resp:
                    data = await resp.json()
                    # Update TTS state based on response
                    self.tts_enabled = data.get("tts_enabled", not self.tts_enabled)
                    self.ttsEnabledChanged.emit(self.tts_enabled)
        except Exception as e:
            logging.error(f"Error toggling TTS via API: {e}")

    async def _stop_tts_and_generation_async(self):
        """Async helper to request server stop any ongoing TTS audio and text generation."""
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(f"{HTTP_BASE_URL}/api/stop-audio")
                await session.post(f"{HTTP_BASE_URL}/api/stop-generation")
        except Exception as e:
            logging.error(f"Error stopping generation: {e}")
        # Finalize any in-progress assistant text and stop audio playback
        logging.info("Stopping TTS playback and finalizing assistant response")
        self.finalizeAssistantResponse()
        # Stop audio sink if playing
        if self.audio_sink.state() == QAudio.State.ActiveState:
            self.audio_sink.stop()
        # Clear audio buffer and mark end-of-stream
        await asyncio.to_thread(self.audio_device.clear_and_mark_end)
        # Flush remaining audio queue
        while not self.audio_queue.empty():
            try: self.audio_queue.get_nowait()
            except asyncio.QueueEmpty: break
        self.audio_queue.put_nowait(None)

    async def _init_tts_state(self):
        """Retrieve initial TTS enabled state from server on startup (optional)."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{HTTP_BASE_URL}/api/tts-enabled") as resp:
                    data = await resp.json()
                    self.tts_enabled = data.get("tts_enabled", False)
                    self.ttsEnabledChanged.emit(self.tts_enabled)
        except Exception as e:
            logging.error(f"Could not fetch initial TTS state: {e}")
            self.tts_enabled = False
            self.ttsEnabledChanged.emit(self.tts_enabled)

    async def audio_consumer_loop(self):
        """Background task to feed PCM audio data to QAudioSink (plays TTS audio)."""
        logging.info("Starting audio consumer loop")
        while True:
            pcm_chunk = await self.audio_queue.get()
            if pcm_chunk is None:
                # End of stream: mark and wait for sink to stop
                await asyncio.to_thread(self.audio_device.mark_end_of_stream)
                # Wait until audio device buffer empties, then stop sink
                while len(self.audio_device.audio_buffer) > 0:
                    await asyncio.sleep(0.05)
                self.audio_sink.stop()
                # Notify server that playback is complete
                if self.ws_client.ws:
                    await self.ws_client.ws.send(json.dumps({"action": "playback-complete"}))
                await asyncio.to_thread(self.audio_device.reset_end_of_stream)
                continue
            # Ensure audio sink is active
            if self.audio_sink.state() != QAudio.State.ActiveState:
                await asyncio.to_thread(self.audio_device.open, QIODevice.ReadOnly)
                self.audio_sink.start(self.audio_device)
            # Write PCM chunk to audio output
            await asyncio.to_thread(self.audio_device.writeData, pcm_chunk)
            await asyncio.sleep(0)
