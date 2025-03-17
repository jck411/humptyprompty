#!/usr/bin/env python3
"""
Wake word detector for the Humptyprompty application
"""
import struct
import time
import threading
import logging
import pyaudio
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

from frontend.config import logger
from frontend.wakeword.config import WAKEWORD_CONFIG
from frontend.wakeword.custom_porcupine import create as create_porcupine

class WakeWordDetector(QObject):
    """
    Wake word detector that listens for specific wake words and triggers actions
    """
    # Signal emitted when a wake word is detected
    wake_word_detected = pyqtSignal(str)  # wake_word_name

    def __init__(self):
        super().__init__()
        self.is_enabled = WAKEWORD_CONFIG.get('enabled', False)
        self.sensitivity = WAKEWORD_CONFIG.get('sensitivity', 0.7)
        self.model_paths = WAKEWORD_CONFIG.get('model_paths', [])
        self.sample_rate = WAKEWORD_CONFIG.get('sample_rate', 16000)
        self.audio_device_index = WAKEWORD_CONFIG.get('audio_device_index')
        self.cooldown_period = WAKEWORD_CONFIG.get('cooldown_period', 3.0)
        self.auto_start = WAKEWORD_CONFIG.get('auto_start', True)
        
        # Initialize attributes
        self.porcupine = None
        self.pa = None
        self.audio_stream = None
        self.is_running = False
        self.last_detection_time = 0
        
        # Wake word names, derived from model filenames
        # Extract file stem and take everything before the first underscore, preserving hyphens
        self.wake_words = []
        for path in self.model_paths:
            stem = Path(path).stem
            if '_' in stem:
                word = stem.split('_')[0]
            else:
                word = stem
            self.wake_words.append(word)
        
        logger.info(f"Initialized wake words: {self.wake_words}")
        
        # Setup detection thread
        self.detection_thread = None
        self.stop_event = threading.Event()
        
        # Auto start if configured
        if self.auto_start and self.is_enabled:
            self.start()

    def start(self):
        """Start wake word detection"""
        if self.is_running:
            logger.warning("Wake word detection already running")
            return
            
        logger.info("Starting wake word detection...")
        
        try:
            # Initialize Porcupine wake word detector with multiple keywords
            self.porcupine = create_porcupine(
                keyword_paths=self.model_paths,
                sensitivities=[self.sensitivity] * len(self.model_paths)
            )
            
            # Initialize PyAudio
            self.pa = pyaudio.PyAudio()
            
            # Open audio stream
            self.audio_stream = self.pa.open(
                rate=self.porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.porcupine.frame_length,
                input_device_index=self.audio_device_index
            )
            
            # Reset stop event
            self.stop_event.clear()
            
            # Start detection thread
            self.detection_thread = threading.Thread(
                target=self._detection_loop,
                daemon=True
            )
            self.detection_thread.start()
            
            self.is_running = True
            logger.info("Wake word detection started successfully")
            
        except Exception as e:
            logger.error(f"Error starting wake word detection: {e}")
            self.cleanup()

    def stop(self):
        """Stop wake word detection"""
        if not self.is_running:
            return
            
        logger.info("Stopping wake word detection...")
        
        # Signal the detection thread to stop
        self.stop_event.set()
        
        # Wait for the thread to finish (with timeout)
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=2.0)
            
        # Cleanup resources
        self.cleanup()
        
        self.is_running = False
        logger.info("Wake word detection stopped")

    def cleanup(self):
        """Clean up resources"""
        if self.audio_stream:
            try:
                self.audio_stream.close()
            except Exception as e:
                logger.error(f"Error closing audio stream: {e}")
            self.audio_stream = None
            
        if self.pa:
            try:
                self.pa.terminate()
            except Exception as e:
                logger.error(f"Error terminating PyAudio: {e}")
            self.pa = None
            
        if self.porcupine:
            try:
                self.porcupine.delete()
            except Exception as e:
                logger.error(f"Error deleting Porcupine: {e}")
            self.porcupine = None
    
    def toggle(self):
        """Toggle wake word detection on/off"""
        if self.is_running:
            self.stop()
        else:
            self.start()
        return self.is_running
    
    def _detection_loop(self):
        """Main detection loop that runs in a separate thread"""
        logger.info("Wake word detection loop started")
        
        try:
            while not self.stop_event.is_set():
                # Read audio frame
                pcm_bytes = self.audio_stream.read(self.porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm_bytes)
                
                # Process audio for wake word detection
                keyword_index = self.porcupine.process(pcm)
                
                # If a wake word is detected
                if keyword_index >= 0 and keyword_index < len(self.wake_words):
                    current_time = time.time()
                    # Check cooldown period
                    if current_time - self.last_detection_time > self.cooldown_period:
                        self.last_detection_time = current_time
                        wake_word = self.wake_words[keyword_index]
                        logger.info(f"Wake word detected: {wake_word}")
                        # Emit signal with detected wake word
                        self.wake_word_detected.emit(wake_word)
                
                # Small sleep to reduce CPU usage
                time.sleep(0.01)
                
        except Exception as e:
            logger.error(f"Error in wake word detection loop: {e}")
            
        logger.info("Wake word detection loop ended")
    
    def __del__(self):
        """Clean up on deletion"""
        self.stop()

# For testing
if __name__ == "__main__":
    # Basic logger setup for testing
    logging.basicConfig(level=logging.INFO)
    
    detector = WakeWordDetector()
    
    def on_wake_word(word):
        print(f"\nWake word detected: {word}")
        
    detector.wake_word_detected.connect(on_wake_word)
    
    if not detector.is_running:
        detector.start()
        
    try:
        print("Listening for wake words... Press Ctrl+C to exit")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        detector.stop()