#!/usr/bin/env python3
import os
import asyncio
import json
import threading
import concurrent.futures
from typing import Optional, List, Dict, Any

from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
    Microphone
)
from PySide6.QtCore import QObject, Signal, QTimer
from dotenv import load_dotenv
from frontend.config import logger
from .config import AUDIO_CONFIG, DEEPGRAM_CONFIG, STT_CONFIG

load_dotenv()

class DeepgramSTT(QObject):
    """
    Speech-to-Text implementation using Deepgram's API.
    
    Handles microphone input, streaming to Deepgram's API, and processing
    transcription results.
    """
    # Signals
    transcription_received = Signal(str)
    complete_utterance_received = Signal(str)
    state_changed = Signal(bool)
    enabled_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        # State tracking
        self.is_enabled = STT_CONFIG['enabled']
        self.is_paused = False
        self.is_finals: List[str] = []
        self.keepalive_active = False
        self.use_keepalive = STT_CONFIG.get('use_keepalive', True)
        self._is_toggling = False

        # Create a dedicated event loop for Deepgram tasks
        self.dg_loop = asyncio.new_event_loop()
        self.dg_thread = threading.Thread(target=self._run_dg_loop, daemon=True)
        self.dg_thread.start()

        # Task references
        self._start_task: Optional[concurrent.futures.Future] = None
        self._stop_task: Optional[concurrent.futures.Future] = None
        self._keepalive_task: Optional[concurrent.futures.Future] = None
        
        # Reconnection timer
        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.timeout.connect(self._reconnect_timeout)
        self.reconnect_timer.setSingleShot(True)

        # Initialize Deepgram client
        api_key = os.getenv('DEEPGRAM_API_KEY')
        if not api_key:
            raise ValueError("Missing DEEPGRAM_API_KEY in environment variables")
        
        # Initialize with client options
        keepalive_config: Dict[str, str] = {"keepalive": "true"}
        if DEEPGRAM_CONFIG.get('keepalive_timeout'):
            keepalive_config["keepalive_timeout"] = str(DEEPGRAM_CONFIG.get('keepalive_timeout'))
        
        config = DeepgramClientOptions(options=keepalive_config)
        self.deepgram = DeepgramClient(api_key, config)
        self.dg_connection = None
        self.microphone = None

        logger.info("DeepgramSTT initialized")
        logger.debug(f"STT config: {STT_CONFIG}")
        logger.debug(f"Deepgram config: {DEEPGRAM_CONFIG}")

        # Initialize STT based on the enabled setting
        if STT_CONFIG['enabled']:
            # If enabled is True in config, start STT
            logger.info("Starting STT (enabled=True in config)")
            # Ensure the internal state is correct
            self.is_enabled = True
            # Start the service directly
            self._is_toggling = False  # Ensure no toggle lock
            self._start_task = asyncio.run_coroutine_threadsafe(self._async_start(), self.dg_loop)
        else:
            # If enabled is False in config, initialize with it off
            logger.info("Initializing STT with enabled=False")
            self.is_enabled = False

    def _run_dg_loop(self):
        """Run the asyncio event loop in a separate thread"""
        asyncio.set_event_loop(self.dg_loop)
        self.dg_loop.run_forever()

    def _reconnect_timeout(self):
        """Handle reconnection timer timeout"""
        if not self.is_enabled:
            return
            
        logger.info("Attempting to reconnect STT service")
        self.set_enabled(True)

    def setup_connection(self):
        """Set up the Deepgram WebSocket connection and event handlers"""
        self.dg_connection = self.deepgram.listen.asyncwebsocket.v("1")

        # Connection opened
        async def on_open(client, *args, **kwargs):
            logger.info("Deepgram connection established")
        self.dg_connection.on(LiveTranscriptionEvents.Open, on_open)

        # Connection closed
        async def on_close(client, *args, **kwargs):
            logger.info("Deepgram connection closed")
            self._handle_close()
        self.dg_connection.on(LiveTranscriptionEvents.Close, on_close)

        # Warning received
        async def on_warning(client, warning, **kwargs):
            logger.warning(f"Deepgram warning: {warning}")
        self.dg_connection.on(LiveTranscriptionEvents.Warning, on_warning)

        # Error received
        async def on_error(client, error, **kwargs):
            logger.error(f"Deepgram error: {error}")
            self._handle_error(error)
        self.dg_connection.on(LiveTranscriptionEvents.Error, on_error)

        # Transcript received
        async def on_transcript(client, result, **kwargs):
            try:
                transcript = result.channel.alternatives[0].transcript
                if transcript.strip():
                    # Log transcript with appropriate label
                    if result.is_final:
                        confidence = getattr(result.channel.alternatives[0], 'confidence', 'N/A')
                        logger.info(f"[FINAL] {transcript} (Confidence: {confidence})")
                        
                        # Store final transcripts for utterance completion
                        self.is_finals.append(transcript)
                    else:
                        logger.debug(f"[INTERIM] {transcript}")
                    
                    # Emit signal with transcript
                    self.transcription_received.emit(transcript)
                    
                # Log speech events if available
                if hasattr(result, 'speech_final') and result.speech_final:
                    logger.debug("Speech segment ended")
                    
            except Exception as e:
                logger.error(f"Error processing transcript: {e}")
        self.dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript)
        
        # Utterance end received
        async def on_utterance_end(client, *args, **kwargs):
            if self.is_finals:
                utterance = " ".join(self.is_finals)
                logger.info(f"Complete utterance: '{utterance}' (segments: {len(self.is_finals)})")
                self.complete_utterance_received.emit(utterance)
                self.is_finals = []
            else:
                logger.debug("Utterance ended with no final segments")
        self.dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)

    async def _async_start(self):
        """Start the STT service asynchronously"""
        try:
            # Set up connection and event handlers
            self.setup_connection()
            
            # Configure transcription options
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
            
            # Start the connection
            started = await self.dg_connection.start(options)
            if not started:
                raise Exception("Failed to start Deepgram connection")

            # Start the microphone
            self.microphone = Microphone(self.dg_connection.send)
            self.microphone.start()
            
            # Emit state change signal
            self.state_changed.emit(self.is_enabled)
            logger.info("STT started successfully")
        except Exception as e:
            logger.error(f"Error starting STT: {e}")
            self.set_enabled(False)

    async def _async_stop(self):
        """Stop the STT service asynchronously"""
        try:
            # Deactivate keepalive if active
            self.keepalive_active = False
            
            # Cancel keepalive task if running
            if self._keepalive_task and not self._keepalive_task.done():
                self._keepalive_task.cancel()
                try:
                    await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(
                        asyncio.sleep(0), self.dg_loop
                    ))
                except (asyncio.CancelledError, concurrent.futures.CancelledError):
                    pass
                self._keepalive_task = None
                
            # Stop microphone if running
            if self.microphone:
                self.microphone.finish()
                self.microphone = None

            # Close Deepgram connection if open
            if self.dg_connection:
                try:
                    # Small delay to ensure microphone is fully stopped
                    await asyncio.sleep(0.1)
                    await self.dg_connection.finish()
                except asyncio.CancelledError:
                    logger.debug("Connection finish cancelled")
                except Exception as e:
                    logger.warning(f"Error during connection finish: {e}")
                finally:
                    self.dg_connection = None

            # Emit state change signal
            self.state_changed.emit(self.is_enabled)
            logger.info("STT stopped successfully")
        except asyncio.CancelledError:
            logger.debug("STT stop operation cancelled")
            # Clean up resources even if cancelled
            if self.microphone:
                self.microphone.finish()
                self.microphone = None
            if self.dg_connection:
                self.dg_connection = None
        except Exception as e:
            logger.error(f"Error stopping STT: {e}")
        finally:
            self._stop_task = None

    def set_enabled(self, enabled: bool):
        """Enable or disable STT"""
        if self.is_enabled == enabled or self._is_toggling:
            return
            
        self._is_toggling = True
        try:
            self.is_enabled = enabled
            self.enabled_changed.emit(enabled)
            self.state_changed.emit(enabled)
            
            # Cancel any pending tasks
            if self._start_task and not self._start_task.done():
                self._start_task.cancel()
                self._start_task = None
            if self._stop_task and not self._stop_task.done():
                self._stop_task.cancel()
                self._stop_task = None
                
            # Start or stop based on new state
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
        logger.info(f"STT paused state set to: {paused}")
        
        # Only handle if STT is globally enabled
        if not self.is_enabled or not self.dg_connection:
            return
            
        # Handle pause/resume based on keepalive setting
        if paused:
            if self.use_keepalive:
                self._activate_keepalive()
            elif self.microphone:
                self.microphone.finish()
                self.microphone = None
        else:
            if self.use_keepalive and self.keepalive_active:
                self._deactivate_keepalive()
            elif not self.microphone and self.dg_connection:
                self.microphone = Microphone(self.dg_connection.send)
                self.microphone.start()
                
    def _activate_keepalive(self):
        """Activate keepalive mode - stop microphone but keep connection open"""
        if self.keepalive_active:
            return
            
        logger.info("Activating Deepgram KeepAlive mode")
        
        # Stop the microphone
        if self.microphone:
            self.microphone.finish()
            self.microphone = None
            
        self.keepalive_active = True
        
        # Cancel existing keepalive task if any
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
            
        # Start keepalive message task
        self._keepalive_task = asyncio.run_coroutine_threadsafe(
            self._send_keepalive_messages(), 
            self.dg_loop
        )
        
    async def _send_keepalive_messages(self):
        """Send periodic keepalive messages to maintain connection"""
        try:
            # Send messages every 5 seconds (half the default timeout)
            interval = 5
            logger.debug(f"Starting KeepAlive message loop ({interval}s interval)")
            
            while self.keepalive_active and self.dg_connection:
                try:
                    keepalive_msg = {"type": "KeepAlive"}
                    await self.dg_connection.send(json.dumps(keepalive_msg))
                    logger.debug("Sent KeepAlive message")
                except Exception as e:
                    logger.error(f"Error sending KeepAlive message: {e}")
                    
                # Wait before next message
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            logger.debug("KeepAlive message loop cancelled")
        except Exception as e:
            logger.error(f"Error in KeepAlive message loop: {e}")
            
    def _deactivate_keepalive(self):
        """Deactivate keepalive mode and restart microphone"""
        if not self.keepalive_active:
            return
            
        logger.info("Deactivating Deepgram KeepAlive mode")
        
        # Cancel keepalive task
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
            self._keepalive_task = None
            
        # Restart the microphone
        if not self.microphone and self.dg_connection:
            self.microphone = Microphone(self.dg_connection.send)
            self.microphone.start()
            
        self.keepalive_active = False

    def _handle_error(self, error):
        """Handle Deepgram errors"""
        logger.error(f"Deepgram error: {error}")
        self.set_enabled(False)
        
        # Try to reconnect after a delay
        if not self.reconnect_timer.isActive():
            self.reconnect_timer.start(5000)  # 5 second delay

    def _handle_close(self):
        """Handle Deepgram connection close"""
        logger.info("Deepgram connection closed")
        self.set_enabled(False)
        
        # Try to reconnect after a delay if it was enabled
        if self.is_enabled and not self.reconnect_timer.isActive():
            self.reconnect_timer.start(5000)  # 5 second delay

    def toggle(self):
        """Toggle STT enabled state"""
        try:
            # Get current state and explicitly set to the opposite
            current_state = self.is_enabled
            new_state = not current_state
            
            # Force toggling even if there's a pending operation
            self._is_toggling = False
            
            # Set the new state
            self.set_enabled(new_state)
            logger.info(f"STT toggle requested: {current_state} -> {new_state}")
        except Exception as e:
            logger.error(f"Error toggling STT: {e}")
            # Ensure UI is updated even if there's an error
            self.state_changed.emit(self.is_enabled)

    def stop(self):
        """Stop STT service immediately"""
        # Cancel any pending tasks
        if self._start_task and not self._start_task.done():
            self._start_task.cancel()
            self._start_task = None
        if self._stop_task and not self._stop_task.done():
            self._stop_task.cancel()
            self._stop_task = None
            
        # Stop reconnection timer if active
        if self.reconnect_timer.isActive():
            self.reconnect_timer.stop()
            
        # Start new stop task
        self._stop_task = asyncio.run_coroutine_threadsafe(self._async_stop(), self.dg_loop)
        
        # Update state
        self.is_enabled = False
        self.is_paused = False
        self.state_changed.emit(False)
        self.enabled_changed.emit(False)
        logger.info("STT shutdown initiated")

    def __del__(self):
        """Cleanup on object destruction"""
        # Ensure keepalive is deactivated
        self.keepalive_active = False
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
            
        # Stop reconnection timer if active
        if hasattr(self, 'reconnect_timer') and self.reconnect_timer.isActive():
            self.reconnect_timer.stop()
            
        # Disable STT
        if hasattr(self, 'is_enabled') and self.is_enabled:
            self.set_enabled(False)
