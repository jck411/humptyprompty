#!/usr/bin/env python3
import sys
import json
import asyncio
import logging

import websockets
import aiohttp

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QScrollArea, QFrame, QLabel
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QIODevice, QMutex, QMutexLocker, QSize
from PyQt6.QtGui import QColor, QPalette, QIcon
from PyQt6.QtMultimedia import (
    QAudioFormat,
    QAudioSink,
    QMediaDevices,
    QAudio,
)

# ===================== Logging Configuration =====================
LOG_LEVEL = logging.WARNING
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ===================== Server Configuration =====================
SERVER_HOST = "192.168.1.226"  # <-- CHANGE THIS
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
    # Existing signals
    message_received = pyqtSignal(str)
    stt_text_received = pyqtSignal(str)
    connection_status = pyqtSignal(bool)
    audio_received = pyqtSignal(bytes)
    tts_state_changed = pyqtSignal(bool)

    # New signals for asynchronous button operations
    stt_toggled = pyqtSignal(bool)        # Emitted after STT on/off
    tts_toggled = pyqtSignal(bool)        # Emitted after TTS on/off
    playback_toggled = pyqtSignal(str)    # Emitted after playback location changes
    all_stopped = pyqtSignal()            # Emitted after stop-tasks
    http_error = pyqtSignal(str)          # Emitted on HTTP error

    def __init__(self):
        super().__init__()
        self.ws = None
        self.running = True
        self.messages = []

        # Track the event loop so we can schedule tasks on it
        self.loop = None

    async def connect(self):
        """ Main coroutine that runs in this QThread """
        ws_url = f"ws://{SERVER_HOST}:{SERVER_PORT}{WEBSOCKET_PATH}"
        try:
            self.loop = asyncio.get_running_loop()

            # 1) Connect the WebSocket
            self.ws = await websockets.connect(ws_url)
            self.connection_status.emit(True)
            logger.info(f"Frontend: WebSocket connected to {ws_url}")

            # 2) Fetch initial TTS state asynchronously (rather than blocking)
            await self.fetch_initial_tts_state()

            # 3) Main receive loop
            while self.running:
                try:
                    message = await self.ws.recv()
                    if isinstance(message, bytes):
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
        """ Send user message over WebSocket """
        if self.ws:
            self.messages.append({"sender": "user", "text": message})
            await self.ws.send(json.dumps({
                "action": "chat",
                "messages": self.messages
            }))

    async def send_playback_complete(self):
        """ Notifies the backend that TTS playback finished """
        if self.ws:
            await self.ws.send(json.dumps({"action": "playback-complete"}))

    def handle_assistant_message(self, message):
        """ Store assistant message in self.messages """
        self.messages.append({"sender": "assistant", "text": message})

    def run(self):
        # Entry point for QThread
        asyncio.run(self.connect())

    # -------------------------------------------------------------------------
    # Below are the new asynchronous coroutines that replace blocking requests.
    # They use aiohttp, and emit signals upon success or error.
    # -------------------------------------------------------------------------

    async def fetch_initial_tts_state(self):
        """
        Called once after WebSocket connects to get the initial TTS state from server.
        Equivalent to your original synchronous code, but now uses aiohttp.
        """
        url = f"{HTTP_BASE_URL}/api/toggle-tts"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        tts_enabled = data.get("tts_enabled", False)
                        # Let the main thread know about the TTS state
                        self.tts_state_changed.emit(tts_enabled)
                    else:
                        text = await resp.text()
                        self.http_error.emit(f"fetch_initial_tts_state: {resp.status} - {text}")
        except Exception as e:
            self.http_error.emit(f"fetch_initial_tts_state error: {e}")

    async def toggle_stt_state(self, current_stt_enabled: bool):
        """
        Toggles STT on/off. We rely on the current state from the GUI,
        so we pass that in. On success, we emit stt_toggled(new_state).
        """
        try:
            url = f"{HTTP_BASE_URL}/api/start-stt" if not current_stt_enabled else f"{HTTP_BASE_URL}/api/pause-stt"
            async with aiohttp.ClientSession() as session:
                async with session.post(url) as resp:
                    resp.raise_for_status()
                    # Return the new STT state to the GUI
                    new_state = not current_stt_enabled
                    self.stt_toggled.emit(new_state)
        except Exception as e:
            self.http_error.emit(f"toggle_stt_state error: {e}")

    async def toggle_tts_state(self, current_tts_enabled: bool):
        """
        Toggles TTS on/off. If turning off TTS, also stops local audio data.
        Emits tts_toggled(new_state).
        """
        try:
            url = f"{HTTP_BASE_URL}/api/toggle-tts"
            async with aiohttp.ClientSession() as session:
                async with session.post(url) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    new_state = data.get("tts_enabled", current_tts_enabled)

            # If TTS was just turned off, call /api/stop-tts to stop server audio
            if not new_state:
                stop_url = f"{HTTP_BASE_URL}/api/stop-tts"
                async with aiohttp.ClientSession() as session:
                    async with session.post(stop_url) as stop_resp:
                        stop_resp.raise_for_status()

            self.tts_toggled.emit(new_state)
        except Exception as e:
            self.http_error.emit(f"toggle_tts_state error: {e}")

    async def toggle_playback_location(self):
        """
        Toggles playback location. Emits playback_toggled(...) with "frontend" or "backend".
        """
        try:
            url = f"{HTTP_BASE_URL}/api/toggle-playback-location"
            async with aiohttp.ClientSession() as session:
                async with session.post(url) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    playback_location = data.get("playback_location", "backend")
            self.playback_toggled.emit(playback_location)
        except Exception as e:
            self.http_error.emit(f"toggle_playback_location error: {e}")

    async def stop_all(self):
        """
        Stops TTS and generation. Then emits all_stopped().
        """
        try:
            url_tts = f"{HTTP_BASE_URL}/api/stop-tts"
            url_gen = f"{HTTP_BASE_URL}/api/stop-generation"
            async with aiohttp.ClientSession() as session:
                # Stop TTS
                async with session.post(url_tts) as resp_tts:
                    resp_tts.raise_for_status()
                # Stop generation
                async with session.post(url_gen) as resp_gen:
                    resp_gen.raise_for_status()

            self.all_stopped.emit()
        except Exception as e:
            self.http_error.emit(f"stop_all error: {e}")

# ===================== MessageBubble =====================
class MessageBubble(QFrame):
    def __init__(self, text, is_user=True, parent=None):
        super().__init__(parent)
        self.setObjectName("messageBubble")
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.RichText)
        self.label.setOpenExternalLinks(True)
        self.setStyleSheet(f"""
            QFrame#messageBubble {{
                background-color: {COLORS['user_bubble'] if is_user else COLORS['assistant_bubble']};
                border-radius: 15px;
                padding: 5px;
                margin: {'5px 50px 5px 5px' if is_user else '5px 5px 5px 50px'};
            }}
            QLabel {{
                color: {COLORS['text_primary']};
                font-size: 14px;
            }}
        """)
        layout.addWidget(self.label)
        layout.setContentsMargins(5, 5, 5, 5)

    def update_text(self, new_text):
        self.label.setText(new_text)
    
    def get_text(self):
        return self.label.text()

# ===================== ChatWindow =====================
class CustomTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

    def keyPressEvent(self, event):
        # Pressing Enter (without Shift) sends the message
        if (event.key() == Qt.Key.Key_Return and 
            not event.modifiers() & Qt.KeyboardModifier.ShiftModifier and 
            self.parent is not None):
            self.parent.send_message()
        else:
            super().keyPressEvent(event)

class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modern Chat Interface")
        self.setMinimumSize(800, 600)

        # We'll track TTS/STT/Playback states in the GUI,
        # but we won't do blocking calls. We'll update them
        # once the asynchronous calls succeed.
        self.tts_enabled = False
        self.stt_enabled = False
        self.playback_location = "backend"

        self.assistant_text_in_progress = ""
        self.assistant_bubble_in_progress = None
        self.playback_complete_notified = False

        # Main layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # Top button area
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(5)
        
        self.toggle_stt_button = QPushButton("STT Off")
        self.toggle_stt_button.setFixedSize(120, 40)
        
        self.toggle_tts_button = QPushButton("TTS Off")
        self.toggle_tts_button.setFixedSize(120, 40)

        self.toggle_playback_button = QPushButton("BACK PLAY")
        self.toggle_playback_button.setFixedSize(120, 40)

        top_layout.addWidget(self.toggle_stt_button)
        top_layout.addWidget(self.toggle_tts_button)
        top_layout.addWidget(self.toggle_playback_button)
        top_layout.addStretch()

        # Chat area
        self.chat_area = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_area)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(2)
        self.chat_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(self.chat_area)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setContentsMargins(0, 0, 0, 0)

        # Input area
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

        # Add sections to main layout
        layout.addWidget(top_widget)
        layout.addWidget(scroll, stretch=1)
        layout.addWidget(input_widget)

        # WebSocket client
        self.ws_client = WebSocketClient()
        self.ws_client.message_received.connect(self.handle_message)
        self.ws_client.stt_text_received.connect(self.handle_stt_text)
        self.ws_client.connection_status.connect(self.handle_connection_status)
        self.ws_client.audio_received.connect(self.on_audio_received)
        self.ws_client.tts_state_changed.connect(self.handle_tts_state_changed)

        # New signals for async calls
        self.ws_client.stt_toggled.connect(self.on_stt_toggled)
        self.ws_client.tts_toggled.connect(self.on_tts_toggled)
        self.ws_client.playback_toggled.connect(self.on_playback_toggled)
        self.ws_client.all_stopped.connect(self.on_all_stopped)
        self.ws_client.http_error.connect(self.on_http_error)

        self.ws_client.start()

        # Button signals
        send_button.clicked.connect(self.send_message)
        self.text_input.textChanged.connect(self.adjust_text_input_height)
        self.toggle_stt_button.clicked.connect(self.toggle_stt)
        self.toggle_tts_button.clicked.connect(self.toggle_tts)
        self.toggle_playback_button.clicked.connect(self.toggle_playback_location)
        self.stop_all_button.clicked.connect(self.stop_tts_and_generation)

        # ============ Setup QAudio for PCM playback ============
        audio_format = QAudioFormat()
        audio_format.setSampleRate(24000)
        audio_format.setChannelCount(1)
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        device = QMediaDevices.defaultAudioOutput()
        if device is None:
            logger.error("Error: No audio output device found!")
        else:
            logger.info(f"Using audio device: {device.description()}")

        self.audio_sink = QAudioSink(device, audio_format)
        self.audio_sink.setVolume(1.0)

        self.audio_device = QueueAudioDevice()
        self.audio_device.open(QIODevice.OpenModeFlag.ReadOnly)
        self.audio_sink.start(self.audio_device)

        self.audio_queue = asyncio.Queue()
        self.audio_timer = QTimer()
        self.audio_timer.setInterval(10)
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
                padding: 5px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['button_hover']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['button_pressed']};
                margin: 2px;
            }}
            QLabel {{
                color: {COLORS['text_primary']};
            }}
        """)
        palette = self.text_input.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(COLORS['text_secondary']))
        self.text_input.setPalette(palette)

    # -------------------------------------------------------------------------
    # Button methods: now all are asynchronous. We dispatch coroutines
    # on the ws_client thread using asyncio.run_coroutine_threadsafe(...)
    # -------------------------------------------------------------------------

    def toggle_stt(self):
        """ Schedules the async STT toggle on the WebSocketClient's event loop """
        if self.ws_client.loop is None:
            return
        future = asyncio.run_coroutine_threadsafe(
            self.ws_client.toggle_stt_state(self.stt_enabled),
            self.ws_client.loop
        )
        # Results handled in on_stt_toggled or on_http_error

    def toggle_tts(self):
        """ Schedules the async TTS toggle on the WebSocketClient's event loop """
        if self.ws_client.loop is None:
            return
        future = asyncio.run_coroutine_threadsafe(
            self.ws_client.toggle_tts_state(self.tts_enabled),
            self.ws_client.loop
        )
        # Results handled in on_tts_toggled or on_http_error

    def toggle_playback_location(self):
        """ Schedules the async playback toggle on the WebSocketClient's event loop """
        if self.ws_client.loop is None:
            return
        future = asyncio.run_coroutine_threadsafe(
            self.ws_client.toggle_playback_location(),
            self.ws_client.loop
        )
        # Results handled in on_playback_toggled or on_http_error

    def stop_tts_and_generation(self):
        """ Schedules the async stop-all on the WebSocketClient's event loop """
        if self.ws_client.loop is None:
            return
        future = asyncio.run_coroutine_threadsafe(
            self.ws_client.stop_all(),
            self.ws_client.loop
        )
        # Results handled in on_all_stopped or on_http_error

    # -------------------------------------------------------------------------
    # Signals handling (UI updates) after async operations
    # -------------------------------------------------------------------------
    def on_stt_toggled(self, new_state: bool):
        self.stt_enabled = new_state
        self.toggle_stt_button.setText("STT On" if self.stt_enabled else "STT Off")

    def on_tts_toggled(self, new_state: bool):
        self.tts_enabled = new_state
        self.toggle_tts_button.setText("TTS On" if self.tts_enabled else "TTS Off")
        if not self.tts_enabled:
            # Clear local audio buffer
            self.audio_device.audio_buffer.clear()
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except:
                    pass
            # Insert a "None" marker to signal end of stream
            self.audio_queue.put_nowait(None)

    def on_playback_toggled(self, new_location: str):
        self.playback_location = new_location
        self.toggle_playback_button.setText("FRONT PLAY" if new_location == "frontend" else "BACK PLAY")

    def on_all_stopped(self):
        # For safety, finalize any in-progress assistant bubble
        self.finalize_assistant_bubble()

    def on_http_error(self, err_message: str):
        logger.error(f"HTTP Error: {err_message}")
        # Optionally show a popup dialog or bubble in chat

    # -------------------------------------------------------------------------
    # Existing logic unchanged
    # -------------------------------------------------------------------------
    def send_message(self):
        text = self.text_input.toPlainText().strip()
        if text:
            try:
                self.finalize_assistant_bubble()
                self.add_message(text, True)
                # Schedule sending on the ws event loop
                if self.ws_client.loop is not None:
                    asyncio.run_coroutine_threadsafe(
                        self.ws_client.send_message(text),
                        self.ws_client.loop
                    )
                self.text_input.clear()
            except Exception as e:
                logger.error(f"Error sending message: {e}")

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

    def handle_tts_state_changed(self, is_enabled: bool):
        """
        Called once after the WebSocket first connects and fetches the
        initial TTS state. This is effectively the "initial" TTS state.
        """
        self.tts_enabled = is_enabled
        self.toggle_tts_button.setText("TTS On" if is_enabled else "TTS Off")

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

    def on_audio_received(self, pcm_data: bytes):
        logger.info(f"Frontend: Processing audio chunk of size: {len(pcm_data)} bytes")
        self.playback_complete_notified = False
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
                        if not self.playback_complete_notified:
                            self.notify_playback_complete()
                            self.playback_complete_notified = True
                        break
                    chunk_size = len(pcm_chunk)
                    total_bytes += chunk_size
                    self.audio_device.writeData(pcm_chunk)
                    chunks_processed += 1
                except asyncio.QueueEmpty:
                    break
            
            if chunks_processed > 0:
                logger.debug(f"Audio chunks processed: {chunks_processed}, total bytes: {total_bytes}")
                if self.audio_sink.state() != QAudio.State.ActiveState:
                    logger.info("Restarting audio sink...")
                    self.audio_sink.start(self.audio_device)

        except Exception as e:
            logger.error(f"Error in feed_audio_data: {e}")

    def notify_playback_complete(self):
        try:
            if self.ws_client.loop is not None:
                asyncio.run_coroutine_threadsafe(
                    self.ws_client.send_playback_complete(),
                    self.ws_client.loop
                )
            logger.info("Notified backend of playback completion.")
        except Exception as e:
            logger.error(f"Error notifying playback complete: {e}")

# ===================== main =====================
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ChatWindow()
    window.apply_styling()
    window.show()
    sys.exit(app.exec())
