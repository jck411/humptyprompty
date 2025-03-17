#!/usr/bin/env python3
"""
Integration module to connect wake word detection with STT functionality
"""
import asyncio
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from frontend.config import logger
from frontend.wakeword.config import WAKEWORD_CONFIG
from frontend.wakeword.detector import WakeWordDetector

class WakeWordManager(QObject):
    """
    Manager class that handles the integration between wake word detection and STT
    """
    # Signals
    wake_word_detected = pyqtSignal(str)  # Wake word name
    wake_word_state_changed = pyqtSignal(bool)  # Is running
    
    def __init__(self, chat_controller=None):
        super().__init__()
        self.chat_controller = chat_controller
        self.detector = WakeWordDetector()
        
        # Set up wake sound path
        self.sounds_dir = Path(__file__).parent / "sounds"
        self.computer_wake_sound = self.sounds_dir / "Wakesound_24kHz_mono_16-bit PCM.wav"
        
        # Pre-load the wake sound data
        self.wake_sound_data = None
        if self.computer_wake_sound.exists():
            try:
                # Just read the binary data directly
                with open(self.computer_wake_sound, 'rb') as f:
                    # Skip the WAV header (44 bytes) to get just the PCM data
                    f.seek(44)  # Standard WAV header size
                    self.wake_sound_data = f.read()
                    logger.info(f"Loaded wake sound: {self.computer_wake_sound, len(self.wake_sound_data)} bytes")
            except Exception as e:
                logger.error(f"Error loading wake sound: {e}")
        
        # Connect signals
        self.detector.wake_word_detected.connect(self._on_wake_word_detected)
        
        # Start wake word detection if configured
        self.enabled = WAKEWORD_CONFIG.get('enabled', False)
        if self.enabled and WAKEWORD_CONFIG.get('auto_start', True):
            self.start()
            
    def set_chat_controller(self, chat_controller):
        """Set the chat controller reference"""
        self.chat_controller = chat_controller
        
    def start(self):
        """Start wake word detection"""
        if not self.detector.is_running:
            self.detector.start()
            self.wake_word_state_changed.emit(self.detector.is_running)
            
    def stop(self):
        """Stop wake word detection"""
        if self.detector.is_running:
            self.detector.stop()
            self.wake_word_state_changed.emit(self.detector.is_running)
            
    def toggle(self):
        """Toggle wake word detection on/off"""
        self.detector.toggle()
        self.wake_word_state_changed.emit(self.detector.is_running)
    
    def play_wake_sound(self):
        """Play the wake sound using the application's audio manager"""
        if self.chat_controller and self.wake_sound_data:
            # Get a reference to the audio manager from the chat controller
            audio_manager = self.chat_controller.audio_manager
            if audio_manager:
                # Put the wake sound data directly into the audio queue
                audio_manager.audio_queue.put_nowait(self.wake_sound_data)
                logger.info("Wake sound queued for playback")
            else:
                logger.warning("Audio manager not available, can't play wake sound")
    
    @pyqtSlot(str)
    def _on_wake_word_detected(self, wake_word):
        """Handle wake word detection event"""
        logger.info(f"Wake word manager detected: {wake_word}")
        
        # Forward the signal
        self.wake_word_detected.emit(wake_word)
        
        # Activate STT if chat controller is available
        if self.chat_controller:
            # Handle different wake words
            if wake_word.lower() == "computer":
                # Play wake sound for "computer" wake word only
                if self.wake_sound_data:
                    logger.info(f"Playing wake sound for '{wake_word}'")
                    self.play_wake_sound()
                
                # Only activate STT if it's not already active
                if not self.chat_controller.frontend_stt.is_enabled:
                    logger.info("Activating STT based on wake word detection")
                    self.chat_controller.toggle_stt()
                    
                    # Also enable auto-send mode
                    if not self.chat_controller.auto_send_enabled:
                        logger.info("Enabling auto-send based on wake word detection")
                        self.chat_controller.auto_send_enabled = True
                        self.chat_controller.auto_send_state_changed.emit(True)
                else:
                    logger.info("STT is already active, ignoring wake word")
            elif wake_word.lower() in ["stop-there", "stop"]:  # Handle both formats in case of filename parsing issues
                # Stop TTS and text generation (no sound played)
                # This acts like the stop button without turning off STT
                logger.info("Stopping TTS and generation based on wake word without disabling STT")
                
                # Create a more robust handling of the stop action with a timeout
                async def stop_with_timeout():
                    try:
                        # Set a timeout to avoid hanging if something goes wrong
                        await asyncio.wait_for(
                            self.chat_controller.stop_tts_and_generation_async(),
                            timeout=5.0
                        )
                        logger.info("Stop operation successfully completed")
                        
                        # Important: After stopping is complete, ensure STT is actively listening
                        # Wait a short moment to let things settle
                        await asyncio.sleep(0.5)
                        
                        # If STT is enabled but not listening, restart it
                        if (self.chat_controller.stt_enabled and 
                            hasattr(self.chat_controller, 'frontend_stt') and 
                            not self.chat_controller.stt_listening):
                            logger.info("Re-activating STT listening after stop")
                            self.chat_controller.frontend_stt.restart_listening()
                    except asyncio.TimeoutError:
                        logger.warning("Stop operation timed out, forcing audio stop")
                        # Force a direct audio stop if the main stop times out
                        if self.chat_controller and self.chat_controller.audio_manager:
                            await self.chat_controller.audio_manager.stop_audio()
                            # Still try to restart listening
                            if (self.chat_controller.stt_enabled and
                                hasattr(self.chat_controller, 'frontend_stt')):
                                logger.info("Re-activating STT listening after timeout")
                                self.chat_controller.frontend_stt.restart_listening()
                    except Exception as e:
                        logger.error(f"Error during stop operation: {e}")
                        # Still try to reset audio state on error
                        if self.chat_controller and self.chat_controller.audio_manager:
                            await self.chat_controller.audio_manager.stop_audio()
                            # Try to restart listening even after error
                            if (self.chat_controller.stt_enabled and
                                hasattr(self.chat_controller, 'frontend_stt')):
                                logger.info("Re-activating STT listening after error")
                                self.chat_controller.frontend_stt.restart_listening()
                
                # Launch the robust stop handler
                asyncio.create_task(stop_with_timeout())
            else:
                logger.warning("Unknown wake word, can't activate STT")
        else:
            logger.warning("Chat controller not set, can't activate STT on wake word")
    
    def cleanup(self):
        """Clean up resources"""
        self.stop()
        
    def __del__(self):
        """Clean up on deletion"""
        self.cleanup()