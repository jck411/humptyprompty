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
    Qt, QTimer, QSize, QIODevice, pyqtSignal, QObject, QMutex, QMutexLocker
)
from PyQt6.QtGui import (
    QColor, QPalette, QIcon
)
from PyQt6.QtMultimedia import (
    QAudio
)

# qasync integration
from qasync import QEventLoop

# Import your frontend STT implementation
from frontend.stt.deepgram_stt import DeepgramSTT

# Import the new audio module
from frontend.audio import AudioManager

import asyncio.exceptions

# Import configuration
from frontend.config import SERVER_HOST, SERVER_PORT, WEBSOCKET_PATH, HTTP_BASE_URL, logger

# -----------------------------------------------------------------------------
#                        2. IMPORT STYLING & THEMING
# -----------------------------------------------------------------------------

from frontend.style import DARK_COLORS, LIGHT_COLORS, generate_main_stylesheet, get_message_bubble_stylesheet

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
#                          6. MAIN CHAT WINDOW CLASS
# -----------------------------------------------------------------------------

class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Modern Chat Interface")
        self.setMinimumSize(800, 600)
        self.is_dark_mode = True
        
        self.colors = DARK_COLORS

        self.assistant_text_in_progress = ""
        self.assistant_bubble_in_progress = None
        self.stt_listening = True
        self.stt_enabled = True
        self.is_toggling_stt = False
        self.is_toggling_tts = False

        # Initialize the audio manager
        self.audio_manager = AudioManager()
        self.audio_manager.audio_state_changed.connect(self.handle_audio_state_changed)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.main_layout = QVBoxLayout(main_widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(2)

        self.frontend_stt = DeepgramSTT()

        self.setup_top_buttons_layout()
        self.setup_chat_area_layout()
        self.setup_input_area_layout()

        self.setup_websocket()

        self.apply_styling()
        
        # Connect to the transcription_received signal for interim updates (optional)
        self.frontend_stt.transcription_received.connect(self.handle_interim_stt_text)
        # Connect to the complete_utterance_received signal for final updates
        self.frontend_stt.complete_utterance_received.connect(self.handle_frontend_stt_text)
        self.frontend_stt.state_changed.connect(self.handle_frontend_stt_state)

        QTimer.singleShot(0, lambda: asyncio.create_task(self._init_states_async()))
        self.theme_toggle.setIcon(QIcon("frontend/icons/light_mode.svg"))

        QTimer.singleShot(0, self.toggle_stt)

        self.async_tasks = []
        QTimer.singleShot(0, self.create_async_tasks)

    def create_async_tasks(self):
        # Start the audio consumer task
        self.audio_manager.start_audio_consumer()
        # Start the websocket connection
        self.async_tasks.append(asyncio.create_task(self.ws_client.connect()))
        logger.info("Created async tasks")

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

    def setup_top_buttons_layout(self):
        self.top_widget = QWidget()
        top_layout = QHBoxLayout(self.top_widget)
        top_layout.setContentsMargins(0, 5, 0, 0)
        top_layout.setSpacing(5)
        
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

    def setup_websocket(self):
        self.ws_client = AsyncWebSocketClient(SERVER_HOST, SERVER_PORT, WEBSOCKET_PATH)
        self.ws_client.message_received.connect(self.handle_message)
        self.ws_client.connection_status.connect(self.handle_connection_status)
        self.ws_client.audio_received.connect(self.on_audio_received)
        self.ws_client.tts_state_changed.connect(self.handle_tts_state_changed)

    def apply_styling(self):
        self.setStyleSheet(generate_main_stylesheet(self.colors))
        self.chat_area.setStyleSheet(f"background-color: {self.colors['background']};")
        scroll_area = self.findChild(QScrollArea)
        scroll_area.setStyleSheet(f"background-color: {self.colors['background']};")
        
        palette = self.text_input.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(self.colors['text_secondary']))
        self.text_input.setPalette(palette)
        
        for i in range(self.chat_layout.count()):
            widget = self.chat_layout.itemAt(i).widget()
            if widget and widget.__class__.__name__ == "MessageBubble":
                is_user = widget.property("isUser")
                widget.setStyleSheet(get_message_bubble_stylesheet(is_user, self.colors))

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.colors = DARK_COLORS if self.is_dark_mode else LIGHT_COLORS
        icon_path = "frontend/icons/light_mode.svg" if self.is_dark_mode else "frontend/icons/dark_mode.svg"
        self.theme_toggle.setIcon(QIcon(icon_path))
        self.apply_styling()

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
        if not self.assistant_bubble_in_progress:
            self.assistant_bubble_in_progress = MessageBubble("", is_user=False)
            self.assistant_bubble_in_progress.setStyleSheet(get_message_bubble_stylesheet(False, self.colors))
            self.chat_layout.insertWidget(self.chat_layout.count() - 1, self.assistant_bubble_in_progress)

        self.assistant_text_in_progress += token
        self.assistant_bubble_in_progress.update_text(self.assistant_text_in_progress)
        self.auto_scroll_chat()

    def finalize_assistant_bubble(self):
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

    def handle_audio_state_changed(self, state):
        logger.info(f"[handle_audio_state_changed] Audio state changed to: {state}")
        buffer_size, is_end_of_stream = self.audio_manager.get_audio_state()
        logger.info(f"[handle_audio_state_changed] Buffer size: {buffer_size}, End of stream: {is_end_of_stream}")

    def on_audio_received(self, pcm_data: bytes):
        # Use the audio manager to process the audio data
        self.audio_manager.process_audio_data(pcm_data, self.frontend_stt)
        
        # Send playback-complete notification to server when audio finishes
        if pcm_data == b'audio:' or len(pcm_data) == 0:
            if self.ws_client and self.ws_client.ws:
                asyncio.create_task(self.ws_client.ws.send(json.dumps({"action": "playback-complete"})))
                logger.info("Sent playback-complete to server")

    def handle_tts_state_changed(self, is_enabled: bool):
        self.tts_enabled = is_enabled
        self.toggle_tts_button.setText("TTS On" if is_enabled else "TTS Off")

    async def toggle_tts_async(self):
        self.is_toggling_tts = True
        try:
            # Toggle the TTS state on the server
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{HTTP_BASE_URL}/api/toggle-tts") as resp:
                    data = await resp.json()
                    self.tts_enabled = data.get("tts_enabled", not self.tts_enabled)
            
            self.toggle_tts_button.setText("TTS On" if self.tts_enabled else "TTS Off")

        except Exception as e:
            logger.error(f"Error toggling TTS: {e}")
        finally:
            self.is_toggling_tts = False

    async def stop_tts_and_generation_async(self):
        logger.info("Stop button pressed - stopping TTS and generation")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{HTTP_BASE_URL}/api/stop-audio") as resp1:
                    resp1_data = await resp1.json()
                    logger.info(f"Stop TTS response: {resp1_data}")

                async with session.post(f"{HTTP_BASE_URL}/api/stop-generation") as resp2:
                    resp2_data = await resp2.json()
                    logger.info(f"Stop generation response: {resp2_data}")
        except Exception as e:
            logger.error(f"Error stopping TTS and generation on server: {e}")

        # Use the audio manager to stop audio playback
        await self.audio_manager.stop_audio()

        logger.info("Finalizing assistant bubble")
        self.finalize_assistant_bubble()

    def handle_connection_status(self, connected):
        self.setWindowTitle(f"Modern Chat Interface - {'Connected' if connected else 'Disconnected'}")

    def adjust_text_input_height(self):
        doc_height = self.text_input.document().size().height()
        new_height = min(max(50, doc_height + 20), 100)
        self.text_input.setFixedHeight(int(new_height))

    def keyPressEvent(self, event):
        super().keyPressEvent(event)

    def closeEvent(self, event):
        logger.info("Closing application...")
        if hasattr(self, 'ws_client') and self.ws_client:
            self.ws_client.running = False
        if hasattr(self, 'frontend_stt') and self.frontend_stt:
            self.frontend_stt.stop()
        if hasattr(self, 'audio_manager'):
            self.audio_manager.cleanup()
        if hasattr(self, 'async_tasks'):
            for task in self.async_tasks:
                if not task.done():
                    task.cancel()
        super().closeEvent(event)

    def handle_interim_stt_text(self, text):
        # This method handles interim transcriptions
        # You can optionally use this for visual feedback without updating the text input
        if text.strip():
            print(f"Interim STT text: {text}")
            # Optionally, you could show this somewhere else in the UI

    def handle_frontend_stt_text(self, text):
        # This method now only handles complete utterances
        if text.strip():
            print(f"Complete utterance: {text}")
            self.text_input.setPlainText(text)
            self.adjust_text_input_height()

    def handle_frontend_stt_state(self, is_listening):
        try:
            self.stt_listening = is_listening
            self.toggle_stt_button.setText(f"STT {'On' if is_listening else 'Off'}")
            self.toggle_stt_button.setProperty("isListening", is_listening)
            style = self.toggle_stt_button.style()
            if style:
                style.unpolish(self.toggle_stt_button)
                style.polish(self.toggle_stt_button)
            self.toggle_stt_button.update()
        except asyncio.exceptions.CancelledError:
            logger.warning("STT state update task was cancelled - this is expected during shutdown")
        except Exception as e:
            logger.error(f"Error updating STT state in UI: {e}")

    def toggle_stt(self):
        if self.is_toggling_stt:
            return
        self.is_toggling_stt = True
        try:
            if hasattr(self.frontend_stt, 'toggle'):
                self.frontend_stt.toggle()
                self.handle_frontend_stt_state(not self.stt_listening)
            else:
                logger.error("Frontend STT implementation missing toggle method")
                self.handle_frontend_stt_state(not self.stt_listening)
        except asyncio.exceptions.CancelledError:
            logger.warning("STT toggle task was cancelled - this is expected during shutdown")
        except Exception as e:
            logger.error(f"Error toggling STT: {e}")
            self.handle_frontend_stt_state(not self.stt_listening)
        finally:
            self.is_toggling_stt = False

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

    try:
        with loop:
            loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    finally:
        logger.info("Cleaning up before exit")
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
