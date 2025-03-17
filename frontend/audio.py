#!/usr/bin/env python3
import asyncio
from PyQt6.QtCore import QObject, pyqtSignal, QMutex, QMutexLocker, QIODevice
from PyQt6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices, QAudio
import time

from frontend.config import logger

# -----------------------------------------------------------------------------
#                             AUDIO DEVICE CLASS
# -----------------------------------------------------------------------------

class QueueAudioDevice(QIODevice):
    """
    Custom QIODevice implementation that uses a buffer to queue audio data.
    This allows for asynchronous audio playback from the websocket.
    """
    def __init__(self):
        super().__init__()
        self.audio_buffer = bytearray()
        self.mutex = QMutex()
        self.end_of_stream = False
        self.last_read_empty = False
        self.is_active = False

    def open(self, mode):
        success = super().open(mode)
        if success:
            self.is_active = True
        return success

    def close(self):
        self.is_active = False
        super().close()

    def seek(self, pos):
        return False

    def readData(self, maxSize: int) -> bytes:
        with QMutexLocker(self.mutex):
            if not self.audio_buffer:
                if self.end_of_stream:
                    logger.debug("[QueueAudioDevice] Buffer empty and end-of-stream marked")
                    return bytes()
                return bytes(maxSize)
            data = bytes(self.audio_buffer[:maxSize])
            self.audio_buffer = self.audio_buffer[maxSize:]
            return data

    def writeData(self, data: bytes) -> int:
        with QMutexLocker(self.mutex):
            self.audio_buffer.extend(data)
            return len(data)

    def bytesAvailable(self) -> int:
        with QMutexLocker(self.mutex):
            return len(self.audio_buffer) + super().bytesAvailable()

    def isSequential(self) -> bool:
        return True

    def mark_end_of_stream(self):
        """Mark the stream as ended, indicating no more data will be written"""
        with QMutexLocker(self.mutex):
            logger.info(f"[QueueAudioDevice] Marking end of stream, current buffer size: {len(self.audio_buffer)}")
            self.end_of_stream = True
            if len(self.audio_buffer) == 0:
                self.last_read_empty = True
                logger.info("[QueueAudioDevice] Buffer empty at end-of-stream mark")

    def clear_buffer(self, mark_end=False):
        """
        Clear the audio buffer and optionally mark end of stream
        
        Args:
            mark_end: If True, mark the end of stream after clearing
        """
        with QMutexLocker(self.mutex):
            self.audio_buffer.clear()
            if mark_end:
                self.end_of_stream = True
                self.last_read_empty = True
                logger.info("[QueueAudioDevice] Audio buffer cleared and marked as end")
            else:
                self.end_of_stream = False
                self.last_read_empty = False
                logger.info("[QueueAudioDevice] Audio buffer cleared and state reset")

    def reset_end_of_stream(self):
        """Reset end-of-stream flags without clearing the buffer"""
        with QMutexLocker(self.mutex):
            self.end_of_stream = False
            self.last_read_empty = False

    def handle_audio_state(self, action):
        """Centralized method to handle audio device state transitions"""
        if action == 'enable' and not self.is_active:
            self.open(QIODevice.ReadWrite)
            self.is_active = True
            logger.info("Audio device enabled")
        elif action == 'disable' and self.is_active:
            self.close()
            self.is_active = False
            logger.info("Audio device disabled")

# -----------------------------------------------------------------------------
#                             AUDIO MANAGER CLASS
# -----------------------------------------------------------------------------

class AudioManager(QObject):
    """
    Manages audio playback for the application.
    Handles TTS audio streaming from the websocket.
    """
    audio_state_changed = pyqtSignal(QAudio.State)
    
    def __init__(self):
        super().__init__()
        self.audio_sink, self.audio_device = self._setup_audio()
        self.audio_sink.stateChanged.connect(self.audio_state_changed)
        self.audio_queue = asyncio.Queue()
        self.tts_audio_playing = False
        self.audio_consumer_task = None
        logger.info("AudioManager initialized")
        
    def _setup_audio(self):
        """Set up the audio output device and format"""
        audio_format = QAudioFormat()
        audio_format.setSampleRate(24000)
        audio_format.setChannelCount(1)
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        device = QMediaDevices.defaultAudioOutput()
        if device is None:
            logger.error("Error: No audio output device found!")
        else:
            logger.info("Default audio output device found.")

        audio_sink = QAudioSink(device, audio_format)
        audio_sink.setVolume(1.0)
        logger.info(f"Audio sink created with initial state: {audio_sink.state()}")

        audio_device = QueueAudioDevice()
        audio_device.open(QIODevice.OpenModeFlag.ReadOnly)
        audio_sink.start(audio_device)
        logger.info("Audio sink started with audio device")
        return audio_sink, audio_device
    
    def start_audio_consumer(self):
        """Start the async audio consumer task"""
        if not self.audio_consumer_task or self.audio_consumer_task.done():
            self.audio_consumer_task = asyncio.create_task(self.audio_consumer())
            logger.info("Started audio consumer task")
    
    async def audio_consumer(self):
        """Async consumer that processes audio data from the queue"""
        logger.info("[audio_consumer] Starting async audio loop")
        while True:
            try:
                pcm_chunk = await self.audio_queue.get()
                if pcm_chunk is None:
                    logger.info("[audio_consumer] Received end-of-stream marker.")
                    await asyncio.to_thread(self.audio_device.mark_end_of_stream)
                    while True:
                        buffer_len = await asyncio.to_thread(lambda: len(self.audio_device.audio_buffer))
                        if buffer_len == 0:
                            logger.info("[audio_consumer] Audio buffer is empty, stopping sink.")
                            self.audio_sink.stop()
                            break
                        await asyncio.sleep(0.05)
                    await asyncio.to_thread(self.audio_device.reset_end_of_stream)
                    continue

                if self.audio_sink.state() != QAudio.State.ActiveState:
                    logger.debug("[audio_consumer] Restarting audio sink from non-active state.")
                    self.audio_device.close()
                    self.audio_device.open(QIODevice.OpenModeFlag.ReadOnly)
                    self.audio_sink.start(self.audio_device)

                bytes_written = await asyncio.to_thread(self.audio_device.writeData, pcm_chunk)
                logger.debug(f"[audio_consumer] Wrote {bytes_written} bytes to device.")
                await asyncio.sleep(0)
            
            except Exception as e:
                logger.error(f"[audio_consumer] Error: {e}")
                await asyncio.sleep(0.05)
    
    def process_audio_data(self, pcm_data: bytes, stt_handler=None):
        """
        Process incoming audio data from the websocket
        
        Args:
            pcm_data: The audio data received
            stt_handler: Optional callback to handle STT pausing/resuming
        """
        logger.info(f"Received audio chunk of size: {len(pcm_data)} bytes")
        
        # Handle empty audio message (end of stream)
        if not pcm_data or pcm_data == b'audio:':
            logger.info("Received empty audio message, marking end-of-stream")
            self.audio_queue.put_nowait(None)
            self.audio_device.mark_end_of_stream()
            
            # Resume STT after TTS audio
            if stt_handler and self.tts_audio_playing:
                asyncio.create_task(self.resume_stt_after_tts(stt_handler))
            self.tts_audio_playing = False
        else:
            # If this is the first audio chunk, pause STT
            if not self.tts_audio_playing and stt_handler:
                self.tts_audio_playing = True
                logger.info("Pausing STT due to TTS audio starting")
                stt_handler.set_paused(True)
                    
            # Process the audio data
            prefix = b'audio:'
            if pcm_data.startswith(prefix):
                pcm_data = pcm_data[len(prefix):]
            self.audio_queue.put_nowait(pcm_data)
    
    async def resume_stt_after_tts(self, stt_handler):
        """Wait for TTS audio to finish playing before resuming STT"""
        logger.info("Waiting for TTS audio to finish playing to resume STT...")
        # Wait until the audio sink is stopped (i.e. TTS audio finished playing)
        while self.audio_sink.state() != QAudio.State.StoppedState:
            await asyncio.sleep(0.1)
        if stt_handler.is_enabled:
            logger.info("Resuming STT after TTS finished playing")
            # Give some time for the audio system to fully settle
            await asyncio.sleep(0.2)
            
            # Reset the activity timer before resuming STT to ensure a fresh timeout period
            stt_handler.last_activity_time = time.time()
            logger.info(f"Reset STT activity timer before unpausing (timeout in {stt_handler.keepalive_timeout} seconds)")
            
            # Now unpause STT
            stt_handler.set_paused(False)
    
    async def stop_audio(self):
        """Stop audio playback and clear buffers"""
        logger.info("Stopping audio playback")
        
        # Reset state flag and stop audio sink
        self.tts_audio_playing = False
        self.audio_sink.stop()
        self.audio_state_changed.emit(QAudio.State.StoppedState)
        
        # Clear device buffer and audio queue
        await asyncio.to_thread(lambda: self.audio_device.clear_buffer(mark_end=True))
        
        # Clear the audio queue efficiently
        self._clear_audio_queue()
        
        # Add end-of-stream marker
        self.audio_queue.put_nowait(None)
        logger.info("Audio resources cleaned up")
    
    def _clear_audio_queue(self):
        """Helper method to clear the audio queue"""
        try:
            while True:
                self.audio_queue.get_nowait()
                self.audio_queue.task_done()
        except asyncio.QueueEmpty:
            pass
    
    def get_audio_state(self):
        """Get the current state of the audio buffer and end-of-stream flag"""
        with QMutexLocker(self.audio_device.mutex):
            return len(self.audio_device.audio_buffer), self.audio_device.end_of_stream
    
    def cleanup(self):
        """Clean up audio resources completely and release all resources"""
        logger.info("Performing complete audio resource cleanup")
        
        # Cancel the consumer task if it's running
        if self.audio_consumer_task and not self.audio_consumer_task.done():
            self.audio_consumer_task.cancel()
            logger.debug("Audio consumer task cancelled")
        
        # Stop the audio sink and clean up device
        if self.audio_sink:
            self.audio_sink.stop()
            logger.debug("Audio sink stopped")
        
        if self.audio_device:
            self.audio_device.clear_buffer()
            self.audio_device.close()
            logger.debug("Audio device closed and buffer cleared")
            
        # Reset state flag and clear queue
        self.tts_audio_playing = False
        self._clear_audio_queue()
        
        logger.info("Audio resources fully cleaned up and released") 