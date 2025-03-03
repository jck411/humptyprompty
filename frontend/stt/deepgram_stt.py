#!/usr/bin/env python3
import os
import asyncio
import json
import sounddevice as sd
import logging
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from PyQt6.QtCore import QObject, pyqtSignal
from dotenv import load_dotenv
from .config import AUDIO_CONFIG, DEEPGRAM_CONFIG, STT_CONFIG

# Configure logging to show only warnings and errors
logging.basicConfig(level=logging.WARNING)

# Load environment variables
load_dotenv()

class DeepgramSTT(QObject):
    """
    Asynchronous frontend for Deepgram real-time STT with global enable/disable and pause/resume.
    
    - Global enable (set_enabled) opens/closes WebSocket and audio stream.
    - Pause (set_paused) stops sending mic audio while keeping the WebSocket open.
    
    Can be used as a context manager:
    ```
    with DeepgramSTT() as stt:
        # STT is automatically enabled here
        # Use stt as needed
    # STT is automatically disabled when exiting the context
    ```
    """

    # Signals for transcription results and state changes
    transcription_received = pyqtSignal(str)
    state_changed = pyqtSignal(bool)
    enabled_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.is_enabled = STT_CONFIG['enabled']  # Global STT toggle
        self.is_paused = False                   # Pause streaming toggle
        self.is_listening = False                # Connection active toggle

        # Keep-alive task reference (for paused state)
        self._keep_alive_task = None
        # Track the start/stop tasks
        self._start_task = None
        self._stop_task = None
        # Flag to track if we're in the process of toggling
        self._is_toggling = False

        # Capture the main event loop (set by qasync in the client)
        self.loop = asyncio.get_event_loop()

        # Initialize Deepgram client (API key from .env)
        api_key = os.getenv('DEEPGRAM_API_KEY')
        if not api_key:
            raise ValueError("Missing DEEPGRAM_API_KEY in environment variables")
        self.deepgram = DeepgramClient(api_key)
        self.dg_connection = None
        self.stream = None

        logging.debug("DeepgramSTT initialized with config: %s", DEEPGRAM_CONFIG)

        # Auto-start if configured
        if STT_CONFIG['auto_start'] and self.is_enabled:
            self.set_enabled(True)

    def setup_connection(self):
        """Setup WebSocket connection and register event handlers."""
        self.dg_connection = self.deepgram.listen.asyncwebsocket.v("1")

        async def on_open(client, *args, **kwargs):
            logging.debug("Deepgram connection established")
        self.dg_connection.on(LiveTranscriptionEvents.Open, on_open)

        async def on_close(client, *args, **kwargs):
            self._handle_close()
        self.dg_connection.on(LiveTranscriptionEvents.Close, on_close)

        async def on_warning(client, warning, **kwargs):
            logging.warning("Deepgram warning: %s", warning)
        self.dg_connection.on(LiveTranscriptionEvents.Warning, on_warning)

        async def on_error(client, error, **kwargs):
            self._handle_error(error)
        self.dg_connection.on(LiveTranscriptionEvents.Error, on_error)

        async def on_transcript(client, result, **kwargs):
            try:
                transcript = result.channel.alternatives[0].transcript
                if transcript.strip():
                    logging.debug("Transcript: %s", transcript)
                    self.transcription_received.emit(transcript)
            except Exception as e:
                logging.error("Error processing transcript: %s", str(e))
        self.dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript)

    def audio_callback(self, indata, frames, time, status):
        """Captures microphone audio and sends it to Deepgram unless paused."""
        if status:
            logging.warning("Audio callback status: %s", status)
            return

        if self.is_listening and self.is_enabled and not self.is_paused and self.dg_connection:
            try:
                # Convert float32 audio (range [-1, 1]) to int16 for "linear16" encoding if necessary
                if AUDIO_CONFIG['dtype'] == 'float32':
                    indata_int16 = (indata * 32767).astype('int16')
                else:
                    indata_int16 = indata
                logging.debug("Captured audio block: frames=%s, first sample=%s", 
                              frames, indata_int16[0][0] if frames > 0 else 'N/A')
                # Schedule sending the audio data on the main event loop
                self.loop.call_soon_threadsafe(
                    asyncio.create_task, self.dg_connection.send(indata_int16.tobytes())
                )
            except Exception as e:
                logging.error("Error in audio callback: %s", str(e))

    async def _async_start(self):
        """Starts STT asynchronously (opens WebSocket and audio stream)."""
        try:
            self.setup_connection()
            started = await self.dg_connection.start(LiveOptions(**DEEPGRAM_CONFIG))
            if not started:
                raise Exception("Failed to start Deepgram connection")

            self.stream = sd.InputStream(
                samplerate=AUDIO_CONFIG['sample_rate'],
                channels=AUDIO_CONFIG['channels'],
                blocksize=AUDIO_CONFIG['block_size'],
                dtype=AUDIO_CONFIG['dtype'],
                callback=self.audio_callback
            )
            self.stream.start()
            self.is_listening = True
            self.state_changed.emit(True)
            logging.debug("STT started")
        except Exception as e:
            logging.error("Error starting STT: %s", str(e))
            self.set_enabled(False)

    async def _async_stop(self):
        """Stops STT asynchronously (closes WebSocket and audio stream)."""
        try:
            # Cancel any pending keep-alive task first
            if self._keep_alive_task and not self._keep_alive_task.done():
                self._keep_alive_task.cancel()
                try:
                    await self._keep_alive_task
                except asyncio.CancelledError:
                    logging.debug("Keep-alive task cancelled during stop")
                self._keep_alive_task = None

            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None

            if self.dg_connection:
                try:
                    await self.dg_connection.finish()
                except asyncio.CancelledError:
                    logging.debug("Deepgram connection finish cancelled as expected.")
                except Exception as e:
                    logging.warning(f"Error during Deepgram connection finish: {e}")
                self.dg_connection = None

            self.is_listening = False
            self.state_changed.emit(False)
            logging.debug("STT stopped")
        except Exception as e:
            logging.error(f"Error stopping STT: {e}")
        finally:
            self._stop_task = None


    async def _keep_alive_loop(self, interval: float = 5.0):
        """Sends keep-alive messages while STT is paused."""
        logging.debug("Keep-alive loop started.")
        try:
            while self.is_paused and self.dg_connection:
                await self.dg_connection.send(json.dumps({"type": "KeepAlive"}))
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logging.debug("Keep-alive loop cancelled.")
        logging.debug("Keep-alive loop ended.")

    def set_enabled(self, enabled: bool):
        """Globally enable or disable STT."""
        if self.is_enabled == enabled or self._is_toggling:
            return
            
        self._is_toggling = True
        try:
            self.is_enabled = enabled
            self.enabled_changed.emit(enabled)
            
            # Cancel any existing tasks first
            if self._start_task and not self._start_task.done():
                self._start_task.cancel()
                self._start_task = None
                
            if self._stop_task and not self._stop_task.done():
                self._stop_task.cancel()
                self._stop_task = None
                
            if enabled:
                self._start_task = asyncio.create_task(self._async_start())
            else:
                # Cancel keep-alive task if it exists
                if self._keep_alive_task and not self._keep_alive_task.done():
                    self._keep_alive_task.cancel()
                    self._keep_alive_task = None
                    
                self._stop_task = asyncio.create_task(self._async_stop())
        finally:
            self._is_toggling = False

    def set_paused(self, paused: bool):
        """Pause or resume audio streaming (while keeping the WebSocket open)."""
        if self.is_paused == paused:
            return
        self.is_paused = paused
        if paused:
            if self._keep_alive_task is None:
                self._keep_alive_task = asyncio.create_task(self._keep_alive_loop())
        else:
            if self._keep_alive_task:
                self._keep_alive_task.cancel()
                self._keep_alive_task = None

    def _handle_error(self, error):
        logging.error("Deepgram error: %s", error)
        self.set_enabled(False)

    def _handle_close(self):
        logging.debug("Deepgram connection closed")
        self.set_enabled(False)

    def toggle(self):
        """Toggle between enabled and disabled states."""
        # Use set_enabled which now has proper task management
        self.set_enabled(not self.is_enabled)
        
    def __enter__(self):
        """Context manager entry - enables STT."""
        self.set_enabled(True)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - disables STT."""
        self.set_enabled(False)
        return False  # Don't suppress exceptions

    def __del__(self):
        self.set_enabled(False)
