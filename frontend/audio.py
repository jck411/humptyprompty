import logging
from PyQt6.QtCore import QIODevice, QMutex, QMutexLocker
from PyQt6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices, QAudio

logger = logging.getLogger(__name__)

class QueueAudioDevice(QIODevice):
    def __init__(self):
        super().__init__()
        self.audio_buffer = bytearray()
        self.mutex = QMutex()
        logger.debug("QueueAudioDevice initialized")

    def readData(self, maxSize: int) -> bytes:
        with QMutexLocker(self.mutex):
            if len(self.audio_buffer) == 0:
                logger.debug("Audio buffer empty, returning silence")
                return bytes(maxSize)
            data = bytes(self.audio_buffer[:maxSize])
            self.audio_buffer = self.audio_buffer[maxSize:]
            logger.debug(f"Reading {len(data)} bytes from buffer, {len(self.audio_buffer)} remaining")
            return data

    def writeData(self, data: bytes) -> int:
        with QMutexLocker(self.mutex):
            logger.debug(f"writeData: appending {len(data)} bytes")
            self.audio_buffer.extend(data)
            return len(data)

    def bytesAvailable(self) -> int:
        with QMutexLocker(self.mutex):
            available = len(self.audio_buffer) + super().bytesAvailable()
            logger.debug(f"bytesAvailable: {available}")
            return available

    def isSequential(self) -> bool:
        return True

def setup_audio():
    audio_format = QAudioFormat()
    audio_format.setSampleRate(24000)
    audio_format.setChannelCount(1)
    audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)

    logger.info(f"Audio Format - Sample Rate: {audio_format.sampleRate()}")
    logger.info(f"Audio Format - Channels: {audio_format.channelCount()}")
    logger.info(f"Audio Format - Sample Format: {audio_format.sampleFormat()}")

    device = QMediaDevices.defaultAudioOutput()
    if device is None:
        logger.error("Error: No audio output device found!")
        return None, None

    logger.info(f"Using audio device: {device.description()}")

    audio_sink = QAudioSink(device, audio_format)
    logger.info(f"Audio sink created with state: {audio_sink.state()}")
    audio_sink.setVolume(1.0)
    logger.info(f"Audio sink volume: {audio_sink.volume()}")

    audio_device = QueueAudioDevice()
    audio_device.open(QIODevice.OpenModeFlag.ReadOnly)
    logger.info(f"Audio device opened: {audio_device.isOpen()}")

    audio_sink.start(audio_device)
    logger.info(f"Audio sink started with state: {audio_sink.state()}")

    return audio_sink, audio_device