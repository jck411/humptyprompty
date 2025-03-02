"""
Audio processing utilities for the frontend application.
"""
import logging
import asyncio
from PyQt6.QtCore import QMutex, QMutexLocker, QIODevice, QTimer
from PyQt6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices, QAudio
from frontend.config.config import AUDIO_CONFIG
from frontend.utils.logger import get_logger

logger = get_logger(__name__)

class QueueAudioDevice(QIODevice):
    """
    A custom QIODevice for handling audio data in a queue.
    """
    def __init__(self):
        """Initialize the audio device with an empty buffer."""
        super().__init__()
        self.audio_buffer = bytearray()
        self.mutex = QMutex()
        self.end_of_stream = False
        self.last_read_empty = False

    def readData(self, maxSize: int) -> bytes:
        """
        Read data from the audio buffer.
        
        Args:
            maxSize: The maximum number of bytes to read.
            
        Returns:
            The read bytes.
        """
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
        """
        Write data to the audio buffer.
        
        Args:
            data: The bytes to write.
            
        Returns:
            The number of bytes written.
        """
        with QMutexLocker(self.mutex):
            self.audio_buffer.extend(data)
            return len(data)

    def bytesAvailable(self) -> int:
        """
        Get the number of bytes available in the buffer.
        
        Returns:
            The number of bytes available.
        """
        with QMutexLocker(self.mutex):
            return len(self.audio_buffer) + super().bytesAvailable()

    def isSequential(self) -> bool:
        """
        Check if the device is sequential.
        
        Returns:
            True, as this is a sequential device.
        """
        return True

    def mark_end_of_stream(self):
        """Mark the end of the audio stream."""
        with QMutexLocker(self.mutex):
            logger.info(f"[QueueAudioDevice] Marking end of stream, current buffer size: {len(self.audio_buffer)}")
            self.end_of_stream = True
            if len(self.audio_buffer) == 0:
                self.last_read_empty = True
                logger.info("[QueueAudioDevice] Buffer empty at end-of-stream mark")

    def clear_buffer(self):
        """Clear the audio buffer and reset the state."""
        with QMutexLocker(self.mutex):
            self.audio_buffer.clear()
            self.end_of_stream = False
            self.last_read_empty = False
            logger.info("[QueueAudioDevice] Audio buffer cleared and state reset")

def setup_audio():
    """
    Set up the audio system.
    
    Returns:
        A tuple containing the audio sink and audio device.
    """
    audio_format = QAudioFormat()
    audio_format.setSampleRate(AUDIO_CONFIG['sample_rate'])
    audio_format.setChannelCount(AUDIO_CONFIG['channels'])
    audio_format.setSampleFormat(getattr(QAudioFormat.SampleFormat, AUDIO_CONFIG['sample_format']))

    device = QMediaDevices.defaultAudioOutput()
    if device is None:
        logger.error("Error: No audio output device found!")
    else:
        logger.info("Default audio output device found.")

    audio_sink = QAudioSink(device, audio_format)
    audio_sink.setVolume(AUDIO_CONFIG['volume'])
    logger.info(f"Audio sink created with initial state: {audio_sink.state()}")

    audio_device = QueueAudioDevice()
    audio_device.open(QIODevice.OpenModeFlag.ReadOnly)
    audio_sink.start(audio_device)
    logger.info("Audio sink started with audio device")
    return audio_sink, audio_device

class AudioManager:
    """
    Manager for audio processing and playback.
    """
    def __init__(self):
        """Initialize the audio manager."""
        self.audio_sink, self.audio_device = setup_audio()
        self.audio_queue = asyncio.Queue()
        
        # Set up timers for audio processing
        self.audio_timer = QTimer()
        self.audio_timer.setInterval(50)  # Process audio every 50ms
        self.audio_timer.timeout.connect(self.feed_audio_data)
        
        self.state_monitor_timer = QTimer()
        self.state_monitor_timer.setInterval(200)  # Check audio state every 200ms
        self.state_monitor_timer.timeout.connect(self.check_audio_state)
        
        # Start timers
        self.audio_timer.start()
        self.state_monitor_timer.start()
        
        logger.info("AudioManager initialized with state monitoring")
    
    def check_audio_state(self):
        """Check the current state of the audio sink."""
        current_state = self.audio_sink.state()
        with QMutexLocker(self.audio_device.mutex):
            buffer_size = len(self.audio_device.audio_buffer)
            is_end_of_stream = self.audio_device.end_of_stream
            if current_state == QAudio.State.IdleState and buffer_size == 0 and is_end_of_stream:
                logger.info("[check_audio_state] Detected idle condition. Buffer size: %d, End of stream: %s", buffer_size, is_end_of_stream)
                self.handle_audio_state_changed(current_state)
    
    def handle_audio_state_changed(self, state):
        """
        Handle changes in the audio state.
        
        Args:
            state: The new audio state.
        """
        logger.info(f"[handle_audio_state_changed] Audio state changed to: {state}")
        with QMutexLocker(self.audio_device.mutex):
            buffer_size = len(self.audio_device.audio_buffer)
            is_end_of_stream = self.audio_device.end_of_stream
        logger.info(f"[handle_audio_state_changed] Buffer size: {buffer_size}, End of stream: {is_end_of_stream}")
    
    def process_audio_data(self, pcm_data: bytes):
        """
        Process incoming audio data.
        
        Args:
            pcm_data: The PCM audio data.
        """
        logger.info(f"Processing audio chunk of size: {len(pcm_data)} bytes")
        if pcm_data == b'audio:' or len(pcm_data) == 0:
            logger.info("Received empty audio message, marking end of stream")
            self.audio_queue.put_nowait(None)
            self.audio_device.mark_end_of_stream()
        else:
            prefix = b'audio:'
            if pcm_data.startswith(prefix):
                pcm_data = pcm_data[len(prefix):]
            self.audio_queue.put_nowait(pcm_data)
    
    def feed_audio_data(self):
        """Feed audio data from the queue to the audio device."""
        current_state = self.audio_sink.state()
        logger.debug(f"[feed_audio_data] Audio sink state: {current_state}")
        if current_state != QAudio.State.ActiveState:
            logger.warning(f"[feed_audio_data] Audio sink not active! Current state: {current_state}. Attempting to restart.")
            self.audio_sink.start(self.audio_device)
            logger.info("[feed_audio_data] Audio sink restarted")
            return

        chunk_limit = 5
        chunks_processed = 0
        
        try:
            while chunks_processed < chunk_limit:
                try:
                    pcm_chunk = self.audio_queue.get_nowait()
                    chunks_processed += 1
                    
                    if pcm_chunk is None:
                        logger.info("[feed_audio_data] Received end-of-stream marker")
                        self.audio_device.mark_end_of_stream()
                        if len(self.audio_device.audio_buffer) == 0:
                            logger.info("[feed_audio_data] Buffer empty at end-of-stream, stopping audio sink")
                            self.audio_sink.stop()
                        break
                    bytes_written = self.audio_device.writeData(pcm_chunk)
                    logger.debug(f"[feed_audio_data] Wrote {bytes_written} bytes to audio device")
                except asyncio.QueueEmpty:
                    break
            if chunks_processed >= chunk_limit and not self.audio_queue.empty():
                QTimer.singleShot(1, self.feed_audio_data)
        except Exception as e:
            logger.error(f"Error in feed_audio_data: {e}")
            logger.exception("Stack trace:")
    
    def clear_audio(self):
        """Clear all audio data and reset the audio device."""
        current_state = self.audio_sink.state()
        logger.info(f"Audio sink state before stopping: {current_state}")
        if current_state == QAudio.State.ActiveState:
            logger.info("Audio sink is active; stopping it")
            self.audio_sink.stop()
            logger.info("Audio sink stopped")
        else:
            logger.info(f"Audio sink not active; current state: {current_state}")

        with QMutexLocker(self.audio_device.mutex):
            logger.info("Clearing audio device buffer")
            self.audio_device.audio_buffer.clear()
            self.audio_device.end_of_stream = True
        
        # Clear the queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        # Add end-of-stream marker
        self.audio_queue.put_nowait(None)
        logger.info("End-of-stream marker placed in audio queue; audio resources cleaned up")
