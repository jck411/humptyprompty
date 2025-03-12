#!/usr/bin/env python3
import asyncio
import json
from PyQt6.QtCore import QObject, pyqtSignal

from frontend.network import AsyncWebSocketClient
from frontend.audio import AudioManager
from frontend.stt.deepgram_stt import DeepgramSTT
from frontend.config import logger
from frontend.stt.config import STT_CONFIG
from frontend.wakeword.integration import WakeWordManager
from frontend.wakeword.config import WAKEWORD_CONFIG

class ChatController(QObject):
    """
    Controller class that handles the business logic of the chat application.
    This separates the application logic from the UI components.
    """
    # Signals to communicate with UI
    message_received = pyqtSignal(str)
    assistant_message_finalized = pyqtSignal()
    connection_status_changed = pyqtSignal(bool)
    stt_state_changed = pyqtSignal(bool, bool)  # is_enabled, is_listening
    tts_state_changed = pyqtSignal(bool)
    auto_send_state_changed = pyqtSignal(bool)
    interim_stt_text_received = pyqtSignal(str)
    final_stt_text_received = pyqtSignal(str)
    audio_state_changed = pyqtSignal(object)  # QAudio.State
    user_message_added = pyqtSignal(str)  # Signal for when a user message is added
    wake_word_state_changed = pyqtSignal(bool)  # is_wake_word_detection_running
    wake_word_detected = pyqtSignal(str)  # wake_word_name
    
    def __init__(self):
        super().__init__()
        
        # Initialize state
        self.messages = []
        self.assistant_text_in_progress = ""
        self.stt_enabled = STT_CONFIG.get('enabled', False)
        self.stt_listening = False
        self.tts_enabled = False
        self.auto_send_enabled = False
        self.is_toggling_stt = False
        self.is_toggling_tts = False
        self.wake_word_enabled = WAKEWORD_CONFIG.get('enabled', False)
        
        # Initialize components
        self.audio_manager = AudioManager()
        self.frontend_stt = DeepgramSTT()
        self.ws_client = AsyncWebSocketClient()
        self.wake_word_manager = WakeWordManager(self)
        
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
        self.ws_client.generation_stopped.connect(self.finalize_assistant_message)
        self.ws_client.audio_stopped.connect(lambda: asyncio.create_task(self.audio_manager.stop_audio()))
        
        # STT signals
        self.frontend_stt.transcription_received.connect(self.handle_interim_stt_text)
        self.frontend_stt.complete_utterance_received.connect(self.handle_final_stt_text)
        self.frontend_stt.state_changed.connect(self.handle_frontend_stt_state)
        self.frontend_stt.enabled_changed.connect(self.handle_frontend_stt_enabled)
        
        # Audio manager signals
        self.audio_manager.audio_state_changed.connect(self.handle_audio_state_changed)
        
        # Wake word signals
        self.wake_word_manager.wake_word_detected.connect(self.handle_wake_word_detected)
        self.wake_word_manager.wake_word_state_changed.connect(self.handle_wake_word_state_changed)
    
    def initialize(self):
        """Initialize the controller and start async tasks"""
        self.audio_manager.start_audio_consumer()
        self.async_tasks.append(asyncio.create_task(self.ws_client.connect()))
        asyncio.create_task(self._init_states_async())
        logger.info("ChatController initialized and async tasks created")
    
    async def _init_states_async(self):
        """Initialize states that require async operations"""
        try:
            # Get all states at once
            all_states = await self.ws_client.get_all_initial_states()
            if all_states:
                # Update TTS state
                self.tts_enabled = all_states.get("tts_enabled", False)
                self.tts_state_changed.emit(self.tts_enabled)
                
                # Update auto-send state
                self.auto_send_enabled = all_states.get("auto_send_enabled", False)
                self.auto_send_state_changed.emit(self.auto_send_enabled)
                
                logger.info(f"Initialized states from server: {all_states}")
            else:
                # If the endpoint fails, use default values
                logger.warning("Failed to get states from server, using defaults")
                self.tts_enabled = False
                self.tts_state_changed.emit(self.tts_enabled)
                
                self.auto_send_enabled = False
                self.auto_send_state_changed.emit(self.auto_send_enabled)
        except Exception as e:
            logger.error(f"Error initializing states: {e}")
            # Set default values in case of error
            self.tts_enabled = False
            self.tts_state_changed.emit(self.tts_enabled)
            
            self.auto_send_enabled = False
            self.auto_send_state_changed.emit(self.auto_send_enabled)
            
        # Always use the local STT configuration
        self.stt_enabled = STT_CONFIG.get('enabled', False)
        self.stt_state_changed.emit(self.stt_enabled, self.stt_listening)
        logger.info(f"Using local STT configuration: enabled={self.stt_enabled}")
            
        # Reset toggle flags
        self.is_toggling_tts = False
        self.is_toggling_stt = False
    
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
            self.add_message(self.assistant_text_in_progress, False)
            self.assistant_text_in_progress = ""
            self.assistant_message_finalized.emit()
    
    def add_message(self, text, is_user):
        """Add a message to the chat history"""
        self.messages.append({
            "text": text,
            "is_user": is_user
        })
        # Emit signal for user messages
        if is_user:
            self.user_message_added.emit(text)
    
    def clear_chat_history(self):
        """Clear the chat history"""
        self.messages = []
        self.assistant_text_in_progress = ""
    
    def handle_audio_state_changed(self, state):
        """Handle audio state changes"""
        self.audio_state_changed.emit(state)
    
    def on_audio_received(self, pcm_data: bytes):
        """Handle audio data received from the server"""
        self.audio_manager.process_audio_data(pcm_data, self.frontend_stt)
    
    def handle_tts_state_changed(self, is_enabled: bool):
        """Handle TTS state changes"""
        self.tts_enabled = is_enabled
        self.tts_state_changed.emit(is_enabled)
    
    def toggle_auto_send(self):
        """Toggle auto-send mode"""
        self.auto_send_enabled = not self.auto_send_enabled
        logger.info(f"Auto-send mode {'enabled' if self.auto_send_enabled else 'disabled'}")
        self.auto_send_state_changed.emit(self.auto_send_enabled)
    
    async def toggle_tts_async(self):
        """Toggle TTS mode asynchronously"""
        if self.is_toggling_tts:
            return
            
        self.is_toggling_tts = True
        try:
            new_state = await self.ws_client.toggle_tts()
            self.tts_enabled = new_state
            self.tts_state_changed.emit(new_state)
            logger.info(f"TTS toggled to: {new_state}")
        except Exception as e:
            logger.error(f"Error toggling TTS: {e}")
        finally:
            self.is_toggling_tts = False
    
    async def stop_tts_and_generation_async(self):
        """Stop TTS and text generation asynchronously"""
        try:
            await self.ws_client.stop_tts_and_generation()
            await self.audio_manager.stop_audio()
            self.finalize_assistant_message()
        except Exception as e:
            logger.error(f"Error stopping TTS and generation: {e}")
    
    def handle_connection_status(self, connected):
        """Handle connection status changes"""
        self.connection_status_changed.emit(connected)
    
    def handle_interim_stt_text(self, text):
        """Handle interim STT text"""
        self.interim_stt_text_received.emit(text)
    
    def handle_final_stt_text(self, text):
        """Handle final STT text"""
        self.final_stt_text_received.emit(text)
        
        # If auto-send is enabled, automatically send the message
        if self.auto_send_enabled and text.strip():
            logger.info(f"Auto-sending message: {text}")
            self.send_message(text)
    
    def handle_frontend_stt_state(self, is_listening):
        """Handle frontend STT state changes (listening state)"""
        self.stt_listening = is_listening
        self.stt_state_changed.emit(self.stt_enabled, is_listening)
        
        if not is_listening:
            # Reset interim text when STT is stopped
            self.interim_stt_text_received.emit("")
        
        logger.info(f"STT listening state changed to: {'listening' if is_listening else 'not listening'}")
    
    def handle_frontend_stt_enabled(self, is_enabled):
        """Handle frontend STT enabled state changes"""
        self.stt_enabled = is_enabled
        self.stt_state_changed.emit(is_enabled, self.stt_listening)
        
        # If STT is turned off, also turn off Auto Send
        if not is_enabled and self.auto_send_enabled:
            self.auto_send_enabled = False
            self.auto_send_state_changed.emit(False)
            logger.info("Auto-send disabled because STT was turned off")
        
        logger.info(f"STT enabled state changed to: {'enabled' if is_enabled else 'disabled'}")
    
    def toggle_stt(self):
        """Toggle STT mode"""
        if self.is_toggling_stt:
            return
            
        self.is_toggling_stt = True
        try:
            # Use the toggle method from DeepgramSTT
            self.frontend_stt.toggle()
            logger.info(f"STT toggled, current state: {self.frontend_stt.is_enabled}")
        except Exception as e:
            logger.error(f"Error toggling STT: {e}")
        finally:
            self.is_toggling_stt = False
    
    def handle_wake_word_detected(self, wake_word):
        """Handle wake word detection event"""
        logger.info(f"Wake word detected by controller: {wake_word}")
        self.wake_word_detected.emit(wake_word)
        
    def handle_wake_word_state_changed(self, is_running):
        """Handle wake word state change event"""
        logger.info(f"Wake word detection state changed: {'running' if is_running else 'stopped'}")
        self.wake_word_state_changed.emit(is_running)
        
    def toggle_wake_word_detection(self):
        """Toggle wake word detection on/off"""
        is_running = self.wake_word_manager.toggle()
        logger.info(f"Wake word detection toggled, current state: {'running' if is_running else 'stopped'}")
        return is_running
    
    def cleanup(self):
        """Clean up resources when shutting down"""
        logger.info("Cleaning up chat controller resources")
        
        # Stop wake word detection
        if hasattr(self, 'wake_word_manager'):
            self.wake_word_manager.cleanup()
            
        # Cancel any running async tasks
        for task in self.async_tasks:
            if not task.done():
                task.cancel()
        
        # Clean up audio
        if hasattr(self, 'audio_manager'):
            self.audio_manager.cleanup()
            
        # Clean up STT
        if hasattr(self, 'frontend_stt'):
            self.frontend_stt.stop()
            
        # Clean up websocket
        if hasattr(self, 'ws_client'):
            asyncio.create_task(self.ws_client.close())
        
        logger.info("Chat controller resources cleaned up") 