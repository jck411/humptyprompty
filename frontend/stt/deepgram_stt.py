import os
import threading
import pyaudio
from queue import Queue
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from .base import BaseSTTProvider, STTState

# We can't import PyAudioSingleton directly in the frontend, so we'll implement a simple singleton pattern here
class PyAudioSingletonFrontend:
    _instance = None
    
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = pyaudio.PyAudio()
        return cls._instance

class DeepgramSTTProvider(BaseSTTProvider):
    def __init__(self, config):
        super().__init__(config)
        self._client = None
        self._connection = None
        self._audio_stream = None
        self._mic_thread = None
        self._is_running = False
        self._is_paused = False
        # Use the singleton pattern for PyAudio
        self._pyaudio = PyAudioSingletonFrontend.instance()
        self.setup_recognizer()

    def setup_recognizer(self) -> None:
        """Initialize the Deepgram client"""
        api_key = os.getenv("DEEPGRAM_API_KEY")
        if not api_key:
            raise ValueError("Missing DEEPGRAM_API_KEY in environment variables")
        self._client = DeepgramClient(api_key)
        self._state = STTState.READY

    def _start_listening_impl(self) -> None:
        """Start the Deepgram live transcription"""
        try:
            # If we're just resuming from pause, reuse existing resources when possible
            if self._is_paused and self._audio_stream and not self._connection:
                # Just create a new connection
                self._connection = self._client.listen.websocket.v("1")
                self._setup_event_handlers()
                
                options = LiveOptions(
                    model=self.config.settings.get("MODEL", "nova-2"),
                    smart_format=True,
                    language=self.config.settings.get("LANGUAGE", "en-US"),
                    interim_results=True,
                    encoding="linear16",
                    sample_rate=self.config.settings.get("SAMPLE_RATE", 16000),
                    channels=1,
                    endpointing=True,
                    utterance_end_ms=1000
                )
                if not self._connection.start(options):
                    raise RuntimeError("Failed to start Deepgram connection")
                
                # Resume the audio stream if it was paused
                if self._audio_stream and not self._audio_stream.is_active():
                    self._audio_stream.start_stream()
                
                self._is_running = True
                self._is_paused = False
                self._start_mic_thread()
                return
                
            # Full initialization if not resuming from pause
            if self._connection:
                return

            # Create a live transcription WebSocket connection (v1 interface)
            self._connection = self._client.listen.websocket.v("1")
            self._setup_event_handlers()
            
            options = LiveOptions(
                model=self.config.settings.get("MODEL", "nova-2"),
                smart_format=True,
                language=self.config.settings.get("LANGUAGE", "en-US"),
                interim_results=True,
                encoding="linear16",
                sample_rate=self.config.settings.get("SAMPLE_RATE", 16000),
                channels=1,
                endpointing=True,
                utterance_end_ms=1000
            )

            if not self._connection.start(options):
                raise RuntimeError("Failed to start Deepgram connection")

            self._setup_audio_stream()
            self._is_running = True
            self._is_paused = False
            self._start_mic_thread()

        except Exception as e:
            print(f"Error starting Deepgram transcription: {e}")
            self._state = STTState.ERROR
            raise

    def _setup_event_handlers(self):
        """Set up Deepgram event handlers"""
        # Handler for transcript events
        def on_transcript(client, result, **kwargs):
            if result and self.is_listening and self.config.enabled:
                # Handle both interim and final results
                alternatives = result.channel.alternatives
                if alternatives:
                    text = alternatives[0].transcript
                    if text:
                        if not result.is_final:
                            if self.config.settings.get("INTERIM_RESULTS", True):
                                self.speech_queue.put(f"(interim) {text}")
                        else:
                            self.speech_queue.put(f"[final] {text}")
        # Register all event handlers
        self._connection.on(
            LiveTranscriptionEvents.Open,
            lambda client, *args, **kwargs: print("Deepgram connection established")
        )
        self._connection.on(
            LiveTranscriptionEvents.Close,
            lambda client, *args, **kwargs: print("Deepgram connection closed")
        )
        self._connection.on(
            LiveTranscriptionEvents.Warning,
            lambda client, warning, **kwargs: print(f"Deepgram Warning: {warning}")
        )
        self._connection.on(
            LiveTranscriptionEvents.Error,
            lambda client, error, **kwargs: print(f"Deepgram Error: {error}")
        )
        self._connection.on(LiveTranscriptionEvents.Transcript, on_transcript)

    def _setup_audio_stream(self):
        """Initialize PyAudio stream"""
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = self.config.settings.get("SAMPLE_RATE", 16000)

        # Only create a new audio stream if we don't already have one
        if not self._audio_stream:
            self._audio_stream = self._pyaudio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )

    def _start_mic_thread(self):
        """Start microphone worker thread"""
        def mic_worker():
            try:
                while self._is_running:
                    if self._audio_stream and self._connection and not self._is_paused:
                        audio_data = self._audio_stream.read(1024, exception_on_overflow=False)
                        if audio_data and self._is_running:
                            self._connection.send(audio_data)
            except Exception as e:
                print(f"Microphone streaming error: {e}")
                self._state = STTState.ERROR

        self._mic_thread = threading.Thread(target=mic_worker, daemon=True)
        self._mic_thread.start()

    def _stop_listening_impl(self) -> None:
        """Stop the Deepgram live transcription"""
        self._is_running = False
        self._is_paused = False
        
        if self._connection:
            self._connection.finish()
            self._connection = None

        if self._audio_stream:
            self._audio_stream.stop_stream()
            self._audio_stream.close()
            self._audio_stream = None

        # Don't terminate PyAudio - we're using the singleton pattern
        
        if self._mic_thread:
            self._mic_thread.join(timeout=1)
            self._mic_thread = None

    def _pause_listening_impl(self) -> None:
        """Pause the Deepgram live transcription without fully terminating resources"""
        self._is_paused = True
        
        # Stop sending data but preserve the audio stream
        if self._connection:
            self._connection.finish()
            self._connection = None
            
        # Pause the audio stream but don't close it
        if self._audio_stream and self._audio_stream.is_active():
            self._audio_stream.stop_stream()
            
        # Mark as not running but keep the resources
        self._is_running = False
