import logging
from PySide6.QtCore import QObject, Signal, Slot, QByteArray, QIODevice, QMutex, QMutexLocker
from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices, QAudio

class QueueAudioDevice(QIODevice):
    """Custom QIODevice that acts as a buffer for audio data"""
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

    def readData(self, maxSize):
        with QMutexLocker(self.mutex):
            if not self.audio_buffer:
                if self.end_of_stream:
                    logging.debug("[QueueAudioDevice] Buffer empty and end-of-stream marked")
                    return bytes()
                return bytes(maxSize)
            
            data = bytes(self.audio_buffer[:maxSize])
            self.audio_buffer = self.audio_buffer[maxSize:]
            return data

    def writeData(self, data):
        with QMutexLocker(self.mutex):
            self.audio_buffer.extend(data)
            return len(data)

    def bytesAvailable(self):
        with QMutexLocker(self.mutex):
            return len(self.audio_buffer) + super().bytesAvailable()

    def isSequential(self):
        return True

    def mark_end_of_stream(self):
        with QMutexLocker(self.mutex):
            logging.info(f"[QueueAudioDevice] Marking end of stream, current buffer size: {len(self.audio_buffer)}")
            self.end_of_stream = True
            if len(self.audio_buffer) == 0:
                self.last_read_empty = True
                logging.info("[QueueAudioDevice] Buffer empty at end-of-stream mark")

    def clear_buffer(self):
        with QMutexLocker(self.mutex):
            self.audio_buffer.clear()
            self.end_of_stream = False
            self.last_read_empty = False
            logging.info("[QueueAudioDevice] Audio buffer cleared and state reset")

    def reset_end_of_stream(self):
        with QMutexLocker(self.mutex):
            self.end_of_stream = False
            self.last_read_empty = False

    def clear_and_mark_end(self):
        with QMutexLocker(self.mutex):
            self.audio_buffer.clear()
            self.end_of_stream = True


class AudioManager(QObject):
    """Manages audio playback for TTS"""
    # Signals
    stateChanged = Signal(int)  # Audio state changed (playing, stopped, etc)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_audio()
        
    def setup_audio(self):
        """Initialize audio format and devices"""
        # Set up audio format for 24kHz mono 16-bit audio (common for TTS)
        audio_format = QAudioFormat()
        audio_format.setSampleRate(24000)
        audio_format.setChannelCount(1)
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        
        # Get default audio output device
        device = QMediaDevices.defaultAudioOutput()
        if device is None:
            logging.error("Error: No audio output device found!")
            return
        
        # Create audio sink
        self.audio_sink = QAudioSink(device, audio_format)
        self.audio_sink.setVolume(1.0)
        
        # Connect state change signal
        self.audio_sink.stateChanged.connect(self.on_audio_state_changed)
        
        # Create audio device for buffering
        self.audio_device = QueueAudioDevice()
        self.audio_device.open(QIODevice.OpenModeFlag.ReadOnly)
        
        # Start the audio sink
        self.audio_sink.start(self.audio_device)
        logging.info("Audio sink started with audio device")
        
    @Slot(int)
    def on_audio_state_changed(self, state):
        """Handle audio state changes"""
        logging.info(f"[AudioManager] Audio state changed to: {state}")
        self.stateChanged.emit(state)
        
        # Log buffer state for debugging
        with QMutexLocker(self.audio_device.mutex):
            buffer_size = len(self.audio_device.audio_buffer)
            is_end_of_stream = self.audio_device.end_of_stream
            logging.info(f"[AudioManager] Buffer size: {buffer_size}, End of stream: {is_end_of_stream}")
    
    @Slot(bytes)
    def process_audio_data(self, data):
        """Process incoming audio data"""
        try:
            # Check if this is an end-of-stream marker
            if data == b'audio:' or len(data) == 0:
                logging.info("[AudioManager] Received empty audio, marking end-of-stream")
                self.audio_device.mark_end_of_stream()
                return False  # No more audio
            
            # Extract audio data if it has the audio: prefix
            if data.startswith(b'audio:'):
                audio_data = data[len(b'audio:'):]
            else:
                audio_data = data
                
            if len(audio_data) == 0:
                logging.info("[AudioManager] Empty audio data after prefix, marking end-of-stream")
                self.audio_device.mark_end_of_stream()
                return False
                
            # If audio sink is not active, restart it
            if self.audio_sink.state() != QAudio.State.ActiveState:
                logging.debug("[AudioManager] Restarting audio sink from non-active state")
                self.audio_device.close()
                self.audio_device.open(QIODevice.OpenModeFlag.ReadOnly)
                self.audio_sink.start(self.audio_device)
            
            # Write data to the device buffer
            bytes_written = self.audio_device.writeData(audio_data)
            logging.debug(f"[AudioManager] Wrote {bytes_written} bytes to device buffer")
            
            return True  # More audio
        except Exception as e:
            logging.error(f"[AudioManager] Error processing audio data: {e}")
            return False
    
    @Slot()
    def stop_playback(self):
        """Stop current audio playback"""
        logging.info("[AudioManager] Stopping audio playback")
        
        # Stop the audio sink
        current_state = self.audio_sink.state()
        logging.info(f"[AudioManager] Audio sink state before stopping: {current_state}")
        
        if current_state == QAudio.State.ActiveState:
            self.audio_sink.stop()
            logging.info("[AudioManager] Audio sink stopped")
        
        # Clear the buffer and mark end of stream
        self.audio_device.clear_and_mark_end()
        logging.info("[AudioManager] Audio buffer cleared and marked as end of stream")
    
    def cleanup(self):
        """Clean up resources when shutting down"""
        try:
            if hasattr(self, 'audio_sink'):
                self.audio_sink.stop()
            if hasattr(self, 'audio_device'):
                self.audio_device.close()
            logging.info("[AudioManager] Audio resources cleaned up")
        except Exception as e:
            logging.error(f"[AudioManager] Error during cleanup: {e}")
