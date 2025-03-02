import os
import asyncio
import sounddevice as sd
import numpy as np
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from PyQt6.QtCore import QObject, pyqtSignal
from dotenv import load_dotenv
from .config import AUDIO_CONFIG, DEEPGRAM_CONFIG, STT_CONFIG

# Load environment variables
load_dotenv()

class DeepgramSTT(QObject):
    """Frontend implementation of Deepgram's real-time speech-to-text using the official SDK."""
    
    # PyQt signals for transcription results
    transcription_received = pyqtSignal(str)  # For both interim and final results
    state_changed = pyqtSignal(bool)  # Emits True when listening, False when stopped
    enabled_changed = pyqtSignal(bool)  # Emits True when enabled, False when disabled

    def __init__(self):
        super().__init__()
        self.is_listening = False
        self.is_enabled = STT_CONFIG['enabled']
        
        # Initialize Deepgram client
        api_key = os.getenv('DEEPGRAM_API_KEY')
        if not api_key:
            raise ValueError("Missing DEEPGRAM_API_KEY in environment variables")
        self.deepgram = DeepgramClient(api_key)
        self.dg_connection = None
        self.stream = None

        print("DeepgramSTT initialized with config:", DEEPGRAM_CONFIG)

        # Auto-start if configured
        if STT_CONFIG['auto_start'] and self.is_enabled:
            self.start()

    def setup_connection(self):
        """Set up the Deepgram WebSocket connection and event handlers."""
        # Create a live transcription WebSocket connection
        self.dg_connection = self.deepgram.listen.websocket.v("1")
        
        # Register event handlers
        self.dg_connection.on(
            LiveTranscriptionEvents.Open,
            lambda client, *args, **kwargs: print("Deepgram connection established")
        )
        
        self.dg_connection.on(
            LiveTranscriptionEvents.Close,
            lambda client, *args, **kwargs: self._handle_close()
        )
        
        self.dg_connection.on(
            LiveTranscriptionEvents.Warning,
            lambda client, warning, **kwargs: print("Deepgram warning:", warning)
        )
        
        self.dg_connection.on(
            LiveTranscriptionEvents.Error,
            lambda client, error, **kwargs: self._handle_error(error)
        )
        
        # Handler for transcript events
        def on_transcript(client, result, **kwargs):
            try:
                transcript = result.channel.alternatives[0].transcript
                if transcript.strip():
                    print(f"Received transcript: {transcript}")
                    self.transcription_received.emit(transcript)
            except Exception as e:
                print(f"Error handling transcript: {str(e)}")
        
        self.dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript)

    def audio_callback(self, indata, frames, time, status):
        """Callback for sounddevice stream to process incoming audio chunks."""
        if status:
            print(f'Audio callback status: {status}')
            return
            
        if self.is_listening and self.is_enabled and self.dg_connection:
            try:
                # Send audio data directly to Deepgram
                self.dg_connection.send(indata.tobytes())
            except Exception as e:
                print(f"Error in audio callback: {str(e)}")

    def _handle_error(self, error):
        """Handle Deepgram errors."""
        print(f"Deepgram error: {error}")
        if self.is_listening:
            self.stop()

    def _handle_close(self):
        """Handle Deepgram connection close."""
        print("Deepgram connection closed")
        if self.is_listening:
            self.stop()

    def start(self):
        """Start transcription."""
        if not self.is_enabled:
            print("Cannot start: STT is disabled")
            return

        if not self.is_listening:
            try:
                print("Starting STT...")
                self.is_listening = True
                
                # Set up Deepgram connection
                self.setup_connection()
                
                # Configure transcription options
                options = LiveOptions(
                    model=DEEPGRAM_CONFIG['model'],
                    smart_format=DEEPGRAM_CONFIG['smart_format'],
                    language=DEEPGRAM_CONFIG['language'],
                    interim_results=DEEPGRAM_CONFIG['interim_results'],
                    encoding=DEEPGRAM_CONFIG['encoding'],
                    sample_rate=DEEPGRAM_CONFIG['sample_rate'],
                    channels=DEEPGRAM_CONFIG['channels'],
                    endpointing=DEEPGRAM_CONFIG['endpointing'],
                    utterance_end_ms=DEEPGRAM_CONFIG['utterance_end_ms']
                )
                
                # Start Deepgram connection
                if not self.dg_connection.start(options):
                    raise Exception("Failed to start Deepgram connection")
                
                # Start audio stream
                self.stream = sd.InputStream(
                    samplerate=AUDIO_CONFIG['sample_rate'],
                    channels=AUDIO_CONFIG['channels'],
                    blocksize=AUDIO_CONFIG['block_size'],
                    dtype='int16',  # Use int16 for Deepgram
                    callback=self.audio_callback
                )
                self.stream.start()
                print("Audio stream started")
                
                self.state_changed.emit(True)
                
            except Exception as e:
                print(f"Error starting STT: {str(e)}")
                self.stop()

    def stop(self):
        """Stop transcription."""
        if not self.is_listening:
            return
            
        print("Stopping STT...")
        self.is_listening = False
        
        # Stop and close audio stream
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
                
        # Close Deepgram connection
        if self.dg_connection:
            self.dg_connection.finish()
            self.dg_connection = None
        
        self.state_changed.emit(False)

    def toggle(self):
        """Toggle between listening and not listening states."""
        if not self.is_enabled:
            print("Cannot toggle: STT is disabled")
            return

        if self.is_listening:
            self.stop()
        else:
            self.start()

    def set_enabled(self, enabled: bool):
        """Enable or disable STT functionality."""
        if self.is_enabled == enabled:
            return

        print(f"Setting STT enabled: {enabled}")
        self.is_enabled = enabled
        self.enabled_changed.emit(enabled)

        if not enabled and self.is_listening:
            self.stop()

    def is_available(self) -> bool:
        """Check if STT is enabled and ready to use."""
        return self.is_enabled

    def __del__(self):
        """Cleanup when object is destroyed."""
        self.stop() 