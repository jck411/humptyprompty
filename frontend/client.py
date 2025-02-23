#!/usr/bin/env python3
import sys
import json
import asyncio
import requests
import logging
from queue import Queue

# PyQt6 Imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QScrollArea, QSizePolicy, QTextEdit, QFrame, QLabel
)
from PyQt6.QtCore import Qt, QTimer, QSize, QMutex, QMutexLocker, QIODevice, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QPalette, QIcon
from PyQt6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices, QAudio

# ----------------------- CONFIGURATION -----------------------
SERVER_HOST = "192.168.1.226"  # Adjust as needed
SERVER_PORT = 8000
WEBSOCKET_PATH = "/ws/chat"
HTTP_BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

# Define color schemes
DARK_COLORS = {
    "background": "#2C2F33",
    "user_bubble": "#7289DA",
    "assistant_bubble": "#99AAB5",
    "text_primary": "#FFFFFF",
    "text_secondary": "#99AAB5",
    "button_primary": "#7289DA",
    "button_hover": "#677BC4",
    "button_pressed": "#5B6EAE",
    "input_background": "#23272A",
    "input_border": "#99AAB5"
}
LIGHT_COLORS = {
    "background": "#F0F2F5",
    "user_bubble": "#DCF8C6",
    "assistant_bubble": "#E8E8E8",
    "text_primary": "#000000",
    "text_secondary": "#666666",
    "button_primary": "#0D8BD9",
    "button_hover": "#0A6CA8",
    "button_pressed": "#084E7A",
    "input_background": "#FFFFFF",
    "input_border": "#E0E0E0"
}
# Start with dark mode
COLORS = DARK_COLORS

# Logger setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

# ----------------------- COMPONENTS -----------------------
class MessageBubble(QFrame):
    def __init__(self, text, is_user=True):
        super().__init__()
        self.setObjectName("messageBubble")
        self.setProperty("isUser", is_user)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.label)
    def update_text(self, new_text):
        self.label.setText(new_text)

class CustomTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
    def keyPressEvent(self, event):
        # Send message on Enter (without Shift)
        if event.key() == Qt.Key.Key_Return and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            main_window = self.window()
            if hasattr(main_window, "send_message"):
                main_window.send_message()
        else:
            super().keyPressEvent(event)

# ----------------------- WEBSOCKET CLIENT -----------------------
class WebSocketClient(QThread):
    message_received = pyqtSignal(str)
    stt_text_received = pyqtSignal(str)
    stt_state_received = pyqtSignal(bool)  # New signal for STT listening state
    connection_status = pyqtSignal(bool)
    audio_received = pyqtSignal(bytes)
    tts_state_changed = pyqtSignal(bool)

    def __init__(self, server_host, server_port, websocket_path, http_base_url):
        super().__init__()
        self.server_host = server_host
        self.server_port = server_port
        self.websocket_path = websocket_path
        self.http_base_url = http_base_url
        self.ws = None
        self.running = True
        self.messages = []

    async def connect(self):
        import websockets
        ws_url = f"ws://{self.server_host}:{self.server_port}{self.websocket_path}"
        try:
            self.ws = await websockets.connect(ws_url)
            self.connection_status.emit(True)
            logger.info(f"Frontend: WebSocket connected to {ws_url}")
            while self.running:
                try:
                    message = await self.ws.recv()
                    if isinstance(message, bytes):
                        if message.startswith(b'audio:'):
                            audio_data = message[len(b'audio:'):]
                            logger.info(f"Frontend: Received audio chunk of size: {len(audio_data)} bytes")
                            self.audio_received.emit(message)
                        else:
                            logger.warning(f"Frontend: Received binary message without audio prefix, size: {len(message)} bytes")
                            self.audio_received.emit(b'audio:' + message)
                    else:
                        logger.info(f"Frontend: Received text message: {message[:100]}...")
                        try:
                            data = json.loads(message)
                            if data.get("type") == "stt_state":
                                # Emit the listening state from the backend broadcast
                                self.stt_state_received.emit(data.get("is_listening", False))
                            elif "content" in data:
                                self.message_received.emit(data["content"])
                            elif "stt_text" in data:
                                self.stt_text_received.emit(data["stt_text"])
                        except json.JSONDecodeError:
                            logger.error(f"Frontend: Failed to parse JSON message: {message}")
                except Exception as e:
                    logger.error(f"Frontend: Error processing WebSocket message: {e}")
                    break
        except Exception as e:
            logger.error(f"Frontend: WebSocket connection error: {e}")
        finally:
            self.connection_status.emit(False)

    async def send_message(self, message):
        if self.ws:
            self.messages.append({"sender": "user", "text": message})
            await self.ws.send(json.dumps({
                "action": "chat",
                "messages": self.messages
            }))

    def handle_assistant_message(self, message):
        self.messages.append({"sender": "assistant", "text": message})

    def run(self):
        asyncio.run(self.connect())

# ----------------------- AUDIO SETUP -----------------------
class QueueAudioDevice(QIODevice):
    def __init__(self):
        super().__init__()
        self.audio_buffer = bytearray()
        self.mutex = QMutex()
        self.end_of_stream = False
        self.last_read_empty = False

    def readData(self, maxSize: int) -> bytes:
        with QMutexLocker(self.mutex):
            if not self.audio_buffer:
                if self.end_of_stream:
                    logger.info("Buffer empty and end-of-stream marked")
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
        with QMutexLocker(self.mutex):
            logger.info("Marking end of stream, current buffer size: %d", len(self.audio_buffer))
            self.end_of_stream = True
            if len(self.audio_buffer) == 0:
                self.last_read_empty = True
                logger.info("Buffer already empty at end of stream mark")

    def clear_buffer(self):
        with QMutexLocker(self.mutex):
            self.audio_buffer.clear()
            self.end_of_stream = False
            self.last_read_empty = False
            logger.info("Audio buffer cleared and state reset")

def setup_audio():
    audio_format = QAudioFormat()
    audio_format.setSampleRate(24000)
    audio_format.setChannelCount(1)
    audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
    device = QMediaDevices.defaultAudioOutput()
    if device is None:
        logger.error("Error: No audio output device found!")
    audio_sink = QAudioSink(device, audio_format)
    audio_sink.setVolume(1.0)
    audio_device = QueueAudioDevice()
    audio_device.open(QIODevice.OpenModeFlag.ReadOnly)
    audio_sink.start(audio_device)
    return audio_sink, audio_device

# ----------------------- MAIN CHAT WINDOW -----------------------
class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modern Chat Interface")
        self.setMinimumSize(800, 600)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Kiosk mode
        self.is_kiosk_mode = False
        self.normal_window_flags = self.windowFlags()
        
        # Dark mode starts enabled
        self.is_dark_mode = True
        global COLORS
        COLORS = DARK_COLORS
        
        # In-progress assistant message
        self.assistant_text_in_progress = ""
        self.assistant_bubble_in_progress = None

        # Default playback location is backend.
        # Button text will show the toggle target (i.e. "FRONT PLAY" when currently backend).
        self.playback_location = "backend"
        
        # New variable to hold the actual listening state from backend
        self.stt_listening = False  
        
        self.init_states()
        self.setup_ui()
        self.setup_websocket()
        self.setup_audio()
        self.apply_styling()
        
        self.theme_toggle.setIcon(QIcon("/home/jack/humptyprompty/frontend/icons/light_mode_24dp_E8EAED.svg"))

    def init_states(self):
        try:
            resp = requests.post(f"{HTTP_BASE_URL}/api/toggle-tts")
            resp.raise_for_status()
            self.tts_enabled = resp.json().get("tts_enabled", False)
        except requests.RequestException as e:
            logger.error(f"Error getting initial TTS state: {e}")
            self.tts_enabled = False
        
        self.is_toggling_tts = False
        self.stt_enabled = False  # Global STT flag (when user toggles STT)
        self.is_toggling_stt = False

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        self.setup_top_buttons(layout)
        self.setup_chat_area(layout)
        self.setup_input_area(layout)

    def setup_top_buttons(self, layout):
        self.top_widget = QWidget()
        top_layout = QHBoxLayout(self.top_widget)
        top_layout.setContentsMargins(0, 5, 0, 0)
        top_layout.setSpacing(5)
        
        self.toggle_stt_button = QPushButton("STT Off")
        self.toggle_stt_button.setFixedSize(120, 40)
        # Assign a unique object name for our STT button.
        self.toggle_stt_button.setObjectName("sttButton")
        
        self.toggle_tts_button = QPushButton("TTS On" if self.tts_enabled else "TTS Off")
        self.toggle_tts_button.setFixedSize(120, 40)

        top_layout.addWidget(self.toggle_stt_button)
        top_layout.addWidget(self.toggle_tts_button)
        
        # Single toggle button for switching playback location
        self.toggle_playback_button = QPushButton("FRONT PLAY")
        self.toggle_playback_button.setFixedSize(120, 40)
        top_layout.addWidget(self.toggle_playback_button)
        
        # Theme toggle button
        self.theme_toggle = QPushButton()
        self.theme_toggle.setFixedSize(45, 45)
        self.theme_toggle.setIcon(QIcon("/home/jack/humptyprompty/frontend/icons/dark_mode_24dp_E8EAED.svg"))
        self.theme_toggle.setIconSize(QSize(35, 35))
        self.theme_toggle.clicked.connect(self.toggle_theme)
        self.theme_toggle.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 20px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.1);
            }
        """)
        top_layout.addWidget(self.theme_toggle)
        
        layout.addWidget(self.top_widget)
        
        # Connect button actions
        self.toggle_stt_button.clicked.connect(self.toggle_stt)
        self.toggle_tts_button.clicked.connect(self.toggle_tts)
        self.toggle_playback_button.clicked.connect(self.toggle_playback)

    def setup_chat_area(self, layout):
        self.chat_area = QWidget()
        self.chat_area.setAutoFillBackground(True)
        self.chat_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        chat_palette = self.chat_area.palette()
        chat_palette.setColor(QPalette.ColorRole.Window, QColor(COLORS['background']))
        self.chat_area.setPalette(chat_palette)
        
        self.chat_layout = QVBoxLayout(self.chat_area)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(2)
        self.chat_layout.addStretch()

        scroll = QScrollArea()
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll.setWidget(self.chat_area)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setContentsMargins(0, 0, 0, 0)
        scroll.setAutoFillBackground(True)
        scroll_palette = scroll.palette()
        scroll_palette.setColor(QPalette.ColorRole.Window, QColor(COLORS['background']))
        scroll.setPalette(scroll_palette)
        
        layout.addWidget(scroll, stretch=1)

    def setup_input_area(self, layout):
        input_widget = QWidget()
        input_layout = QHBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(5)

        self.text_input = CustomTextEdit(self)
        self.text_input.setPlaceholderText("Type your message...")
        self.text_input.setMaximumHeight(60)
        self.text_input.setMinimumHeight(50)

        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(5)

        send_button = QPushButton()
        send_button.setFixedSize(50, 50)
        send_button.setIcon(QIcon("/home/jack/humptyprompty/frontend/icons/send.svg"))
        send_button.setIconSize(QSize(20, 20))

        self.stop_all_button = QPushButton()
        self.stop_all_button.setFixedSize(50, 50)
        self.stop_all_button.setIcon(QIcon("/home/jack/humptyprompty/frontend/icons/stop_all.svg"))
        self.stop_all_button.setIconSize(QSize(30, 30))

        button_layout.addWidget(send_button)
        button_layout.addWidget(self.stop_all_button)

        input_layout.addWidget(self.text_input, stretch=1)
        input_layout.addWidget(button_widget)

        layout.addWidget(input_widget)

        send_button.clicked.connect(self.send_message)
        self.text_input.textChanged.connect(self.adjust_text_input_height)
        self.stop_all_button.clicked.connect(self.stop_tts_and_generation)

    def setup_websocket(self):
        self.ws_client = WebSocketClient(
            SERVER_HOST, 
            SERVER_PORT, 
            WEBSOCKET_PATH, 
            HTTP_BASE_URL
        )
        self.ws_client.message_received.connect(self.handle_message)
        self.ws_client.stt_text_received.connect(self.handle_stt_text)
        self.ws_client.stt_state_received.connect(self.handle_stt_state)  # Connect new signal
        self.ws_client.connection_status.connect(self.handle_connection_status)
        self.ws_client.audio_received.connect(self.on_audio_received)
        self.ws_client.tts_state_changed.connect(self.handle_tts_state_changed)
        self.ws_client.start()

    def setup_audio(self):
        self.audio_sink, self.audio_device = setup_audio()
        self.audio_sink.stateChanged.connect(self.handle_audio_state_changed)
        self.audio_queue = asyncio.Queue()
        self.audio_timer = QTimer()
        self.audio_timer.setInterval(10)
        self.audio_timer.timeout.connect(self.feed_audio_data)
        self.audio_timer.start()
        self.state_monitor_timer = QTimer()
        self.state_monitor_timer.setInterval(100)
        self.state_monitor_timer.timeout.connect(self.check_audio_state)
        self.state_monitor_timer.start()
        logger.info("Audio setup completed with state monitoring")

    def check_audio_state(self):
        current_state = self.audio_sink.state()
        with QMutexLocker(self.audio_device.mutex):
            buffer_size = len(self.audio_device.audio_buffer)
            is_end_of_stream = self.audio_device.end_of_stream
            if current_state == QAudio.State.IdleState and buffer_size == 0 and is_end_of_stream:
                logger.info("State monitor: detected idle condition, ensuring playback completion is handled")
                self.handle_audio_state_changed(current_state)

    def handle_audio_state_changed(self, state):
        logger.info(f"Audio state changed to: {state}")
        if state == QAudio.State.IdleState and self.ws_client and self.ws_client.ws:
            with QMutexLocker(self.audio_device.mutex):
                buffer_size = len(self.audio_device.audio_buffer)
                is_end_of_stream = self.audio_device.end_of_stream
                logger.info(f"State change to Idle - Buffer size: {buffer_size}, End of stream: {is_end_of_stream}")
                if buffer_size == 0 and is_end_of_stream:
                    logger.info("Audio playback finished, sending playback-complete message to server...")
                    asyncio.run(self.ws_client.ws.send(json.dumps({
                        "action": "playback-complete"
                    })))
                    logger.info("Playback-complete message sent to server")
                    self.audio_device.end_of_stream = False
                    self.audio_device.last_read_empty = False

    def apply_styling(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLORS['background']};
            }}
            QScrollArea {{
                border: none;
                background-color: {COLORS['background']};
            }}
            QScrollBar:vertical {{
                border: none;
                background: {COLORS['background']};
                width: 10px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['input_border']};
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
                width: 0;
                background: none;
                border: none;
            }}
            QWidget {{
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
                padding: 5px;
                font-weight: bold;
                font-size: 13px;
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
            /* Specific rule for the STT button when listening */
            QPushButton#sttButton[isListening="true"] {{
                background-color: red !important;
                color: white !important;
                border: none;
                border-radius: 10px;
            }}
        """)
        palette = self.text_input.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(COLORS['text_secondary']))
        self.text_input.setPalette(palette)

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        global COLORS
        COLORS = DARK_COLORS if self.is_dark_mode else LIGHT_COLORS
        icon_path = "/home/jack/humptyprompty/frontend/icons/light_mode_24dp_E8EAED.svg" if self.is_dark_mode else "/home/jack/humptyprompty/frontend/icons/dark_mode_24dp_E8EAED.svg"
        self.theme_toggle.setIcon(QIcon(icon_path))
        self.chat_area.setStyleSheet(f"background-color: {COLORS['background']};")
        scroll_area = self.findChild(QScrollArea)
        scroll_area.setStyleSheet(f"background-color: {COLORS['background']};")
        for i in range(self.chat_layout.count()):
            widget = self.chat_layout.itemAt(i).widget()
            if widget and widget.__class__.__name__ == "MessageBubble":
                is_user = widget.property("isUser")
                if is_user:
                    widget.setStyleSheet(f"""
                        QFrame#messageBubble {{
                            background-color: {COLORS['user_bubble']};
                            border-radius: 15px;
                            margin: 5px 50px 5px 5px;
                            padding: 5px;
                        }}
                        QLabel {{
                            color: {COLORS['text_primary']};
                            font-size: 14px;
                            background-color: transparent;
                        }}
                    """)
                else:
                    widget.setStyleSheet(f"""
                        QFrame#messageBubble {{
                            background-color: {COLORS['background']};
                            margin: 5px 5px 5px 50px;
                            padding: 5px;
                        }}
                        QLabel {{
                            color: {COLORS['text_primary']};
                            font-size: 14px;
                            background-color: transparent;
                        }}
                    """)
        self.apply_styling()

    def send_message(self):
        text = self.text_input.toPlainText().strip()
        if text:
            try:
                self.finalize_assistant_bubble()
                self.add_message(text, True)
                asyncio.run(self.ws_client.send_message(text))
                self.text_input.clear()
            except Exception as e:
                logger.error(f"Error sending message: {e}")

    def handle_message(self, token):
        if not self.assistant_bubble_in_progress:
            self.assistant_bubble_in_progress = MessageBubble("", is_user=False)
            self.assistant_bubble_in_progress.setStyleSheet(f"""
                QFrame#messageBubble {{
                    background-color: {COLORS['background']};
                    margin: 5px 5px 5px 50px;
                    padding: 5px;
                }}
                QLabel {{
                    color: {COLORS['text_primary']};
                    font-size: 14px;
                    background-color: transparent;
                }}
            """)
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

    def handle_tts_state_changed(self, is_enabled: bool):
        self.tts_enabled = is_enabled
        self.toggle_tts_button.setText("TTS On" if is_enabled else "TTS Off")

    def handle_stt_state(self, is_listening: bool):
        # This handler is connected to stt_state_received and updates the actual listening state.
        self.stt_listening = is_listening
        self.update_stt_button_style()

    def add_message(self, text, is_user):
        bubble = MessageBubble(text, is_user)
        if is_user:
            bubble.setStyleSheet(f"""
                QFrame#messageBubble {{
                    background-color: {COLORS['user_bubble']};
                    border-radius: 15px;
                    margin: 5px 50px 5px 5px;
                    padding: 5px;
                }}
                QLabel {{
                    color: {COLORS['text_primary']};
                    font-size: 14px;
                    background-color: transparent;
                }}
            """)
        else:
            bubble.setStyleSheet(f"""
                QFrame#messageBubble {{
                    background-color: {COLORS['background']};
                    margin: 5px 5px 5px 50px;
                    padding: 5px;
                }}
                QLabel {{
                    color: {COLORS['text_primary']};
                    font-size: 14px;
                    background-color: transparent;
                }}
            """)
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

    def update_stt_button_style(self):
        # Update the STT button by setting its "isListening" property based on the actual listening state.
        self.toggle_stt_button.setProperty("isListening", "true" if self.stt_listening else "false")
        self.toggle_stt_button.style().unpolish(self.toggle_stt_button)
        self.toggle_stt_button.style().polish(self.toggle_stt_button)

    def toggle_stt(self):
        self.is_toggling_stt = True
        try:
            if not self.stt_enabled:
                # Use WebSocket to start STT and initiate listening
                if self.ws_client.ws:
                    asyncio.run(self.ws_client.ws.send(json.dumps({"action": "start-stt"})))
                    self.stt_enabled = True
                else:
                    logger.error("WebSocket is not connected; cannot start STT.")
            else:
                # Use WebSocket to pause STT and stop listening
                if self.ws_client.ws:
                    asyncio.run(self.ws_client.ws.send(json.dumps({"action": "pause-stt"})))
                    self.stt_enabled = False
                else:
                    logger.error("WebSocket is not connected; cannot pause STT.")
            self.toggle_stt_button.setText("STT On" if self.stt_enabled else "STT Off")
            # Do not update style directly here; wait for backend broadcast to update self.stt_listening.
        except Exception as e:
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
                self.audio_device.audio_buffer.clear()
                while not self.audio_queue.empty():
                    try:
                        self.audio_queue.get_nowait()
                    except:
                        pass
                self.audio_queue.put_nowait(None)
            self.toggle_tts_button.setText("TTS On" if self.tts_enabled else "TTS Off")
        except requests.RequestException as e:
            logger.error(f"Error toggling TTS: {e}")
        finally:
            self.is_toggling_tts = False

    def stop_tts_and_generation(self):
        try:
            requests.post(f"{HTTP_BASE_URL}/api/stop-tts").raise_for_status()
            requests.post(f"{HTTP_BASE_URL}/api/stop-generation").raise_for_status()
            with QMutexLocker(self.audio_device.mutex):
                self.audio_device.clear_buffer()
                self.audio_device.mark_end_of_stream()
                while not self.audio_queue.empty():
                    try:
                        self.audio_queue.get_nowait()
                    except:
                        pass
                self.audio_queue.put_nowait(None)
        except requests.RequestException as e:
            logger.error(f"Error stopping TTS and generation: {e}")
        self.finalize_assistant_bubble()

    def on_audio_received(self, pcm_data: bytes):
        logger.info(f"Frontend: Processing audio chunk of size: {len(pcm_data)} bytes")
        if pcm_data == b'audio:' or len(pcm_data) == 0:
            logger.info("Frontend: Received empty audio message, marking end of stream")
            self.audio_queue.put_nowait(None)
            self.audio_device.mark_end_of_stream()
        else:
            prefix = b'audio:'
            if pcm_data.startswith(prefix):
                pcm_data = pcm_data[len(prefix):]
            self.audio_queue.put_nowait(pcm_data)

    def feed_audio_data(self):
        current_state = self.audio_sink.state()
        if current_state != QAudio.State.ActiveState:
            logger.warning(f"Warning: Audio sink not active! Current state: {current_state}")
            self.audio_sink.start(self.audio_device)
            return
        try:
            while True:
                try:
                    pcm_chunk = self.audio_queue.get_nowait()
                    if pcm_chunk is None:
                        logger.info("Received end-of-stream marker in feed_audio_data")
                        self.audio_device.mark_end_of_stream()
                        if len(self.audio_device.audio_buffer) == 0:
                            logger.info("Buffer empty at end-of-stream, stopping audio sink")
                            self.audio_sink.stop()
                        break
                    bytes_written = self.audio_device.writeData(pcm_chunk)
                    logger.debug(f"Wrote {bytes_written} bytes to audio device")
                except asyncio.QueueEmpty:
                    break
        except Exception as e:
            logger.error(f"Error in feed_audio_data: {e}")
            logger.exception("Stack trace:")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.toggle_kiosk_mode()
        super().keyPressEvent(event)

    def toggle_kiosk_mode(self):
        self.is_kiosk_mode = not self.is_kiosk_mode
        if self.is_kiosk_mode:
            self.normal_geometry = self.geometry()
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.centralWidget().layout().setContentsMargins(5, 0, 5, 5)
        else:
            self.setWindowFlags(self.normal_window_flags)
            self.setGeometry(self.normal_geometry)
            self.centralWidget().layout().setContentsMargins(5, 5, 5, 5)
        self.show()
        QTimer.singleShot(100, self.auto_scroll_chat)

    # --- Toggle playback method ---
    def toggle_playback(self):
        try:
            resp = requests.post(f"{HTTP_BASE_URL}/api/toggle-playback-location")
            resp.raise_for_status()
            new_state = resp.json().get("playback_location", None)
            if new_state:
                self.playback_location = new_state
                if self.playback_location == "backend":
                    self.toggle_playback_button.setText("FRONT PLAY")
                else:
                    self.toggle_playback_button.setText("BACK PLAY")
                logger.info(f"Playback location toggled to {self.playback_location}")
            else:
                logger.error("No playback_location returned from toggle endpoint")
        except Exception as e:
            logger.error(f"Error toggling playback location: {e}")

# ----------------------- MAIN -----------------------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ChatWindow()
    window.apply_styling()
    window.show()
    sys.exit(app.exec())
