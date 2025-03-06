#!/usr/bin/env python3
import asyncio
import json
from PyQt6.QtCore import QObject, pyqtSignal

from frontend.network import AsyncWebSocketClient
from frontend.audio import AudioManager
from frontend.stt.deepgram_stt import DeepgramSTT
from frontend.config import logger

class ChatController(QObject):
    """
    Controller class that handles the business logic of the chat application.
    This separates the application logic from the UI components.
    """
    # Signals to communicate with UI
    message_received = pyqtSignal(str)
    assistant_message_finalized = pyqtSignal()
    connection_status_changed = pyqtSignal(bool)
    stt_state_changed = pyqtSignal(bool)
    tts_state_changed = pyqtSignal(bool)
    interim_stt_text_received = pyqtSignal(str)
    final_stt_text_received = pyqtSignal(str)
    audio_state_changed = pyqtSignal(object)  # QAudio.State
    
    def __init__(self):
        super().__init__()
        
        # Initialize state
        self.messages = []
        self.assistant_text_in_progress = ""
        self.stt_listening = True
        self.tts_enabled = False
        self.is_toggling_stt = False
        self.is_toggling_tts = False
        
        # Initialize components
        self.audio_manager = AudioManager()
        self.frontend_stt = DeepgramSTT()
        self.ws_client = AsyncWebSocketClient()
        
        # Connect signals
        self._connect_signals()
        
        # Async tasks
        self.async_tasks = []
    
    def _connect_signals(self):
        """Connect all internal signals between components"""
        # WebSocket client signals
        self.ws_client.message_received.connect(self.handle_message)
        self.ws_client.connection_status.connect(self.handle_connection_status)
        self.ws_client.audio_received.connect(self.on_audio_received)
        self.ws_client.tts_state_changed.connect(self.handle_tts_state_changed)
        self.ws_client.tts_toggled.connect(self.handle_tts_state_changed)
        self.ws_client.generation_stopped.connect(self.finalize_assistant_message)
        self.ws_client.audio_stopped.connect(lambda: asyncio.create_task(self.audio_manager.stop_audio()))
        
        # STT signals
        self.frontend_stt.transcription_received.connect(self.handle_interim_stt_text)
        self.frontend_stt.complete_utterance_received.connect(self.handle_final_stt_text)
        self.frontend_stt.state_changed.connect(self.handle_frontend_stt_state)
        
        # Audio manager signals
        self.audio_manager.audio_state_changed.connect(self.handle_audio_state_changed)
    
    def initialize(self):
        """Initialize the controller and start async tasks"""
        self.audio_manager.start_audio_consumer()
        self.async_tasks.append(asyncio.create_task(self.ws_client.connect()))
        asyncio.create_task(self._init_states_async())
        logger.info("ChatController initialized and async tasks created")
    
    async def _init_states_async(self):
        """Initialize states that require async operations"""
        try:
            self.tts_enabled = await self.ws_client.get_initial_tts_state()
            logger.info(f"Initial TTS state: {self.tts_enabled}")
            self.tts_state_changed.emit(self.tts_enabled)
        except Exception as e:
            logger.error(f"Error getting initial TTS state: {e}")
            self.tts_enabled = False
        self.is_toggling_tts = False
    
    def send_message(self, text):
        """Send a user message to the server"""
        if not text.strip():
            return
            
        try:
            self.finalize_assistant_message()
            self.add_message(text, True)
            asyncio.create_task(self.ws_client.send_message(text))
            return True
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    def handle_message(self, token):
        """Handle incoming message tokens from the server"""
        self.assistant_text_in_progress += token
        self.message_received.emit(token)
    
    def finalize_assistant_message(self):
        """Finalize the current assistant message"""
        if self.assistant_text_in_progress:
            self.ws_client.handle_assistant_message(self.assistant_text_in_progress)
            self.assistant_text_in_progress = ""
            self.assistant_message_finalized.emit()
    
    def add_message(self, text, is_user):
        """Add a message to the message history"""
        if is_user:
            self.messages.append({"sender": "user", "text": text})
        else:
            self.messages.append({"sender": "assistant", "text": text})
    
    def clear_chat_history(self):
        """Clear the chat history"""
        self.messages.clear()
        self.assistant_text_in_progress = ""
        self.ws_client.clear_messages()
        logger.info("Chat history cleared")
    
    def handle_audio_state_changed(self, state):
        """Handle audio state changes"""
        logger.info(f"[handle_audio_state_changed] Audio state changed to: {state}")
        self.audio_state_changed.emit(state)
    
    def on_audio_received(self, pcm_data: bytes):
        """Handle received audio data"""
        self.audio_manager.process_audio_data(pcm_data, self.frontend_stt)
        if pcm_data == b'audio:' or len(pcm_data) == 0:
            asyncio.create_task(self.ws_client.send_playback_complete())
    
    def handle_tts_state_changed(self, is_enabled: bool):
        """Handle TTS state changes"""
        self.tts_enabled = is_enabled
        self.tts_state_changed.emit(is_enabled)
    
    async def toggle_tts_async(self):
        """Toggle text-to-speech"""
        if self.is_toggling_tts:
            return
            
        self.is_toggling_tts = True
        try:
            await self.ws_client.toggle_tts()
        except Exception as e:
            logger.error(f"Error toggling TTS: {e}")
        finally:
            self.is_toggling_tts = False
    
    async def stop_tts_and_generation_async(self):
        """Stop TTS and text generation"""
        logger.info("Stop button pressed - stopping TTS and generation")
        await self.ws_client.stop_tts_and_generation()
        await self.audio_manager.stop_audio()
        logger.info("Finalizing assistant message")
        self.finalize_assistant_message()
    
    def handle_connection_status(self, connected):
        """Handle connection status changes"""
        self.connection_status_changed.emit(connected)
    
    def handle_interim_stt_text(self, text):
        """Handle interim STT text"""
        if text.strip():
            self.interim_stt_text_received.emit(text)
    
    def handle_final_stt_text(self, text):
        """Handle final STT text"""
        if text.strip():
            self.final_stt_text_received.emit(text)
    
    def handle_frontend_stt_state(self, is_listening):
        """Handle STT state changes"""
        try:
            self.stt_listening = is_listening
            self.stt_state_changed.emit(is_listening)
        except asyncio.CancelledError:
            logger.warning("STT state update task was cancelled - this is expected during shutdown")
        except Exception as e:
            logger.error(f"Error updating STT state: {e}")
    
    def toggle_stt(self):
        """Toggle speech-to-text"""
        if self.is_toggling_stt:
            return
            
        self.is_toggling_stt = True
        try:
            if hasattr(self.frontend_stt, 'toggle'):
                self.frontend_stt.toggle()
                self.handle_frontend_stt_state(not self.stt_listening)
            else:
                logger.error("Frontend STT implementation missing toggle method")
                self.handle_frontend_stt_state(not self.stt_listening)
        except asyncio.CancelledError:
            logger.warning("STT toggle task was cancelled - this is expected during shutdown")
        except Exception as e:
            logger.error(f"Error toggling STT: {e}")
            self.handle_frontend_stt_state(not self.stt_listening)
        finally:
            self.is_toggling_stt = False
    
    def cleanup(self):
        """Clean up resources and cancel async tasks"""
        logger.info("Cleaning up ChatController resources...")
        
        # Stop STT
        if hasattr(self, 'frontend_stt') and self.frontend_stt:
            self.frontend_stt.stop()
        
        # Clean up audio manager
        if hasattr(self, 'audio_manager'):
            self.audio_manager.cleanup()
        
        # Stop WebSocket client
        if hasattr(self, 'ws_client') and self.ws_client:
            self.ws_client.running = False
        
        # Cancel async tasks
        if hasattr(self, 'async_tasks'):
            for task in self.async_tasks:
                if not task.done():
                    task.cancel() 