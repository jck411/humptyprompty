#!/usr/bin/env python3
import os
import asyncio
import json
import logging
import threading
from queue import Queue
from signal import SIGINT, SIGTERM

from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
    Microphone
)
from PyQt6.QtCore import QObject, pyqtSignal
from dotenv import load_dotenv
from .config import AUDIO_CONFIG, DEEPGRAM_CONFIG, STT_CONFIG

logging.basicConfig(level=logging.INFO)

load_dotenv()

class DeepgramSTT(QObject):
    transcription_received = pyqtSignal(str)
    complete_utterance_received = pyqtSignal(str)
    state_changed = pyqtSignal(bool)
    enabled_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.is_enabled = STT_CONFIG['enabled']
        self.is_paused = False
        self.is_finals = []

        # Create a dedicated event loop for Deepgram tasks and run it in a separate thread.
        self.dg_loop = asyncio.new_event_loop()
        self.dg_thread = threading.Thread(target=self._run_dg_loop, daemon=True)
        self.dg_thread.start()

        # Task references
        self._start_task = None
        self._stop_task = None
        self._is_toggling = False

        # Initialize Deepgram client
        api_key = os.getenv('DEEPGRAM_API_KEY')
        if not api_key:
            raise ValueError("Missing DEEPGRAM_API_KEY in environment variables")
        
        # Initialize with new client options
        config = DeepgramClientOptions(options={"keepalive": "true"})
        self.deepgram = DeepgramClient(api_key, config)
        self.dg_connection = None
        self.microphone = None

        logging.debug("DeepgramSTT initialized with config: %s", DEEPGRAM_CONFIG)

        if STT_CONFIG['auto_start'] and self.is_enabled:
            self.set_enabled(True)

    def _run_dg_loop(self):
        asyncio.set_event_loop(self.dg_loop)
        self.dg_loop.run_forever()

    def setup_connection(self):
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
                    # Add clear labels to distinguish between interim and final transcripts
                    if result.is_final:
                        confidence = result.channel.alternatives[0].confidence if hasattr(result.channel.alternatives[0], 'confidence') else 'N/A'
                        logging.info("[FINAL TRANSCRIPT] %s (Confidence: %s)", transcript, confidence)
                    else:
                        logging.info("[INTERIM TRANSCRIPT] %s", transcript)
                    
                    self.transcription_received.emit(transcript)
                    
                    # Handle final transcripts
                    if result.is_final and transcript:
                        self.is_finals.append(transcript)
                        
                # Log speech events if available
                if hasattr(result, 'speech_final') and result.speech_final:
                    logging.info("[SPEECH EVENT] Speech segment ended")
                    
            except Exception as e:
                logging.error("Error processing transcript: %s", str(e))
        self.dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript)
        
        async def on_utterance_end(client, *args, **kwargs):
            if self.is_finals:
                utterance = " ".join(self.is_finals)
                logging.info("[COMPLETE UTTERANCE] %s", utterance)
                logging.info("[UTTERANCE INFO] Segments combined: %d", len(self.is_finals))
                self.complete_utterance_received.emit(utterance)
                self.is_finals = []
            else:
                logging.info("[UTTERANCE END] No final segments to combine")
        self.dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)

    async def _async_start(self):
        try:
            self.setup_connection()
            
            # Configure transcription options with updated parameters
            options = LiveOptions(
                model=DEEPGRAM_CONFIG.get('model', 'nova-3'),
                language=DEEPGRAM_CONFIG.get('language', 'en-US'),
                smart_format=DEEPGRAM_CONFIG.get('smart_format', True),
                encoding=DEEPGRAM_CONFIG.get('encoding', 'linear16'),
                channels=DEEPGRAM_CONFIG.get('channels', 1),
                sample_rate=DEEPGRAM_CONFIG.get('sample_rate', 16000),
                interim_results=DEEPGRAM_CONFIG.get('interim_results', True),
                utterance_end_ms="1000",
                vad_events=DEEPGRAM_CONFIG.get('vad_events', True),
                endpointing=DEEPGRAM_CONFIG.get('endpointing', 300),
            )
            
            started = await self.dg_connection.start(options)
            if not started:
                raise Exception("Failed to start Deepgram connection")

            # Use the new Microphone class instead of sounddevice
            self.microphone = Microphone(self.dg_connection.send)
            self.microphone.start()
            
            self.state_changed.emit(self.is_enabled)
            logging.debug("STT started")
        except Exception as e:
            logging.error("Error starting STT: %s", str(e))
            self.set_enabled(False)

    async def _async_stop(self):
        try:
            if self.microphone:
                self.microphone.finish()
                self.microphone = None

            if self.dg_connection:
                try:
                    await self.dg_connection.finish()
                except asyncio.CancelledError:
                    logging.debug("Deepgram connection finish cancelled as expected.")
                except Exception as e:
                    logging.warning(f"Error during Deepgram connection finish: {e}")
                self.dg_connection = None

            self.state_changed.emit(self.is_enabled)
            logging.debug("STT stopped")
        except Exception as e:
            logging.error(f"Error stopping STT: {e}")
        finally:
            self._stop_task = None

    def set_enabled(self, enabled: bool):
        if self.is_enabled == enabled or self._is_toggling:
            return
        self._is_toggling = True
        try:
            self.is_enabled = enabled
            self.enabled_changed.emit(enabled)
            self.state_changed.emit(enabled)
            
            if self._start_task and not self._start_task.done():
                self._start_task.cancel()
                self._start_task = None
            if self._stop_task and not self._stop_task.done():
                self._stop_task.cancel()
                self._stop_task = None
            if enabled:
                self._start_task = asyncio.run_coroutine_threadsafe(self._async_start(), self.dg_loop)
            else:
                self._stop_task = asyncio.run_coroutine_threadsafe(self._async_stop(), self.dg_loop)
        finally:
            self._is_toggling = False

    def set_paused(self, paused: bool):
        if self.is_paused == paused:
            return
        self.is_paused = paused
        # Pausing is handled differently with the Microphone class
        if self.microphone:
            if paused:
                self.microphone.pause()
            else:
                self.microphone.resume()

    def _handle_error(self, error):
        logging.error("Deepgram error: %s", error)
        self.set_enabled(False)

    def _handle_close(self):
        logging.debug("Deepgram connection closed")
        self.set_enabled(False)

    def toggle(self):
        self.set_enabled(not self.is_enabled)

    def stop(self):
        if self._start_task and not self._start_task.done():
            self._start_task.cancel()
            self._start_task = None
        if self._stop_task and not self._stop_task.done():
            self._stop_task.cancel()
            self._stop_task = None
        self._stop_task = asyncio.run_coroutine_threadsafe(self._async_stop(), self.dg_loop)
        self.is_enabled = False
        self.is_paused = False
        self.state_changed.emit(False)
        self.enabled_changed.emit(False)
        logging.debug("STT stop initiated (fire and forget)")

    async def stop_async(self):
        if self._start_task and not self._start_task.done():
            self._start_task.cancel()
            self._start_task = None
        if self._stop_task and not self._stop_task.done():
            self._stop_task.cancel()
            self._stop_task = None
        self._stop_task = asyncio.run_coroutine_threadsafe(self._async_stop(), self.dg_loop)
        self._stop_task.result()
        self.is_enabled = False
        self.is_paused = False
        self.enabled_changed.emit(False)
        logging.debug("STT fully stopped and cleaned up (async)")

    def __enter__(self):
        self.set_enabled(True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.set_enabled(False)
        return False

    def __del__(self):
        self.set_enabled(False)

    async def shutdown(self, signal, loop):
        """Gracefully shutdown the Deepgram connection"""
        logging.debug(f"Received exit signal {signal.name if hasattr(signal, 'name') else signal}...")
        if self.microphone:
            self.microphone.finish()
        if self.dg_connection:
            await self.dg_connection.finish()
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        [task.cancel() for task in tasks]
        await asyncio.gather(*tasks, return_exceptions=True)
        loop.stop()
