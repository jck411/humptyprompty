#!/usr/bin/env python3
import os
import asyncio
import json
import sounddevice as sd
import logging
import threading
from queue import Queue

from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from PyQt6.QtCore import QObject, pyqtSignal
from dotenv import load_dotenv
from .config import AUDIO_CONFIG, DEEPGRAM_CONFIG, STT_CONFIG

logging.basicConfig(level=logging.WARNING)

load_dotenv()

class DeepgramSTT(QObject):
    transcription_received = pyqtSignal(str)
    state_changed = pyqtSignal(bool)
    enabled_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.is_enabled = STT_CONFIG['enabled']
        self.is_paused = False
        self.is_listening = False

        # Use a thread-safe queue for audio data
        self._audio_queue = Queue()

        # Create a dedicated event loop for Deepgram tasks and run it in a separate thread.
        self.dg_loop = asyncio.new_event_loop()
        self.dg_thread = threading.Thread(target=self._run_dg_loop, daemon=True)
        self.dg_thread.start()

        # Task references
        self._audio_consumer_task = None
        self._keep_alive_task = None
        self._start_task = None
        self._stop_task = None
        self._is_toggling = False

        # Initialize Deepgram client
        api_key = os.getenv('DEEPGRAM_API_KEY')
        if not api_key:
            raise ValueError("Missing DEEPGRAM_API_KEY in environment variables")
        self.deepgram = DeepgramClient(api_key)
        self.dg_connection = None
        self.stream = None

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
                    logging.debug("Transcript: %s", transcript)
                    self.transcription_received.emit(transcript)
            except Exception as e:
                logging.error("Error processing transcript: %s", str(e))
        self.dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript)

    def audio_callback(self, indata, frames, time, status):
        if status:
            logging.warning("Audio callback status: %s", status)
            return

        if self.is_listening and self.is_enabled and not self.is_paused:
            try:
                if AUDIO_CONFIG['dtype'] == 'float32':
                    indata_int16 = (indata * 32767).astype('int16')
                else:
                    indata_int16 = indata

                logging.debug("Captured audio block: frames=%s, first sample=%s", 
                              frames, indata_int16[0][0] if frames > 0 else 'N/A')
                # Put audio data into the thread-safe queue.
                self._audio_queue.put(indata_int16.tobytes())
            except Exception as e:
                logging.error("Error in audio callback: %s", str(e))

    async def stt_audio_consumer(self):
        # Helper to asynchronously get items from the thread-safe queue.
        async def async_get(q):
            return await asyncio.to_thread(q.get)
        
        try:
            while True:
                audio_chunk = await async_get(self._audio_queue)
                if self.dg_connection is not None and self.is_listening and not self.is_paused:
                    try:
                        await self.dg_connection.send(audio_chunk)
                    except Exception as e:
                        logging.error(f"Error sending chunk to Deepgram: {e}")
        except asyncio.CancelledError:
            logging.debug("Audio consumer task cancelled")
        except Exception as e:
            logging.error(f"Error in audio consumer: {e}")

    async def _async_start(self):
        try:
            self.setup_connection()
            started = await self.dg_connection.start(LiveOptions(**DEEPGRAM_CONFIG))
            if not started:
                raise Exception("Failed to start Deepgram connection")

            if self._audio_consumer_task is None or self._audio_consumer_task.done():
                self._audio_consumer_task = asyncio.create_task(self.stt_audio_consumer())

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
        try:
            if self._keep_alive_task and not self._keep_alive_task.done():
                self._keep_alive_task.cancel()
                try:
                    await self._keep_alive_task
                except asyncio.CancelledError:
                    logging.debug("Keep-alive task cancelled during stop")
                self._keep_alive_task = None

            if self._audio_consumer_task and not self._audio_consumer_task.done():
                self._audio_consumer_task.cancel()
                try:
                    await self._audio_consumer_task
                except asyncio.CancelledError:
                    logging.debug("Audio consumer task cancelled during stop")
                self._audio_consumer_task = None

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
        logging.debug("Keep-alive loop started.")
        try:
            while self.is_paused and self.dg_connection:
                await self.dg_connection.send(json.dumps({"type": "KeepAlive"}))
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logging.debug("Keep-alive loop cancelled.")
        logging.debug("Keep-alive loop ended.")

    def set_enabled(self, enabled: bool):
        if self.is_enabled == enabled or self._is_toggling:
            return
        self._is_toggling = True
        try:
            self.is_enabled = enabled
            self.enabled_changed.emit(enabled)
            if self._start_task and not self._start_task.done():
                self._start_task.cancel()
                self._start_task = None
            if self._stop_task and not self._stop_task.done():
                self._stop_task.cancel()
                self._stop_task = None
            if enabled:
                self._start_task = asyncio.run_coroutine_threadsafe(self._async_start(), self.dg_loop)
            else:
                if self._keep_alive_task and not self._keep_alive_task.done():
                    self._keep_alive_task.cancel()
                    self._keep_alive_task = None
                self._stop_task = asyncio.run_coroutine_threadsafe(self._async_stop(), self.dg_loop)
        finally:
            self._is_toggling = False

    def set_paused(self, paused: bool):
        if self.is_paused == paused:
            return
        self.is_paused = paused
        if paused:
            if self._keep_alive_task is None:
                self._keep_alive_task = asyncio.run_coroutine_threadsafe(self._keep_alive_loop(), self.dg_loop)
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
        self.set_enabled(not self.is_enabled)

    def stop(self):
        if self._start_task and not self._start_task.done():
            self._start_task.cancel()
            self._start_task = None
        if self._stop_task and not self._stop_task.done():
            self._stop_task.cancel()
            self._stop_task = None
        self._stop_task = asyncio.run_coroutine_threadsafe(self._async_stop(), self.dg_loop)
        self.is_listening = False
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
