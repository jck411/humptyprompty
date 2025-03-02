"""
Main chat window for the frontend application.
"""
import asyncio
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QScrollArea, QSizePolicy, QFrame, QLabel
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QPalette, QIcon

from frontend.config.config import UI_CONFIG, SERVER_CONFIG
from frontend.ui.components import MessageBubble, CustomTextEdit
from frontend.ui.styles import generate_main_stylesheet, get_message_bubble_stylesheet
from frontend.network.websocket_client import AsyncWebSocketClient
from frontend.audio.processor import AudioManager
from frontend.stt.deepgram_stt import DeepgramSTT
from frontend.utils.logger import get_logger

logger = get_logger(__name__)

class ChatWindow(QMainWindow):
    """
    Main chat window for the application.
    """
    def __init__(self):
        """Initialize the chat window."""
        super().__init__()
        
        # Set up main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.main_layout = QVBoxLayout(main_widget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(2)
        
        # Set window properties
        self.setWindowTitle(UI_CONFIG['window_title'])
        self.setMinimumSize(UI_CONFIG['min_width'], UI_CONFIG['min_height'])
        
        # Initialize state variables
        self.is_dark_mode = UI_CONFIG['default_theme'] == 'dark'
        self.colors = UI_CONFIG['colors']['dark'] if self.is_dark_mode else UI_CONFIG['colors']['light']
        
        self.assistant_text_in_progress = ""
        self.assistant_bubble_in_progress = None

        self.stt_listening = False
        self.stt_enabled = False
        self.is_toggling_stt = False
        self.tts_enabled = False
        self.is_toggling_tts = False
        
        # Initialize frontend STT
        self.frontend_stt = DeepgramSTT()

        # Set up UI components
        self.setup_top_buttons_layout()
        self.setup_chat_area_layout()
        self.setup_input_area_layout()

        # Set up network and audio
        self.setup_websocket()
        self.audio_manager = AudioManager()
        
        # Apply styling
        self.apply_styling()
        
        # Connect STT signals
        self.frontend_stt.transcription_received.connect(self.handle_frontend_stt_text)
        self.frontend_stt.state_changed.connect(self.handle_frontend_stt_state)

        # Initialize states asynchronously
        QTimer.singleShot(0, lambda: asyncio.create_task(self._init_states_async()))
        
        # Set theme icon
        icon_path = "frontend/icons/light_mode.svg" if self.is_dark_mode else "frontend/icons/dark_mode.svg"
        self.theme_toggle.setIcon(QIcon(icon_path))

    async def _init_states_async(self):
        """Initialize states asynchronously."""
        self.tts_enabled = await self.ws_client.get_initial_tts_state()
        logger.info(f"Initial TTS state: {self.tts_enabled}")
        self.toggle_tts_button.setText("TTS On" if self.tts_enabled else "TTS Off")
        self.is_toggling_tts = False

    def setup_top_buttons_layout(self):
        """Set up the top buttons layout."""
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
        self.toggle_stt_button.clicked.connect(self.toggle_stt)

        self.toggle_tts_button = QPushButton("TTS Off")
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
        """Set up the chat area layout."""
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
        """Set up the input area layout."""
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
        """Set up the WebSocket client."""
        self.ws_client = AsyncWebSocketClient()
        self.ws_client.message_received.connect(self.handle_message)
        self.ws_client.connection_status.connect(self.handle_connection_status)
        self.ws_client.audio_received.connect(self.handle_audio_received)
        self.ws_client.tts_state_changed.connect(self.handle_tts_state_changed)
        QTimer.singleShot(0, lambda: asyncio.create_task(self.ws_client.connect()))

    def apply_styling(self):
        """Apply styling to the window."""
        self.setStyleSheet(generate_main_stylesheet(self.colors))
        palette = self.text_input.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(self.colors['text_secondary']))
        self.text_input.setPalette(palette)

    def toggle_theme(self):
        """Toggle between light and dark themes."""
        self.is_dark_mode = not self.is_dark_mode
        self.colors = UI_CONFIG['colors']['dark'] if self.is_dark_mode else UI_CONFIG['colors']['light']

        icon_path = "frontend/icons/light_mode.svg" if self.is_dark_mode else "frontend/icons/dark_mode.svg"
        self.theme_toggle.setIcon(QIcon(icon_path))
        self.chat_area.setStyleSheet(f"background-color: {self.colors['background']};")
        scroll_area = self.findChild(QScrollArea)
        scroll_area.setStyleSheet(f"background-color: {self.colors['background']};")
        
        # Update all message bubbles
        for i in range(self.chat_layout.count()):
            widget = self.chat_layout.itemAt(i).widget()
            if widget and widget.__class__.__name__ == "MessageBubble":
                is_user = widget.property("isUser")
                widget.setStyleSheet(get_message_bubble_stylesheet(is_user, self.colors))
        
        self.apply_styling()

    def send_message(self):
        """Send a message to the server."""
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
        """
        Handle a message token from the server.
        
        Args:
            token: The message token.
        """
        if not self.assistant_bubble_in_progress:
            self.assistant_bubble_in_progress = MessageBubble("", is_user=False, colors=self.colors)
            self.chat_layout.insertWidget(self.chat_layout.count() - 1, self.assistant_bubble_in_progress)
        
        self.assistant_text_in_progress += token
        self.assistant_bubble_in_progress.update_text(self.assistant_text_in_progress)
        self.auto_scroll_chat()

    def finalize_assistant_bubble(self):
        """Finalize the current assistant message bubble."""
        if self.assistant_bubble_in_progress:
            self.ws_client.handle_assistant_message(self.assistant_text_in_progress)
            self.assistant_text_in_progress = ""
            self.assistant_bubble_in_progress = None

    def handle_connection_status(self, connected):
        """
        Handle connection status changes.
        
        Args:
            connected: Boolean indicating if connected.
        """
        self.setWindowTitle(f"{UI_CONFIG['window_title']} - {'Connected' if connected else 'Disconnected'}")

    def handle_tts_state_changed(self, is_enabled: bool):
        """
        Handle TTS state changes.
        
        Args:
            is_enabled: Boolean indicating if TTS is enabled.
        """
        self.tts_enabled = is_enabled
        self.toggle_tts_button.setText("TTS On" if is_enabled else "TTS Off")

    def add_message(self, text, is_user):
        """
        Add a message to the chat.
        
        Args:
            text: The message text.
            is_user: Boolean indicating if the message is from the user.
        """
        bubble = MessageBubble(text, is_user, self.colors)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        self.auto_scroll_chat()

    def auto_scroll_chat(self):
        """Auto-scroll the chat to the bottom."""
        scroll_area = self.findChild(QScrollArea)
        vsb = scroll_area.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    def adjust_text_input_height(self):
        """Adjust the height of the text input based on content."""
        doc_height = self.text_input.document().size().height()
        new_height = min(max(50, doc_height + 20), 100)
        self.text_input.setFixedHeight(int(new_height))

    async def toggle_tts_async(self):
        """Toggle TTS asynchronously."""
        if self.is_toggling_tts:
            return
            
        self.is_toggling_tts = True
        try:
            tts_enabled = await self.ws_client.toggle_tts_async()
            if tts_enabled is not None:
                self.tts_enabled = tts_enabled
                self.toggle_tts_button.setText("TTS On" if self.tts_enabled else "TTS Off")
                
                if not self.tts_enabled:
                    self.audio_manager.clear_audio()
        except Exception as e:
            logger.error(f"Error toggling TTS: {e}")
        finally:
            self.is_toggling_tts = False

    async def stop_tts_and_generation_async(self):
        """Stop TTS and text generation asynchronously."""
        logger.info("Stop button pressed - stopping TTS and generation")
        
        # Stop on server
        await self.ws_client.stop_tts_and_generation_async()
        
        # Clean up audio
        self.audio_manager.clear_audio()
        
        # Finalize assistant bubble
        self.finalize_assistant_bubble()

    def handle_audio_received(self, pcm_data: bytes):
        """
        Handle received audio data.
        
        Args:
            pcm_data: The PCM audio data.
        """
        self.audio_manager.process_audio_data(pcm_data)

    def toggle_stt(self):
        """Toggle speech-to-text functionality."""
        self.frontend_stt.toggle()

    def handle_frontend_stt_text(self, text):
        """
        Handle text from the frontend STT.
        
        Args:
            text: The transcribed text.
        """
        if text.strip():
            logger.info(f"Frontend STT text: {text}")
            self.text_input.setPlainText(text)
            self.adjust_text_input_height()

    def handle_frontend_stt_state(self, is_listening):
        """
        Handle state changes from the frontend STT.
        
        Args:
            is_listening: Boolean indicating if STT is listening.
        """
        self.stt_listening = is_listening
        self.toggle_stt_button.setText(f"STT {'On' if is_listening else 'Off'}")
        self.toggle_stt_button.setProperty("isListening", is_listening)
        self.toggle_stt_button.style().unpolish(self.toggle_stt_button)
        self.toggle_stt_button.style().polish(self.toggle_stt_button)

    def clear_chat_history(self):
        """Clear the chat history."""
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

    def keyPressEvent(self, event):
        """
        Handle key press events.
        
        Args:
            event: The key event.
        """
        super().keyPressEvent(event)
