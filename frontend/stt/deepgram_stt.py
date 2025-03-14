#!/usr/bin/env python3
import os
import asyncio
import json
import logging
import threading
import time
from queue import Queue
from signal import SIGINT, SIGTERM
import concurrent.futures

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
    state_changed = pyqtSignal(bool)  # is_listening
    enabled_changed = pyqtSignal(bool)  # is_enabled

    def __init__(self):
        super().__init__()
        self.is_enabled = STT_CONFIG['enabled']
        self.is_paused = False
        self.is_finals = []
        self.keepalive_active = False
        
        # Get keepalive settings from Deepgram config
        self.keepalive_enabled = DEEPGRAM_CONFIG.get('keepalive', {}).get('enabled', False)
        self.keepalive_timeout = DEEPGRAM_CONFIG.get('keepalive', {}).get('timeout', 10)  # seconds
        self.last_activity_time = time.time()
        self.timeout_timer = None

        # Create a dedicated event loop for Deepgram tasks and run it in a separate thread.
        self.dg_loop = asyncio.new_event_loop()
        self.dg_thread = threading.Thread(target=self._run_dg_loop, daemon=True)
        self.dg_thread.start()

        # Task references
        self._start_task = None
        self._stop_task = None
        self._is_toggling = False
        self._keepalive_task = None

        # Initialize Deepgram client
        api_key = os.getenv('DEEPGRAM_API_KEY')
        if not api_key:
            raise ValueError("Missing DEEPGRAM_API_KEY in environment variables")
        
        # Initialize with client options directly from Deepgram config
        keepalive_config = {}
        if self.keepalive_enabled:
            keepalive_config["keepalive"] = "true"
            keepalive_config["keepalive_timeout"] = str(self.keepalive_timeout)
        
        config = DeepgramClientOptions(options=keepalive_config)
        self.deepgram = DeepgramClient(api_key, config)
        self.dg_connection = None
        self.microphone = None

        logging.debug("DeepgramSTT initialized with config: %s", DEEPGRAM_CONFIG)
        logging.debug("KeepAlive settings from Deepgram config: enabled=%s, timeout=%s seconds", 
                     self.keepalive_enabled,
                     self.keepalive_timeout)

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

                # Only reset timer if there's actual speech content
                # We'll consider two conditions for activity:
                # 1. There's an actual transcript with content
                # 2. There's a speech_started event that's explicitly true
                has_speech_content = transcript and transcript.strip()
                is_speech_starting = hasattr(result, 'speech_started') and result.speech_started
                
                if has_speech_content or is_speech_starting:
                    self._reset_activity_timer()
                    
                    # Log the reason for the reset
                    if has_speech_content:
                        # Fix the string formatting
                        transcript_preview = transcript[:20] + "..." if len(transcript) > 20 else transcript
                        logging.info(f"Activity timer reset due to speech content: '{transcript_preview}'")
                    elif is_speech_starting:
                        logging.info("Activity timer reset due to speech_started event")
                
                # Continue with normal processing
                if has_speech_content:
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
                elif hasattr(result, 'speech_started') and result.speech_started:
                    logging.info("[SPEECH EVENT] Speech segment started")
                    
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
            
            # Ensure the activity timer is freshly reset and started
            # This ensures we have a clean slate for timing speech activity
            self.last_activity_time = time.time()  # Direct assignment for certainty
            self._cancel_keepalive_timer()  # Cancel any existing timer first
            
            # Explicitly log the timeout that will be used
            logging.info(f"STT started with keepalive timeout of {self.keepalive_timeout} seconds")
            
            # Start the keepalive timer with a fresh timer task
            self.timeout_timer = asyncio.run_coroutine_threadsafe(
                self._check_keepalive_timeout(), self.dg_loop
            )
            
            self.state_changed.emit(self.is_enabled)
            logging.debug("STT started")
        except Exception as e:
            logging.error("Error starting STT: %s", str(e))
            self.set_enabled(False)

    async def _async_stop(self):
        try:
            # Cancel the keepalive timer
            self._cancel_keepalive_timer()
            
            # Ensure keepalive is deactivated
            self.keepalive_active = False
            
            if self._keepalive_task and not self._keepalive_task.done():
                self._keepalive_task.cancel()
                try:
                    # Wait for the task to be cancelled properly
                    await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(
                        self._keepalive_task, self.dg_loop
                    ))
                except (asyncio.CancelledError, concurrent.futures.CancelledError):
                    # This is expected when cancelling tasks
                    pass
                self._keepalive_task = None
                
            if self.microphone:
                self.microphone.finish()
                self.microphone = None

            if self.dg_connection:
                try:
                    # Add a small delay to ensure microphone is fully stopped
                    await asyncio.sleep(0.1)
                    await self.dg_connection.finish()
                except asyncio.CancelledError:
                    logging.debug("Deepgram connection finish cancelled as expected.")
                except Exception as e:
                    logging.warning(f"Error during Deepgram connection finish: {e}")
                finally:
                    # Ensure we clear the connection reference even if there was an error
                    self.dg_connection = None

            self.state_changed.emit(self.is_enabled)
            logging.debug("STT stopped")
        except asyncio.CancelledError:
            logging.debug("STT stop operation was cancelled")
            # Still clean up resources even if cancelled
            if self.microphone:
                self.microphone.finish()
                self.microphone = None
            if self.dg_connection:
                self.dg_connection = None
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
        """
        Pause or resume the STT microphone input.
        When paused with keepalive=true, the connection stays open but no audio is sent.
        """
        if self.is_paused == paused:
            return
            
        self.is_paused = paused
        
        # Only handle keepalive if STT is globally enabled
        if not self.is_enabled:
            return
            
        # Emit state changed to update UI
        self.state_changed.emit(not paused)
        
        # When unpausing (resuming), reset the activity timer to give a fresh timeout period
        if not paused:
            self.last_activity_time = time.time()
            logging.info(f"Resuming from pause state - reset activity timer (timeout in {self.keepalive_timeout} seconds)")
            
        # Use the appropriate method based on whether we're pausing or resuming
        if self.dg_connection:
            if paused:
                if self.keepalive_enabled:
                    self._activate_keepalive()
                else:
                    # If not using keepalive, we'll just stop the microphone
                    if self.microphone:
                        self.microphone.finish()
                        self.microphone = None
            else:
                if self.keepalive_enabled and self.keepalive_active:
                    self._deactivate_keepalive()
                else:
                    # If not using keepalive or not active, restart the microphone
                    if not self.microphone and self.dg_connection:
                        self.microphone = Microphone(self.dg_connection.send)
                        self.microphone.start()
                
    def _activate_keepalive(self):
        """
        Activate keepalive mode - stop the microphone but keep the connection open
        by sending KeepAlive messages.
        """
        if self.keepalive_active:
            return
            
        logging.debug("Activating Deepgram KeepAlive mode")
        
        # Stop the microphone to prevent sending audio data
        if self.microphone:
            self.microphone.finish()
            self.microphone = None
            
        self.keepalive_active = True
        
        # Emit state changed to update UI - not actively listening when in keepalive mode
        self.state_changed.emit(False)
        
        # Cancel any existing keepalive task
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
            
        # Start a task to send KeepAlive messages periodically
        self._keepalive_task = asyncio.run_coroutine_threadsafe(
            self._send_keepalive_messages(), 
            self.dg_loop
        )
        
    async def _send_keepalive_messages(self):
        """
        Send KeepAlive messages periodically to keep the connection open.
        """
        try:
            # Send KeepAlive messages at half the keepalive_timeout rate to ensure
            # the connection stays alive while respecting the same timeout value
            interval = max(1, self.keepalive_timeout / 2)  # minimum of 1 second, default would be 2.5s for 5s timeout
            logging.debug(f"Starting KeepAlive message loop with {interval}s interval (based on keepalive_timeout: {self.keepalive_timeout}s)")
            
            while self.keepalive_active and self.dg_connection:
                try:
                    # Send the KeepAlive message as JSON
                    keepalive_msg = {"type": "KeepAlive"}
                    await self.dg_connection.send(json.dumps(keepalive_msg))
                    logging.debug("Sent KeepAlive message")
                except Exception as e:
                    logging.error(f"Error sending KeepAlive message: {e}")
                    
                # Wait before sending the next message
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            logging.debug("KeepAlive message loop cancelled")
        except Exception as e:
            logging.error(f"Error in KeepAlive message loop: {e}")
            
    def _deactivate_keepalive(self):
        """
        Deactivate keepalive mode - restart the microphone.
        """
        if not self.keepalive_active:
            return
            
        logging.debug("Deactivating Deepgram KeepAlive mode")
        
        # Cancel the keepalive task
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
            self._keepalive_task = None
            
        # Restart the microphone
        if not self.microphone and self.dg_connection:
            self.microphone = Microphone(self.dg_connection.send)
            self.microphone.start()
            
        self.keepalive_active = False
        
        # Emit state changed to update UI - actively listening when not in keepalive mode
        self.state_changed.emit(True)

    def _handle_error(self, error):
        logging.error("Deepgram error: %s", error)
        self.set_enabled(False)

    def _handle_close(self):
        logging.debug("Deepgram connection closed")
        self.set_enabled(False)

    def toggle(self):
        try:
            self.set_enabled(not self.is_enabled)
        except Exception as e:
            logging.error(f"Error toggling STT: {e}")
            # Ensure UI is updated even if there's an error
            self.state_changed.emit(self.is_enabled)

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
        # Ensure keepalive is deactivated
        self.keepalive_active = False
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
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

    # Keepalive timeout methods
    def _reset_activity_timer(self):
        """Reset the keepalive timer by updating the last activity timestamp"""
        current_time = time.time()
        
        # Avoid excessive resets - only update if at least 0.5 seconds have passed
        # This prevents constant updates from Deepgram events
        if (current_time - self.last_activity_time) > 0.5:
            self.last_activity_time = current_time
            logging.info(f"Activity timer reset - will timeout in {self.keepalive_timeout} seconds if no speech detected")
        # Otherwise, silently ignore the reset

    def _start_keepalive_timer(self):
        """Start the keepalive timeout timer"""
        self._cancel_keepalive_timer()  # Cancel any existing timer first
        self.timeout_timer = asyncio.run_coroutine_threadsafe(
            self._check_keepalive_timeout(), self.dg_loop
        )
        logging.info(f"Keepalive timer started with timeout of {self.keepalive_timeout} seconds")
        
    def _cancel_keepalive_timer(self):
        """Cancel the keepalive timeout timer if it exists"""
        if self.timeout_timer and not self.timeout_timer.done():
            self.timeout_timer.cancel()
            self.timeout_timer = None
            logging.info("Keepalive timer cancelled")
            
    async def _check_keepalive_timeout(self):
        """Check for inactivity and turn off STT if keepalive threshold is exceeded"""
        try:
            logging.info(f"Starting keepalive check loop with timeout of {self.keepalive_timeout} seconds")
            check_interval = 0.5  # Check more frequently (twice per second)
            last_log_time = 0
            
            while self.is_enabled:
                # Only check for timeout if not paused - don't count down when TTS is playing
                if not self.is_paused:
                    # Check if we've exceeded the keepalive timeout
                    current_time = time.time()
                    time_since_last_activity = current_time - self.last_activity_time
                    
                    # Log progress at most once every 5 seconds to avoid log spam
                    if current_time - last_log_time >= 5:
                        logging.info(f"Keepalive timer: {time_since_last_activity:.1f}/{self.keepalive_timeout} seconds passed")
                        last_log_time = current_time
                    
                    # Use a very strict comparison to ensure we timeout exactly on time
                    if time_since_last_activity >= self.keepalive_timeout:
                        logging.info(f"TIMEOUT REACHED: No activity detected for {time_since_last_activity:.1f} seconds (threshold: {self.keepalive_timeout})")
                        # Directly disable rather than scheduling it to ensure immediate action
                        self.is_enabled = False  # Set flag immediately for other check loops
                        await self._disable_on_timeout()
                        break
                else:
                    # If we're paused, just log less frequently to confirm we're not counting down
                    current_time = time.time()
                    if current_time - last_log_time >= 10:  # Log less frequently when paused
                        logging.debug("Keepalive timer paused while system is in pause state (e.g., during TTS playback)")
                        last_log_time = current_time
                
                # Sleep for a short time to avoid high CPU usage
                await asyncio.sleep(check_interval)
        except asyncio.CancelledError:
            # This is expected if the timer is cancelled
            logging.debug("Keepalive check task cancelled")
        except Exception as e:
            logging.error(f"Error in keepalive check: {e}")
            
    async def _disable_on_timeout(self):
        """Disable STT due to timeout - separated to ensure clean execution"""
        try:
            logging.info("Disabling STT due to keepalive timeout")
            # Use set_enabled but protect against recursive calls
            if self.is_enabled:  # This should be false already, but double-check
                self.set_enabled(False)
            else:
                # Just ensure we clean up resources
                self._stop_task = asyncio.run_coroutine_threadsafe(self._async_stop(), self.dg_loop)
                self.enabled_changed.emit(False)
                self.state_changed.emit(False)
        except Exception as e:
            logging.error(f"Error disabling STT on timeout: {e}")
