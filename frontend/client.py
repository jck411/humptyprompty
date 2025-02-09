#!/usr/bin/env python3
import sys
import json
import asyncio
import requests
import websockets
import logging

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QScrollArea, QFrame, QLabel
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QIODevice, QMutex, QMutexLocker
from PyQt6.QtGui import QColor, QPalette, QIcon
from PyQt6.QtMultimedia import (
    QAudioFormat,
    QAudioSink,
    QMediaDevices,
    QAudio,
)

# ===================== Logging Configuration =====================
LOG_LEVEL = logging.WARNING  # Change this to adjust the logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL.
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ===================== Server Configuration =====================
# Replace with your server machine's IP address, port, and WebSocket path.
SERVER_HOST = "192.168.1.226"  # <-- CHANGE THIS to your server's local IP
SERVER_PORT = 8000
WEBSOCKET_PATH = "/ws/chat"
HTTP_BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

# ===================== Color Scheme =====================
COLORS = {
    'background': '#F0F2F5',
    'user_bubble': '#DCF8C6',
    'assistant_bubble': '#E8E8E8',
    'text_primary': '#000000',
    'text_secondary': '#666666',
    'button_primary': '#0D8BD9',
    'button_hover': '#0A6CA8',
    'button_pressed': '#084E7A',
    'input_background': '#FFFFFF',
    'input_border': '#E0E0E0'
}

# ===================== QueueAudioDevice =====================
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

# ===================== WebSocketClient =====================
class WebSocketClient(QThread):
    message_received = pyqtSignal(str)
    stt_text_received = pyqtSignal(str)
    connection_status = pyqtSignal(bool)
    audio_received = pyqtSignal(bytes)  # PCM audio data

    def __init__(self):
        super().__init__()
        self.ws = None
        self.running = True
        self.messages = []

    async def connect(self):
        ws_url = f"ws://{SERVER_HOST}:{SERVER_PORT}{WEBSOCKET_PATH}"
        try:
            self.ws = await websockets.connect(ws_url)
            self.connection_status.emit(True)
            logger.info(f"Frontend: WebSocket connected to {ws_url}")

            while self.running:
                try:
                    message = await self.ws.recv()
                    if isinstance(message, bytes):
                        # Remove the 'audio:' prefix if present.
                        prefix = b'audio:'
                        if message.startswith(prefix):
                            audio_data = message[len(prefix):]
                        else:
                            audio_data = message
                        logger.info(f"Frontend: Received binary message of size: {len(audio_data)} bytes")
                        self.audio_received.emit(audio_data)
                    else:
                        logger.info(f"Frontend: Received text message: {message[:100]}...")
                        try:
                            data = json.loads(message)
                            if "content" in data:
                                self.message_received.emit(data["content"])
                            elif "stt_text" in data:
                                self.stt_text_received.emit(data["stt_text"])
                        except json.JSONDecodeError:
                            logger.error(f"Frontend: Failed to parse JSON message: {message}")
                except websockets.exceptions.ConnectionClosed:
                    logger.info("Frontend: WebSocket connection closed")
                    break
                except Exception as e:
                    logger.error(f"Frontend: Error processing WebSocket message: {e}")
                    break
        except Exception as e:
            logger.error(f"Frontend: WebSocket connection error: {e}")
        finally:
            self.connection_status.emit(False)

    async def send_message(self, message):
        if self.ws:
            self.messages.append({
                "sender": "user",
                "text": message
            })
            await self.ws.send(json.dumps({
                "action": "chat",
                "messages": self.messages
            }))

    def handle_assistant_message(self, message):
        self.messages.append({
            "sender": "assistant",
            "text": message
        })

    def run(self):
        asyncio.run(self.connect())

# ===================== MessageBubble =====================
class MessageBubble(QFrame):
    def __init__(self, text, is_user=True, parent=None):
        super().__init__(parent)
        self.setObjectName("messageBubble")
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.RichText)
        self.label.setOpenExternalLinks(True)
        self.setStyleSheet(f"""
            QFrame#messageBubble {{
                background-color: {COLORS['user_bubble'] if is_user else COLORS['assistant_bubble']};
                border-radius: 15px;
                padding: 10px;
                margin: {'10px 50px 10px 10px' if is_user else '10px 10px 10px 50px'};
            }}
            QLabel {{
                color: {COLORS['text_primary']};
                font-size: 14px;
            }}
        """)
        layout.addWidget(self.label)
        layout.setContentsMargins(10, 10, 10, 10)
    
    def update_text(self, new_text):
        self.label.setText(new_text)
    
    def get_text(self):
        return self.label.text()

# ===================== ChatWindow =====================
class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modern Chat Interface")
        self.setMinimumSize(800, 600)

        # Buffer for in-progress assistant message
        self.assistant_text_in_progress = ""
        self.assistant_bubble_in_progress = None

        # TTS and STT toggle states
        self.tts_enabled = True
        self.is_toggling_tts = False
        self.stt_enabled = False
        self.is_toggling_stt = False

        # Main layout setup
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Chat area
        self.chat_area = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_area)
        self.chat_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(self.chat_area)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Input area
        input_widget = QWidget()
        input_layout = QHBoxLayout(input_widget)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Type your message...")
        self.text_input.setMaximumHeight(100)

        send_button = QPushButton("Send")
        send_button.setFixedSize(50, 50)

        self.toggle_stt_button = QPushButton("STT Off")
        self.toggle_stt_button.setFixedSize(120, 50)

        self.toggle_tts_button = QPushButton("TTS On")
        self.toggle_tts_button.setFixedSize(120, 50)

        self.stop_all_button = QPushButton()
        self.stop_all_button.setFixedSize(50, 50)
        self.stop_all_button.setIcon(QIcon("/home/jack/AI-chat-PyQt/frontend_PyQt/icons/stop-button.png"))

        input_layout.addWidget(self.text_input)
        input_layout.addWidget(send_button)
        input_layout.addWidget(self.toggle_stt_button)
        input_layout.addWidget(self.toggle_tts_button)
        input_layout.addWidget(self.stop_all_button)

        layout.addWidget(scroll)
        layout.addWidget(input_widget)

        # Initialize WebSocket client (in its own thread)
        self.ws_client = WebSocketClient()
        self.ws_client.message_received.connect(self.handle_message)
        self.ws_client.stt_text_received.connect(self.handle_stt_text)
        self.ws_client.connection_status.connect(self.handle_connection_status)
        self.ws_client.audio_received.connect(self.on_audio_received)
        self.ws_client.start()

        # Connect signals
        send_button.clicked.connect(self.send_message)
        self.text_input.textChanged.connect(self.adjust_text_input_height)
        self.toggle_stt_button.clicked.connect(self.toggle_stt)
        self.toggle_tts_button.clicked.connect(self.toggle_tts)
        self.stop_all_button.clicked.connect(self.stop_tts_and_generation)

        # ===================== Setup QAudio for PCM playback =====================
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
        else:
            logger.info(f"Using audio device: {device.description()}")

        self.audio_sink = QAudioSink(device, audio_format)
        logger.info(f"Audio sink created with state: {self.audio_sink.state()}")
        self.audio_sink.setVolume(1.0)
        logger.info(f"Audio sink volume: {self.audio_sink.volume()}")

        self.audio_device = QueueAudioDevice()
        self.audio_device.open(QIODevice.OpenModeFlag.ReadOnly)
        logger.info(f"Audio device opened: {self.audio_device.isOpen()}")

        self.audio_sink.start(self.audio_device)
        logger.info(f"Audio sink started with state: {self.audio_sink.state()}")

        self.audio_queue = asyncio.Queue()
        self.audio_timer = QTimer()
        self.audio_timer.setInterval(10)  # Check every 10ms
        self.audio_timer.timeout.connect(self.feed_audio_data)
        self.audio_timer.start()

    def apply_styling(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLORS['background']};
            }}
            QScrollArea {{
                border: none;
                background-color: {COLORS['background']};
            }}
            QTextEdit {{
                border: 1px solid {COLORS['input_border']};
                border-radius: 20px;
                padding: 10px;
                background-color: {COLORS['input_background']};
                color: {COLORS['text_primary']};
                font-size: 14px;
            }}
            QPushButton {{
                border: none;
                border-radius: 25px;
                background-color: {COLORS['button_primary']};
                color: white;
                padding: 10px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLORS['button_hover']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['button_pressed']};
            }}
            QLabel {{
                color: {COLORS['text_primary']};
            }}
        """)
        palette = self.text_input.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(COLORS['text_secondary']))
        self.text_input.setPalette(palette)

    def send_message(self):
        text = self.text_input.toPlainText().strip()
        if text:
            self.finalize_assistant_bubble()
            self.add_message(text, True)
            asyncio.run(self.ws_client.send_message(text))
            self.text_input.clear()

    def handle_message(self, token):
        if not self.assistant_bubble_in_progress:
            self.assistant_bubble_in_progress = MessageBubble("", is_user=False)
            self.chat_layout.insertWidget(self.chat_layout.count() - 1, self.assistant_bubble_in_progress)
        self.assistant_text_in_progress += token
        self.assistant_bubble_in_progress.update_text(self.assistant_text_in_progress)
        self.auto_scroll_chat()

    def finalize_assistant_bubble(self):
        if self.assistant_bubble_in_progress:
            self.ws_client.handle_assistant_message(self.assistant_text_in_progress)
            self.assistant_text_in_progress = ""
            self.assistant_bubble_in_progress = None

    def handle_stt_text(self, text):
        self.text_input.setPlainText(text)

    def handle_connection_status(self, connected):
        self.setWindowTitle(f"Modern Chat Interface - {'Connected' if connected else 'Disconnected'}")

    def add_message(self, text, is_user):
        bubble = MessageBubble(text, is_user)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        self.auto_scroll_chat()

    def auto_scroll_chat(self):
        QApplication.processEvents()
        scroll_area = self.findChild(QScrollArea)
        vsb = scroll_area.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    def adjust_text_input_height(self):
        doc_height = self.text_input.document().size().height()
        new_height = min(max(50, doc_height + 20), 100)
        self.text_input.setFixedHeight(int(new_height))

    def toggle_stt(self):
        self.is_toggling_stt = True
        try:
            if not self.stt_enabled:
                resp = requests.post(f"{HTTP_BASE_URL}/api/start-stt")
                resp.raise_for_status()
                self.stt_enabled = True
            else:
                resp = requests.post(f"{HTTP_BASE_URL}/api/pause-stt")
                resp.raise_for_status()
                self.stt_enabled = False
            self.toggle_stt_button.setText("STT On" if self.stt_enabled else "STT Off")
        except requests.RequestException as e:
            logger.error(f"Error toggling STT: {e}")
        finally:
            self.is_toggling_stt = False

    def toggle_tts(self):
        self.is_toggling_tts = True
        try:
            resp = requests.post(f"{HTTP_BASE_URL}/api/toggle-tts")
            resp.raise_for_status()
            data = resp.json()
            self.tts_enabled = data.get("tts_enabled", self.tts_enabled)
            if not self.tts_enabled:
                stop_resp = requests.post(f"{HTTP_BASE_URL}/api/stop-tts")
                stop_resp.raise_for_status()
            self.toggle_tts_button.setText("TTS On" if self.tts_enabled else "TTS Off")
        except requests.RequestException as e:
            logger.error(f"Error toggling TTS: {e}")
        finally:
            self.is_toggling_tts = False

    def stop_tts_and_generation(self):
        try:
            requests.post(f"{HTTP_BASE_URL}/api/stop-tts").raise_for_status()
            requests.post(f"{HTTP_BASE_URL}/api/stop-generation").raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Error stopping TTS and generation: {e}")
        self.finalize_assistant_bubble()

    def on_audio_received(self, pcm_data: bytes):
        logger.info(f"Frontend: Processing audio chunk of size: {len(pcm_data)} bytes")
        self.audio_queue.put_nowait(pcm_data)

    def feed_audio_data(self):
        if self.audio_sink.state() != QAudio.State.ActiveState:
            logger.warning(f"Warning: Audio sink not active! State: {self.audio_sink.state()}")
            self.audio_sink.start(self.audio_device)
            return

        chunks_processed = 0
        total_bytes = 0
        
        try:
            while True:
                try:
                    pcm_chunk = self.audio_queue.get_nowait()
                    if pcm_chunk is None:
                        logger.info("Received end-of-stream marker")
                        break
                    chunk_size = len(pcm_chunk)
                    total_bytes += chunk_size
                    # Use the thread-safe writeData method
                    self.audio_device.writeData(pcm_chunk)
                    chunks_processed += 1
                except asyncio.QueueEmpty:
                    break
            
            if chunks_processed > 0:
                logger.debug("Audio Stats:")
                logger.debug(f"- Chunks processed: {chunks_processed}")
                logger.debug(f"- Total bytes processed: {total_bytes}")
                with QMutexLocker(self.audio_device.mutex):
                    logger.debug(f"- Current buffer size: {len(self.audio_device.audio_buffer)}")
                logger.debug(f"- Sink state: {self.audio_sink.state()}")
                logger.debug(f"- Sink volume: {self.audio_sink.volume()}")
                
                # Optionally, restart the sink if not active
                if self.audio_sink.state() != QAudio.State.ActiveState:
                    logger.info("Restarting audio sink...")
                    self.audio_sink.start(self.audio_device)
                    
        except Exception as e:
            logger.error(f"Error in feed_audio_data: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ChatWindow()
    window.apply_styling()
    window.show()
    sys.exit(app.exec())
