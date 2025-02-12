#!/usr/bin/env python3
import sys
import json
import asyncio
import requests
import logging
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QSize, QMutexLocker
from PyQt6.QtGui import QColor, QPalette, QIcon
from PyQt6.QtMultimedia import QAudio

from config import (
    SERVER_HOST, SERVER_PORT, WEBSOCKET_PATH, HTTP_BASE_URL,
    COLORS, DARK_COLORS, LIGHT_COLORS, logger
)
from components import MessageBubble, CustomTextEdit
from websocket_client import WebSocketClient
from audio import setup_audio

class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modern Chat Interface")
        self.setMinimumSize(800, 600)  # Keep minimum size for usability
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Initialize kiosk mode state
        self.is_kiosk_mode = False
        self.normal_window_flags = self.windowFlags()
        
        # Initialize dark mode and colors first
        self.is_dark_mode = True
        global COLORS
        COLORS = DARK_COLORS
        
        # Buffer for in-progress assistant message
        self.assistant_text_in_progress = ""
        self.assistant_bubble_in_progress = None

        # Initialize states first
        self.init_states()
        
        # Setup UI components after states are initialized
        self.setup_ui()
        
        # Setup WebSocket client
        self.setup_websocket()
        
        # Setup audio
        self.setup_audio()
        
        # Apply initial styling
        self.apply_styling()
        
        # Set initial theme toggle icon to reflect dark mode
        self.theme_toggle.setIcon(QIcon("/home/jack/humptyprompty/frontend/icons/light_mode_24dp_E8EAED.svg"))

    def init_states(self):
        # Get initial TTS state from server
        try:
            resp = requests.post(f"{HTTP_BASE_URL}/api/toggle-tts")
            resp.raise_for_status()
            self.tts_enabled = resp.json().get("tts_enabled", False)
        except requests.RequestException as e:
            logger.error(f"Error getting initial TTS state: {e}")
            self.tts_enabled = False
        
        self.is_toggling_tts = False
        self.stt_enabled = False
        self.is_toggling_stt = False
        self.playback_complete_notified = False

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # Top button area
        self.setup_top_buttons(layout)
        
        # Chat area
        self.setup_chat_area(layout)
        
        # Input area
        self.setup_input_area(layout)

    def setup_top_buttons(self, layout):
        self.top_widget = QWidget()  # Make it instance variable so we can modify it later
        top_layout = QHBoxLayout(self.top_widget)
        top_layout.setContentsMargins(0, 5, 0, 0)  # Add top padding that will work in both modes
        top_layout.setSpacing(5)
        
        self.toggle_stt_button = QPushButton("STT Off")
        self.toggle_stt_button.setFixedSize(120, 40)
        
        self.toggle_tts_button = QPushButton("TTS On" if self.tts_enabled else "TTS Off")
        self.toggle_tts_button.setFixedSize(120, 40)

        top_layout.addWidget(self.toggle_stt_button)
        top_layout.addWidget(self.toggle_tts_button)
        top_layout.addStretch()

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

        # Connect signals
        send_button.clicked.connect(self.send_message)
        self.text_input.textChanged.connect(self.adjust_text_input_height)
        self.toggle_stt_button.clicked.connect(self.toggle_stt)
        self.toggle_tts_button.clicked.connect(self.toggle_tts)
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
        self.ws_client.connection_status.connect(self.handle_connection_status)
        self.ws_client.audio_received.connect(self.on_audio_received)
        self.ws_client.tts_state_changed.connect(self.handle_tts_state_changed)
        self.ws_client.start()

    def setup_audio(self):
        self.audio_sink, self.audio_device = setup_audio()
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
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
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
        """)
        palette = self.text_input.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(COLORS['text_secondary']))
        self.text_input.setPalette(palette)

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        global COLORS
        COLORS = DARK_COLORS if self.is_dark_mode else LIGHT_COLORS
        
        # Update theme toggle icon
        icon_path = "/home/jack/humptyprompty/frontend/icons/light_mode_24dp_E8EAED.svg" if self.is_dark_mode else "/home/jack/humptyprompty/frontend/icons/dark_mode_24dp_E8EAED.svg"
        self.theme_toggle.setIcon(QIcon(icon_path))
        
        # Update chat area background
        self.chat_area.setStyleSheet(f"background-color: {COLORS['background']};")
        
        # Update scroll area background
        scroll_area = self.findChild(QScrollArea)
        scroll_area.setStyleSheet(f"background-color: {COLORS['background']};")
        
        # Reapply styling for all existing message bubbles
        for i in range(self.chat_layout.count()):
            widget = self.chat_layout.itemAt(i).widget()
            if isinstance(widget, MessageBubble):
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
        
        # Reapply overall styling
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
                # Optionally show an error to the user here

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
        """Handle TTS state changes from the server"""
        self.tts_enabled = is_enabled
        self.toggle_tts_button.setText("TTS On" if is_enabled else "TTS Off")

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
            # Toggle the TTS state first
            resp = requests.post(f"{HTTP_BASE_URL}/api/toggle-tts")
            resp.raise_for_status()
            data = resp.json()
            
            # Update the local flag with the server's response
            self.tts_enabled = data.get("tts_enabled", self.tts_enabled)
            
            # If we're turning TTS off, immediately stop any ongoing audio
            if not self.tts_enabled:
                # Stop the TTS on the backend
                stop_resp = requests.post(f"{HTTP_BASE_URL}/api/stop-tts")
                stop_resp.raise_for_status()
                # Clear local audio buffer and queue
                self.audio_device.audio_buffer.clear()
                while not self.audio_queue.empty():
                    try:
                        self.audio_queue.get_nowait()
                    except:
                        pass
                # Signal termination of the audio stream
                self.audio_queue.put_nowait(None)
            
            # Update button text - fixed to show the current state
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
        # Reset the flag if new audio data arrives.
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
                        # Notify the backend only once per stream.
                        if not self.playback_complete_notified:
                            self.notify_playback_complete()
                            self.playback_complete_notified = True
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

    def notify_playback_complete(self):
        """
        Called when the audio stream has finished.
        We send a 'playback-complete' notification to the backend over the WebSocket.
        """
        try:
            # We use asyncio.run here because this method is called from a synchronous context.
            asyncio.run(self.ws_client.send_playback_complete())
            logger.info("Notified backend of playback completion.")
        except Exception as e:
            logger.error(f"Error notifying playback complete: {e}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.toggle_kiosk_mode()
        super().keyPressEvent(event)

    def toggle_kiosk_mode(self):
        self.is_kiosk_mode = not self.is_kiosk_mode
        
        if self.is_kiosk_mode:
            # Store current geometry before changing flags
            self.normal_geometry = self.geometry()
            # Remove title bar and frame
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            # Adjust margins to use title bar space
            self.centralWidget().layout().setContentsMargins(5, 0, 5, 5)
        else:
            # Restore normal window flags and geometry
            self.setWindowFlags(self.normal_window_flags)
            self.setGeometry(self.normal_geometry)
            # Restore normal margins
            self.centralWidget().layout().setContentsMargins(5, 5, 5, 5)
        
        # Show window again (required after changing flags)
        self.show()
        
        # Ensure the chat area gets scrolled properly after toggling
        QTimer.singleShot(100, self.auto_scroll_chat)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ChatWindow()
    window.apply_styling()
    window.show()
    sys.exit(app.exec())
