from PySide6.QtCore import QObject, Signal, Slot, QIODevice, QMutex, QMutexLocker
from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices, QAudio
from frontend.config import logger

class QueueAudioDevice(QIODevice):
    """
    Custom QIODevice that acts as a buffer for audio data.
    
    This device manages a thread-safe audio buffer that can be written to
    by the WebSocket handler and read from by the audio sink.
    """
    def __init__(self):
        super().__init__()
        self.audio_buffer = bytearray()
        self.mutex = QMutex()
        self.end_of_stream = False
        self.is_active = False
        self.buffer_threshold = 1024 * 16  # 16KB buffer threshold for logging

    def open(self, mode):
        success = super().open(mode)
        if success:
            self.is_active = True
            logger.debug("[QueueAudioDevice] Device opened successfully")
        return success

    def close(self):
        self.is_active = False
        logger.debug("[QueueAudioDevice] Device closed")
        super().close()

    def readData(self, maxSize):
        with QMutexLocker(self.mutex):
            if not self.audio_buffer:
                if self.end_of_stream:
                    return bytes()
                return bytes(maxSize)
            
            # Read up to maxSize bytes from the buffer
            data = bytes(self.audio_buffer[:maxSize])
            self.audio_buffer = self.audio_buffer[maxSize:]
            
            # Log buffer state if it's getting large
            if len(self.audio_buffer) > self.buffer_threshold:
                logger.debug(f"[QueueAudioDevice] Large buffer: {len(self.audio_buffer)} bytes")
                
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
        """Mark the end of the audio stream"""
        with QMutexLocker(self.mutex):
            self.end_of_stream = True
            if not self.audio_buffer:
                logger.debug("[QueueAudioDevice] Buffer empty at end-of-stream mark")

    def clear_buffer(self):
        """Clear the audio buffer and reset state"""
        with QMutexLocker(self.mutex):
            buffer_size = len(self.audio_buffer)
            self.audio_buffer.clear()
            self.end_of_stream = False
            logger.debug(f"[QueueAudioDevice] Cleared {buffer_size} bytes from buffer")

    def clear_and_mark_end(self):
        """Clear the buffer and mark end of stream in one atomic operation"""
        with QMutexLocker(self.mutex):
            self.audio_buffer.clear()
            self.end_of_stream = True
            logger.debug("[QueueAudioDevice] Buffer cleared and marked as end of stream")


class AudioManager(QObject):
    """
    Manages audio playback for TTS responses.
    
    Handles buffering and playback of audio data received from the backend.
    """
    # Signals
    stateChanged = Signal(int)  # Audio state changed (playing, stopped, etc)
    
    # Signal to notify when audio playback starts/stops
    playbackStateChanged = Signal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.audio_sink = None
        self.audio_device = None
        self.is_playing = False
        self.setup_audio()
        logger.info("AudioManager initialized")
        
    def setup_audio(self):
        """Initialize audio format and devices"""
        try:
            # Set up audio format for 24kHz mono 16-bit audio (common for TTS)
            audio_format = QAudioFormat()
            audio_format.setSampleRate(24000)
            audio_format.setChannelCount(1)
            audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            
            # Get default audio output device
            device = QMediaDevices.defaultAudioOutput()
            if device is None:
                logger.error("No audio output device found!")
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
            logger.info("Audio sink started successfully")
        except Exception as e:
            logger.error(f"Failed to set up audio: {e}")
        
    @Slot(int)
    def on_audio_state_changed(self, state):
        """Handle audio state changes"""
        state_names = {
            QAudio.State.ActiveState: "Active",
            QAudio.State.SuspendedState: "Suspended",
            QAudio.State.StoppedState: "Stopped",
            QAudio.State.IdleState: "Idle"
        }
        state_name = state_names.get(state, f"Unknown ({state})")
        logger.debug(f"Audio state changed to: {state_name}")
        
        # Emit signal for QML
        self.stateChanged.emit(state)
    
    @Slot(bytes)
    def process_audio_data(self, data):
        """Process incoming audio data"""
        if not self.audio_device or not self.audio_sink:
            logger.error("Cannot process audio: device or sink not initialized")
            return False
            
        try:
            # Check if this is an end-of-stream marker
            if data == b'audio:' or len(data) == 0:
                logger.debug("Received empty audio, marking end-of-stream")
                self.audio_device.mark_end_of_stream()
                
                # Update playback state - audio has stopped
                self.update_playback_state(False)
                return False
            
            # Extract audio data if it has the audio: prefix
            if data.startswith(b'audio:'):
                audio_data = data[len(b'audio:'):]
            else:
                audio_data = data
                
            if len(audio_data) == 0:
                logger.debug("Empty audio data after prefix, marking end-of-stream")
                self.audio_device.mark_end_of_stream()
                
                # Update playback state - audio has stopped
                self.update_playback_state(False)
                return False
                
            # If audio sink is not active, restart it
            if self.audio_sink.state() != QAudio.State.ActiveState:
                logger.debug("Restarting audio sink")
                self.restart_audio_sink()
            
            # Write data to the device buffer
            bytes_written = self.audio_device.writeData(audio_data)
            
            # Only log for larger chunks to reduce noise
            if len(audio_data) > 1000:
                logger.debug(f"Wrote {bytes_written} bytes to audio buffer")
            
            # Update playback state - audio is playing
            self.update_playback_state(True)
            return True  # More audio
        except Exception as e:
            logger.error(f"Error processing audio data: {e}")
            return False
            
    def update_playback_state(self, is_playing):
        """Update the playback state and emit signal if changed"""
        if self.is_playing != is_playing:
            self.is_playing = is_playing
            logger.info(f"Audio playback state changed to: {'playing' if is_playing else 'stopped'}")
            self.playbackStateChanged.emit(is_playing)
    
    def restart_audio_sink(self):
        """Restart the audio sink with a fresh device"""
        try:
            # Stop existing sink if any
            if self.audio_sink:
                self.audio_sink.stop()
            
            # Close and reopen the device
            if self.audio_device:
                self.audio_device.close()
                self.audio_device.open(QIODevice.OpenModeFlag.ReadOnly)
            
            # Restart the sink
            if self.audio_sink:
                self.audio_sink.start(self.audio_device)
                logger.debug("Audio sink restarted")
        except Exception as e:
            logger.error(f"Error restarting audio sink: {e}")
    
    @Slot()
    def stop_playback(self):
        """Stop current audio playback"""
        logger.info("Stopping audio playback")
        
        try:
            # Stop the audio sink
            if self.audio_sink and self.audio_sink.state() == QAudio.State.ActiveState:
                self.audio_sink.stop()
            
            # Clear the buffer and mark end of stream
            if self.audio_device:
                self.audio_device.clear_and_mark_end()
        except Exception as e:
            logger.error(f"Error stopping playback: {e}")
    
    def cleanup(self):
        """Clean up resources when shutting down"""
        logger.info("Cleaning up audio resources")
        
        try:
            if self.audio_sink:
                self.audio_sink.stop()
                
            if self.audio_device:
                self.audio_device.close()
                
            logger.info("Audio resources cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during audio cleanup: {e}")
