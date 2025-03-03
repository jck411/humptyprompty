#!/usr/bin/env python3
import sys
import json
import asyncio
import logging
import os

import aiohttp
import websockets

# PyQt6 Imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QScrollArea, QSizePolicy, QTextEdit, QFrame, QLabel
)
from PyQt6.QtCore import (
    Qt, QTimer, QSize, QMutex, QMutexLocker, QIODevice, pyqtSignal, QObject
)
from PyQt6.QtGui import (
    QColor, QPalette, QIcon
)
from PyQt6.QtMultimedia import (
    QAudioFormat, QAudioSink, QMediaDevices, QAudio
)

# qasync integration
from qasync import QEventLoop

# Import your frontend STT implementation
from frontend.stt.deepgram_stt import DeepgramSTT

# Add this import for task cancellation handling
import asyncio.exceptions

# -----------------------------------------------------------------------------
#                           1. CONFIGURATION & LOGGING
# -----------------------------------------------------------------------------

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
WEBSOCKET_PATH = "/ws/chat"
HTTP_BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
ch = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

# -----------------------------------------------------------------------------
#                             2. THEMING & COLORS
# -----------------------------------------------------------------------------

DARK_COLORS = {
    "background": "#1a1b26", 
    "user_bubble": "#3b4261", 
    "assistant_bubble": "transparent", 
    "text_primary": "#a9b1d6", 
    "text_secondary": "#565f89", 
    "button_primary": "#7aa2f7", 
    "button_hover": "#3d59a1", 
    "button_pressed": "#2ac3de", 
    "input_background": "#24283b", 
    "input_border": "#414868"
}

LIGHT_COLORS = {
    "background": "#E8EEF5",
    "user_bubble": "#D0D7E1", 
    "assistant_bubble": "#F7F9FB", 
    "text_primary": "#1C1E21", 
    "text_secondary": "#65676B", 
    "button_primary": "#0D8BD9", 
    "button_hover": "#0A6CA8", 
    "button_pressed": "#084E7A", 
    "input_background": "#FFFFFF", 
    "input_border": "#D3D7DC"
}

# No longer using global COLORS - each component manages its own theme

def generate_main_stylesheet(colors):
    return f"""
    QWidget {{
        font-family: 'DejaVu Sans', 'sans-serif';
        background-color: {colors['background']};
    }}
    QMainWindow {{
        background-color: {colors['background']};
    }}
    QScrollArea {{
        border: none;
        background-color: {colors['background']};
    }}
    QScrollBar:vertical {{
        border: none;
        background: {colors['background']};
        width: 10px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {colors['input_border']};
        border-radius: 5px;
        min-height: 20px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
        width: 0;
        background: none;
        border: none;
    }}
    QTextEdit {{
        border: 1px solid {colors['input_border']};
        border-radius: 20px;
        padding: 10px;
        background-color: {colors['input_background']};
        color: {colors['text_primary']};
        font-size: 14px;
    }}
    QPushButton {{
        border: none;
        border-radius: 25px;
        background-color: {colors['button_primary']};
        color: white;
        padding: 5px;
        font-weight: bold;
        font-size: 13px;
    }}
    QPushButton:hover {{
        background-color: {colors['button_hover']};
    }}
    QPushButton:pressed {{
        background-color: {colors['button_pressed']};
    }}
    QLabel {{
        color: {colors['text_primary']};
        font-size: 14px;
    }}
    QPushButton#sttButton[isListening="true"] {{
        background-color: red !important;
        color: white !important;
        border: none;
        border-radius: 10px;
    }}
    """

def get_message_bubble_stylesheet(is_user, colors):
    if is_user:
        return f"""
            QFrame#messageBubble {{
                background-color: {colors['user_bubble']};
                border-radius: 15px;
                margin: 5px 50px 5px 5px;
                padding: 5px;
            }}
            QLabel {{
                color: {colors['text_primary']};
                font-size: 14px;
                background-color: transparent;
            }}
        """
    else:
        return f"""
            QFrame#messageBubble {{
                background-color: {colors['assistant_bubble']};
                margin: 5px 5px 5px 50px;
                padding: 5px;
            }}
            QLabel {{
                color: {colors['text_primary']};
                font-size: 14px;
                background-color: transparent;
            }}
        """

# -----------------------------------------------------------------------------
#                         3. COMPONENTS & HELPER WIDGETS
# -----------------------------------------------------------------------------

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
        """
        Override keyPressEvent to allow sending messages when pressing
        Enter without Shift.
        """
        if event.key() == Qt.Key.Key_Return and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            main_window = self.window()
            if hasattr(main_window, "send_message"):
                main_window.send_message()
        else:
            super().keyPressEvent(event)

# -----------------------------------------------------------------------------
#                         4. ASYNC WEBSOCKET CLIENT
# -----------------------------------------------------------------------------

class AsyncWebSocketClient(QObject):
    message_received = pyqtSignal(str)
    stt_text_received = pyqtSignal(str)
    stt_state_received = pyqtSignal(bool)
    connection_status = pyqtSignal(bool)
    audio_received = pyqtSignal(bytes)
    tts_state_changed = pyqtSignal(bool)

    def __init__(self, server_host, server_port, websocket_path):
        super().__init__()
        self.server_host = server_host
        self.server_port = server_port
        self.websocket_path = websocket_path
        self.ws = None
        self.running = True
        self.messages = []

    async def connect(self):
        ws_url = f"ws://{self.server_host}:{self.server_port}{self.websocket_path}"
        try:
            self.ws = await websockets.connect(ws_url)
            self.connection_status.emit(True)
            logger.info(f"Connected to {ws_url}")

            while self.running:
                try:
                    message = await self.ws.recv()
                    if isinstance(message, bytes):
                        # Audio data check
                        if message.startswith(b'audio:'):
                            audio_data = message[len(b'audio:'):]
                            logger.debug(f"Received audio chunk of size: {len(audio_data)} bytes")
                            self.audio_received.emit(message)
                        else:
                            logger.warning("Received binary message without audio prefix")
                            self.audio_received.emit(b'audio:' + message)
                    else:
                        try:
                            data = json.loads(message)
                            logger.debug(f"Received message: {data}")
                            
                            msg_type = data.get("type")
                            if msg_type == "stt":
                                stt_text = data.get("stt_text", "")
                                logger.debug(f"Processing STT text immediately: {stt_text}")
                                self.stt_text_received.emit(stt_text)
                            elif msg_type == "stt_state":
                                is_listening = data.get("is_listening", False)
                                logger.debug(f"Updating STT state: listening = {is_listening}")
                                self.stt_state_received.emit(is_listening)
                            elif "content" in data:
                                self.message_received.emit(data["content"])
                            else:
                                logger.warning(f"Unknown message type: {data}")
                        except json.JSONDecodeError:
                            logger.error("Failed to parse JSON message")
                            logger.error(f"Raw message: {message}")
                except Exception as e:
                    logger.error(f"WebSocket message processing error: {e}")
                    await asyncio.sleep(0.1)
                    continue
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
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

# -----------------------------------------------------------------------------
#                             5. AUDIO SETUP
# -----------------------------------------------------------------------------

class QueueAudioDevice(QIODevice):
    """
    QIODevice subclass to handle audio data in a buffer queue.
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
        # Explicitly prevent seek operations
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
        with QMutexLocker(self.mutex):
            logger.info(f"[QueueAudioDevice] Marking end of stream, current buffer size: {len(self.audio_buffer)}")
            self.end_of_stream = True
            if len(self.audio_buffer) == 0:
                self.last_read_empty = True
                logger.info("[QueueAudioDevice] Buffer empty at end-of-stream mark")

    def clear_buffer(self):
        with QMutexLocker(self.mutex):
            self.audio_buffer.clear()
            self.end_of_stream = False
            self.last_read_empty = False
            logger.info("[QueueAudioDevice] Audio buffer cleared and state reset")

def setup_audio():
    """
    Sets up the audio output device and starts the QAudioSink with a
    QueueAudioDevice. Adjust sample rates/formats as needed.
    """
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

# -----------------------------------------------------------------------------
#                          6. MAIN CHAT WINDOW CLASS
# -----------------------------------------------------------------------------

class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Basic Window Setup
        self.setWindowTitle("Modern Chat Interface")
        self.setMinimumSize(800, 600)
        self.is_dark_mode = True
        
        # Theme management - store theme locally instead of using global
        self.colors = DARK_COLORS

        # UI State Fields
        self.assistant_text_in_progress = ""
        self.assistant_bubble_in_progress = None
        self.stt_listening = True
        self.stt_enabled = True
        self.is_toggling_stt = False
        self.is_toggling_tts = False

        # Initialize Qt Layout and main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.main_layout = QVBoxLayout(main_widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(2)

        # Prepare Deepgram-based STT
        self.frontend_stt = DeepgramSTT()

        # Set up top bar, chat area, and input area
        self.setup_top_buttons_layout()
        self.setup_chat_area_layout()
        self.setup_input_area_layout()

        # Prepare WebSocket and Audio
        self.setup_websocket()
        self.setup_audio()

        # Initial Theming
        self.apply_styling()
        
        # Connect STT signals
        self.frontend_stt.transcription_received.connect(self.handle_frontend_stt_text)
        self.frontend_stt.state_changed.connect(self.handle_frontend_stt_state)

        # Initialize TTS State from server
        QTimer.singleShot(0, lambda: asyncio.create_task(self._init_states_async()))
        self.theme_toggle.setIcon(QIcon("frontend/icons/light_mode.svg"))

        # Optionally start STT automatically
        QTimer.singleShot(0, self.toggle_stt)

        # Store tasks to prevent them from being garbage collected
        self.async_tasks = []
        
        # Defer the creation of async tasks until the event loop is running
        # Use a slightly longer delay for the audio_consumer to ensure the websocket is connected first
        QTimer.singleShot(0, self.create_async_tasks)

    def create_async_tasks(self):
        """Create and store async tasks to prevent garbage collection and task conflicts"""
        # Create the audio consumer task
        self.async_tasks.append(asyncio.create_task(self.audio_consumer()))
        logger.info("Created audio_consumer task")

    async def _init_states_async(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{HTTP_BASE_URL}/api/toggle-tts") as resp:
                    data = await resp.json()
                    self.tts_enabled = data.get("tts_enabled", False)
                    logger.info(f"Initial TTS state: {self.tts_enabled}")
        except Exception as e:
            logger.error(f"Error getting initial TTS state: {e}")
            self.tts_enabled = False
        self.is_toggling_tts = False

    # -------------------------- Layout Setup Methods --------------------------

    def setup_top_buttons_layout(self):
        self.top_widget = QWidget()
        top_layout = QHBoxLayout(self.top_widget)
        top_layout.setContentsMargins(0, 5, 0, 0)
        top_layout.setSpacing(5)
        
        # Left Buttons
        left_buttons = QWidget()
        left_layout = QHBoxLayout(left_buttons)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)
        
        self.toggle_stt_button = QPushButton("STT Off")
        self.toggle_stt_button.setFixedSize(120, 40)
        self.toggle_stt_button.setObjectName("sttButton")
        self.toggle_stt_button.setProperty("isListening", False)
        self.toggle_stt_button.clicked.connect(self.toggle_stt)

        self.toggle_tts_button = QPushButton("TTS On" if getattr(self, 'tts_enabled', False) else "TTS Off")
        self.toggle_tts_button.setFixedSize(120, 40)

        self.clear_chat_button = QPushButton("CLEAR")
        self.clear_chat_button.setFixedSize(120, 40)
        self.clear_chat_button.clicked.connect(self.clear_chat_history)

        left_layout.addWidget(self.toggle_stt_button)
        left_layout.addWidget(self.toggle_tts_button)
        left_layout.addWidget(self.clear_chat_button)
        left_layout.addStretch()
        top_layout.addWidget(left_buttons, stretch=1)

        # Theme Toggle Button
        self.theme_toggle = QPushButton()
        self.theme_toggle.setFixedSize(45, 45)
        self.theme_toggle.setIcon(QIcon("frontend/icons/dark_mode.svg"))
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

        # Finalize top widget
        self.main_layout.addWidget(self.top_widget)
        self.toggle_tts_button.clicked.connect(lambda: asyncio.create_task(self.toggle_tts_async()))

    def setup_chat_area_layout(self):
        self.chat_area = QWidget()
        self.chat_area.setAutoFillBackground(True)
        self.chat_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        chat_palette = self.chat_area.palette()
        chat_palette.setColor(QPalette.ColorRole.Window, QColor(self.colors['background']))
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
        scroll_palette.setColor(QPalette.ColorRole.Window, QColor(self.colors['background']))
        scroll.setPalette(scroll_palette)

        self.main_layout.addWidget(scroll, stretch=1)

    def setup_input_area_layout(self):
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
        send_button.setIcon(QIcon("frontend/icons/send.svg"))
        send_button.setIconSize(QSize(24, 24))

        self.stop_all_button = QPushButton()
        self.stop_all_button.setFixedSize(50, 50)
        self.stop_all_button.setIcon(QIcon("frontend/icons/stop_all.svg"))
        self.stop_all_button.setIconSize(QSize(30, 30))

        button_layout.addWidget(send_button)
        button_layout.addWidget(self.stop_all_button)

        input_layout.addWidget(self.text_input, stretch=1)
        input_layout.addWidget(button_widget)

        self.main_layout.addWidget(input_widget)
        send_button.clicked.connect(self.send_message)
        self.text_input.textChanged.connect(self.adjust_text_input_height)
        self.stop_all_button.clicked.connect(lambda: asyncio.create_task(self.stop_tts_and_generation_async()))

    # -------------------------- Setup Methods --------------------------

    def setup_websocket(self):
        self.ws_client = AsyncWebSocketClient(SERVER_HOST, SERVER_PORT, WEBSOCKET_PATH)
        self.ws_client.message_received.connect(self.handle_message)
        self.ws_client.connection_status.connect(self.handle_connection_status)
        self.ws_client.audio_received.connect(self.on_audio_received)
        self.ws_client.tts_state_changed.connect(self.handle_tts_state_changed)
        
        # Store the websocket connection task to prevent it from being garbage collected
        # and to ensure it's properly managed
        if hasattr(self, 'async_tasks'):
            self.async_tasks.append(asyncio.create_task(self.ws_client.connect()))
        else:
            # This should not happen, but just in case setup_websocket is called before __init__ completes
            QTimer.singleShot(0, lambda: asyncio.create_task(self.ws_client.connect()))

    def setup_audio(self):
        self.audio_sink, self.audio_device = setup_audio()
        self.audio_sink.stateChanged.connect(self.handle_audio_state_changed)
        # This asyncio.Queue will be consumed by self.audio_consumer()
        self.audio_queue = asyncio.Queue()
        logger.info("Audio setup completed, using async consumer loop")

    # -------------------------- Theming --------------------------

    def apply_styling(self):
        # One-stop shop for setting all style info
        self.setStyleSheet(generate_main_stylesheet(self.colors))
        
        # Style the chat area and scroll area
        self.chat_area.setStyleSheet(f"background-color: {self.colors['background']};")
        scroll_area = self.findChild(QScrollArea)
        scroll_area.setStyleSheet(f"background-color: {self.colors['background']};")
        
        # Update text input placeholder color
        palette = self.text_input.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(self.colors['text_secondary']))
        self.text_input.setPalette(palette)
        
        # Update all message bubbles
        for i in range(self.chat_layout.count()):
            widget = self.chat_layout.itemAt(i).widget()
            if widget and widget.__class__.__name__ == "MessageBubble":
                is_user = widget.property("isUser")
                widget.setStyleSheet(get_message_bubble_stylesheet(is_user, self.colors))

    def toggle_theme(self):
        """
        Switch between DARK_COLORS and LIGHT_COLORS. Re-apply styles to all
        relevant widgets and message bubbles.
        """
        self.is_dark_mode = not self.is_dark_mode
        self.colors = DARK_COLORS if self.is_dark_mode else LIGHT_COLORS

        # Update theme toggle button icon
        icon_path = "frontend/icons/light_mode.svg" if self.is_dark_mode else "frontend/icons/dark_mode.svg"
        self.theme_toggle.setIcon(QIcon(icon_path))
        
        # Apply all styling changes
        self.apply_styling()

    # -------------------------- Chat Logic --------------------------

    def send_message(self):
        text = self.text_input.toPlainText().strip()
        if text:
            try:
                self.finalize_assistant_bubble()
                self.add_message(text, True)
                asyncio.create_task(self.ws_client.send_message(text))
                self.text_input.clear()
            except Exception as e:
                logger.error(f"Error sending message: {e}")

    def handle_message(self, token):
        # Accumulate token in the "assistant bubble in progress"
        if not self.assistant_bubble_in_progress:
            self.assistant_bubble_in_progress = MessageBubble("", is_user=False)
            self.assistant_bubble_in_progress.setStyleSheet(get_message_bubble_stylesheet(False, self.colors))
            self.chat_layout.insertWidget(self.chat_layout.count() - 1, self.assistant_bubble_in_progress)

        self.assistant_text_in_progress += token
        self.assistant_bubble_in_progress.update_text(self.assistant_text_in_progress)
        self.auto_scroll_chat()

    def finalize_assistant_bubble(self):
        """
        Once an assistant response is complete, store it in the WebSocket client's
        message log and reset in-progress text/bubbles.
        """
        if self.assistant_bubble_in_progress:
            self.ws_client.handle_assistant_message(self.assistant_text_in_progress)
            self.assistant_text_in_progress = ""
            self.assistant_bubble_in_progress = None

    def add_message(self, text, is_user):
        bubble = MessageBubble(text, is_user)
        bubble.setStyleSheet(get_message_bubble_stylesheet(is_user, self.colors))
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        self.auto_scroll_chat()

    def auto_scroll_chat(self):
        QApplication.processEvents()
        scroll_area = self.findChild(QScrollArea)
        vsb = scroll_area.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    def clear_chat_history(self):
        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.chat_layout.addStretch()
        self.assistant_text_in_progress = ""
        self.assistant_bubble_in_progress = None
        self.ws_client.messages.clear()
        logger.info("Chat history cleared, starting with a blank slate.")

    # -------------------------- STT Handling --------------------------

    def toggle_stt(self):
        """
        Toggle global STT using the frontend implementation.
        """
        if self.is_toggling_stt:
            return
        
        self.is_toggling_stt = True
        try:
            if hasattr(self.frontend_stt, 'toggle'):
                # Use the existing toggle method
                self.frontend_stt.toggle()
                # Update UI state to reflect the opposite of current state
                self.handle_frontend_stt_state(not self.stt_listening)
            else:
                logger.error("Frontend STT implementation missing toggle method")
                # Still update the UI state as a fallback
                self.handle_frontend_stt_state(not self.stt_listening)
        except asyncio.exceptions.CancelledError:
            logger.warning("STT toggle task was cancelled - this is expected during shutdown")
        except Exception as e:
            logger.error(f"Error toggling STT: {e}")
            # Update UI state as a fallback
            self.handle_frontend_stt_state(not self.stt_listening)
        finally:
            self.is_toggling_stt = False

    def handle_frontend_stt_text(self, text):
        """
        Called when the frontend STT engine returns a chunk of recognized text.
        """
        if text.strip():
            print(f"Frontend STT text: {text}")
            self.text_input.setPlainText(text)
            self.adjust_text_input_height()

    def handle_frontend_stt_state(self, is_listening):
        """
        Update UI to reflect the STT listening state.
        """
        try:
            self.stt_listening = is_listening
            self.toggle_stt_button.setText(f"STT {'On' if is_listening else 'Off'}")
            self.toggle_stt_button.setProperty("isListening", is_listening)
            
            # Force style update
            style = self.toggle_stt_button.style()
            if style:
                style.unpolish(self.toggle_stt_button)
                style.polish(self.toggle_stt_button)
            
            self.toggle_stt_button.update()
        except asyncio.exceptions.CancelledError:
            logger.warning("STT state update task was cancelled - this is expected during shutdown")
        except Exception as e:
            logger.error(f"Error updating STT state in UI: {e}")

    # -------------------------- TTS Handling --------------------------

    async def toggle_tts_async(self):
        self.is_toggling_tts = True
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{HTTP_BASE_URL}/api/toggle-tts") as resp:
                    data = await resp.json()
                    self.tts_enabled = data.get("tts_enabled", self.tts_enabled)

                # If TTS was turned off, properly clean up audio resources
                if not self.tts_enabled:
                    # Stop server-side TTS first
                    async with session.post(f"{HTTP_BASE_URL}/api/stop-tts") as stop_resp:
                        await stop_resp.json()
                    
                    # Clean up audio sink
                    if self.audio_sink.state() != QAudio.State.StoppedState:
                        self.audio_sink.stop()
                    
                    # Clean up audio device
                    if self.audio_device.is_active:
                        self.audio_device.close()
                    
                    # Clear buffers
                    with QMutexLocker(self.audio_device.mutex):
                        self.audio_device.audio_buffer.clear()
                        self.audio_device.end_of_stream = False
                    
                    # Clear queue
                    while not self.audio_queue.empty():
                        try:
                            self.audio_queue.get_nowait()
                        except:
                            pass
                    
                    # Reinitialize audio device for next use
                    self.audio_device.open(QIODevice.OpenModeFlag.ReadOnly)
                    self.audio_sink.start(self.audio_device)

                self.toggle_tts_button.setText("TTS On" if self.tts_enabled else "TTS Off")
        except Exception as e:
            logger.error(f"Error toggling TTS: {e}")
        finally:
            self.is_toggling_tts = False

    def handle_tts_state_changed(self, is_enabled: bool):
        """
        If the server changes TTS state, reflect it here.
        """
        self.tts_enabled = is_enabled
        self.toggle_tts_button.setText("TTS On" if is_enabled else "TTS Off")

    async def stop_tts_and_generation_async(self):
        logger.info("Stop button pressed - stopping TTS and generation")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{HTTP_BASE_URL}/api/stop-tts") as resp1:
                    resp1_data = await resp1.json()
                    logger.info(f"Stop TTS response: {resp1_data}")

                async with session.post(f"{HTTP_BASE_URL}/api/stop-generation") as resp2:
                    resp2_data = await resp2.json()
                    logger.info(f"Stop generation response: {resp2_data}")
        except Exception as e:
            logger.error(f"Error stopping TTS and generation on server: {e}")

        # Clean up audio playback
        logger.info("Cleaning frontend audio resources")
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

        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self.audio_queue.put_nowait(None)
        logger.info("End-of-stream marker placed in audio queue; audio resources cleaned up")

        logger.info("Finalizing assistant bubble")
        self.finalize_assistant_bubble()

    # -------------------------- Asynchronous Audio Consumer --------------------------

    async def audio_consumer(self):
        """
        An async loop that continuously reads audio chunks from `self.audio_queue`
        and writes them to the `QueueAudioDevice`. Eliminates the need for
        QTimer-based polling.
        """
        logger.info("[audio_consumer] Starting async audio loop")
        while True:
            try:
                pcm_chunk = await self.audio_queue.get()
                if pcm_chunk is None:
                    # End-of-stream
                    logger.info("[audio_consumer] Received end-of-stream marker.")
                    self.audio_device.mark_end_of_stream()

                    # Wait for the device to play the remainder
                    while True:
                        with QMutexLocker(self.audio_device.mutex):
                            buffer_len = len(self.audio_device.audio_buffer)
                        if buffer_len == 0:
                            logger.info("[audio_consumer] Audio buffer is empty, stopping sink.")
                            self.audio_sink.stop()
                            break
                        await asyncio.sleep(0.05)

                    # Let the server know we're done playing audio
                    if self.ws_client and self.ws_client.ws:
                        await self.ws_client.ws.send(json.dumps({"action": "playback-complete"}))
                        logger.info("[audio_consumer] Sent playback-complete to server")

                    # Reset end_of_stream
                    with QMutexLocker(self.audio_device.mutex):
                        self.audio_device.end_of_stream = False
                        self.audio_device.last_read_empty = False
                    continue

                # If sink is not active, attempt to restart
                if self.audio_sink.state() != QAudio.State.ActiveState:
                    logger.debug("[audio_consumer] Restarting audio sink from non-active state.")
                    self.audio_device.close()
                    self.audio_device.open(QIODevice.OpenModeFlag.ReadOnly)
                    self.audio_sink.start(self.audio_device)

                # Write chunk to device
                bytes_written = self.audio_device.writeData(pcm_chunk)
                logger.debug(f"[audio_consumer] Wrote {bytes_written} bytes to device.")
            
            except Exception as e:
                logger.error(f"[audio_consumer] Error: {e}")
                await asyncio.sleep(0.05)

    # -------------------------- Audio & WS Handlers --------------------------

    def on_audio_received(self, pcm_data: bytes):
        logger.info(f"Received audio chunk of size: {len(pcm_data)} bytes")
        if pcm_data == b'audio:' or len(pcm_data) == 0:
            logger.info("Received empty audio message, marking end of stream")
            self.audio_queue.put_nowait(None)
            self.audio_device.mark_end_of_stream()
        else:
            prefix = b'audio:'
            if pcm_data.startswith(prefix):
                pcm_data = pcm_data[len(prefix):]
            self.audio_queue.put_nowait(pcm_data)

    def handle_audio_state_changed(self, state):
        logger.info(f"[handle_audio_state_changed] Audio state changed to: {state}")
        with QMutexLocker(self.audio_device.mutex):
            buffer_size = len(self.audio_device.audio_buffer)
            is_end_of_stream = self.audio_device.end_of_stream
        logger.info(f"[handle_audio_state_changed] Buffer size: {buffer_size}, End of stream: {is_end_of_stream}")

    # -------------------------- Connection Status --------------------------

    def handle_connection_status(self, connected):
        self.setWindowTitle(f"Modern Chat Interface - {'Connected' if connected else 'Disconnected'}")

    # -------------------------- Misc UI Helpers --------------------------

    def adjust_text_input_height(self):
        doc_height = self.text_input.document().size().height()
        new_height = min(max(50, doc_height + 20), 100)
        self.text_input.setFixedHeight(int(new_height))

    def keyPressEvent(self, event):
        super().keyPressEvent(event)

    def closeEvent(self, event):
        """
        Handle application shutdown when the window is closed.
        
        This method uses the "fire and forget" approach for cleanup operations
        since we're shutting down the application and don't need to wait for
        cleanup to complete before proceeding.
        """
        logger.info("Closing application...")
        
        # Stop the websocket client
        if hasattr(self, 'ws_client') and self.ws_client:
            self.ws_client.running = False
        
        # Stop STT if it's running - using the synchronous "fire and forget" method
        # which is appropriate for application shutdown as we don't need to block
        # waiting for cleanup to complete
        #
        # NOTE: This is the ONLY place where frontend_stt.stop() should be called!
        # For all other cases where STT needs to be stopped, use the async methods
        # (either set_enabled(False) or stop_async()) to ensure proper cleanup.
        if hasattr(self, 'frontend_stt') and self.frontend_stt:
            self.frontend_stt.stop()
        
        # Cancel all async tasks
        if hasattr(self, 'async_tasks'):
            for task in self.async_tasks:
                if not task.done():
                    task.cancel()
        
        # Cancel audio task if it exists
        try:
            if hasattr(self, 'audio_task') and self.audio_task:
                self.audio_task.cancel()
        except Exception as e:
            logger.error(f"Error cancelling audio task: {e}")
            
        # Let the parent class handle the rest of the shutdown process
        super().closeEvent(event)

# -----------------------------------------------------------------------------
#                                   7. MAIN
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = ChatWindow()
    window.apply_styling()
    window.show()

    # Ensure the event loop is properly set up before running
    try:
        with loop:
            loop.run_forever()
    except KeyboardInterrupt:
        # Handle clean shutdown on Ctrl+C
        logger.info("Keyboard interrupt received, shutting down...")
    finally:
        # Ensure all tasks are properly cleaned up
        logger.info("Cleaning up before exit")
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
