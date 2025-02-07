import sys
import json
import asyncio
import requests
import websockets

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QScrollArea, QFrame, QLabel
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QIODevice
from PyQt6.QtGui import QColor, QPalette, QIcon

from PyQt6.QtMultimedia import (
    QAudioFormat,
    QAudioSink,
    QMediaDevices,
    QAudioDevice,
    QAudio  # Add this for State enum
)

# Define a consistent color scheme
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

# -------------------------------------------------------------
# A simple QIODevice that lets QAudioOutput pull PCM frames
# from an internal buffer. We will fill this buffer from
# an asyncio.Queue whenever new audio arrives.
# -------------------------------------------------------------
class QueueAudioDevice(QIODevice):
    def __init__(self):
        super().__init__()
        self.audio_buffer = bytearray()
        print("QueueAudioDevice initialized")

    def readData(self, maxSize):
        if len(self.audio_buffer) == 0:
            print("Audio buffer empty, returning silence")
            return bytes(maxSize)  # Return silence instead of empty bytes
        
        data = bytes(self.audio_buffer[:maxSize])
        self.audio_buffer = self.audio_buffer[maxSize:]
        print(f"Reading {len(data)} bytes from buffer, {len(self.audio_buffer)} remaining")
        return data

    def writeData(self, data):
        print(f"WriteData called with {len(data)} bytes")
        return len(data)

    def bytesAvailable(self):
        available = len(self.audio_buffer) + super().bytesAvailable()
        print(f"BytesAvailable: {available}")
        return available

    def isSequential(self):
        return True


# -------------------------------------------------------------
# WebSocket Client runs in a QThread so the UI stays responsive.
# Now we also emit a signal with PCM audio (as bytes).
# -------------------------------------------------------------
class WebSocketClient(QThread):
    message_received = pyqtSignal(str)
    stt_text_received = pyqtSignal(str)
    connection_status = pyqtSignal(bool)

    # --- AUDIO-RELATED CODE ---
    audio_received = pyqtSignal(bytes)  # Signal to send PCM frames to main thread

    def __init__(self):
        super().__init__()
        self.ws = None
        self.running = True
        self.messages = []

    async def connect(self):
        try:
            self.ws = await websockets.connect('ws://localhost:8000/ws/chat')
            self.connection_status.emit(True)
            print("Frontend: WebSocket connected")

            while self.running:
                try:
                    message = await self.ws.recv()
                    
                    if isinstance(message, bytes):
                        # Ensure we're actually receiving audio data
                        print(f"Frontend: Received binary message of size: {len(message)} bytes")
                        if message.startswith(b'audio:'):
                            audio_data = message[6:]  # Skip the 'audio:' prefix
                            if len(audio_data) > 0:
                                print("Frontend: Emitting audio data")
                                self.audio_received.emit(audio_data)
                        else:
                            print("Frontend: Received non-audio binary data")
                    else:
                        try:
                            data = json.loads(message)
                            if "content" in data:
                                print(f"Frontend: Received text message: {message[:100]}...")
                                self.message_received.emit(data["content"])
                            elif "stt_text" in data:
                                self.stt_text_received.emit(data["stt_text"])
                            else:
                                print(f"Frontend: Received other JSON message: {message[:100]}...")
                        except json.JSONDecodeError:
                            print(f"Frontend: Failed to parse JSON message: {message}")

                except websockets.exceptions.ConnectionClosed:
                    print("Frontend: WebSocket connection closed")
                    break
                except Exception as e:
                    print(f"Frontend: Error processing WebSocket message: {e}")
                    break

        except Exception as e:
            print(f"Frontend: WebSocket connection error: {e}")
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

# -------------------------------------------------------------
# A single message bubble for either user or assistant.
# -------------------------------------------------------------
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

# -------------------------------------------------------------
# Main Window for Chat + Audio playback
# -------------------------------------------------------------
class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modern Chat Interface")
        self.setMinimumSize(800, 600)

        # Buffers to keep track of an in-progress assistant message
        self.assistant_text_in_progress = ""
        self.assistant_bubble_in_progress = None

        # State for TTS and STT toggling
        self.tts_enabled = True
        self.is_toggling_tts = False
        self.stt_enabled = False
        self.is_toggling_stt = False

        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Chat area
        self.chat_area = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_area)
        self.chat_layout.addStretch()

        # Scroll area for chat
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

        # --- STT Toggle Button (text-based) ---
        self.toggle_stt_button = QPushButton("STT Off")
        self.toggle_stt_button.setFixedSize(120, 50)

        # --- Toggle TTS Button ---
        self.toggle_tts_button = QPushButton("TTS On")
        self.toggle_tts_button.setFixedSize(120, 50)

        # --- Stop Button (stops TTS and text generation) ---
        self.stop_all_button = QPushButton()
        self.stop_all_button.setFixedSize(50, 50)
        self.stop_all_button.setIcon(QIcon("/home/jack/AI-chat-PyQt/frontend_PyQt/icons/stop-button.png"))

        # Add widgets to the input layout.
        input_layout.addWidget(self.text_input)
        input_layout.addWidget(send_button)
        input_layout.addWidget(self.toggle_stt_button)
        input_layout.addWidget(self.toggle_tts_button)
        input_layout.addWidget(self.stop_all_button)

        layout.addWidget(scroll)
        layout.addWidget(input_widget)

        # ----------------------------------------------------
        # Initialize the WebSocket client (QThread)
        # ----------------------------------------------------
        self.ws_client = WebSocketClient()
        self.ws_client.message_received.connect(self.handle_message)
        self.ws_client.stt_text_received.connect(self.handle_stt_text)
        self.ws_client.connection_status.connect(self.handle_connection_status)

        # --- AUDIO-RELATED CODE ---
        # When PCM frames arrive, put them in a local queue for playback
        self.ws_client.audio_received.connect(self.on_audio_received)
        self.ws_client.start()

        # Connect button signals.
        send_button.clicked.connect(self.send_message)
        self.text_input.textChanged.connect(self.adjust_text_input_height)
        self.toggle_stt_button.clicked.connect(self.toggle_stt)
        self.toggle_tts_button.clicked.connect(self.toggle_tts)
        self.stop_all_button.clicked.connect(self.stop_tts_and_generation)

        # ----------------------------------------------------
        # AUDIO-RELATED CODE: Setup QAudioOutput
        # We'll play 24 kHz, 16-bit, mono PCM frames.
        # ----------------------------------------------------
        audio_format = QAudioFormat()
        audio_format.setSampleRate(24000)      # 24 kHz
        audio_format.setChannelCount(1)        # Mono
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)  # 16-bit

        print(f"Audio Format - Sample Rate: {audio_format.sampleRate()}")
        print(f"Audio Format - Channels: {audio_format.channelCount()}")
        print(f"Audio Format - Sample Format: {audio_format.sampleFormat()}")

        device = QMediaDevices.defaultAudioOutput()
        if device is None:
            print("Error: No audio output device found!")
        else:
            print(f"Using audio device: {device.description()}")

        # Create QAudioSink with format
        self.audio_sink = QAudioSink(device, audio_format)
        print(f"Audio sink created with state: {self.audio_sink.state()}")

        self.audio_sink.setVolume(1.0)
        print(f"Audio sink volume: {self.audio_sink.volume()}")

        # Create and setup QueueAudioDevice
        self.audio_device = QueueAudioDevice()
        self.audio_device.open(QIODevice.OpenModeFlag.ReadOnly)
        print(f"Audio device opened: {self.audio_device.isOpen()}")

        # Start the audio sink
        self.audio_sink.start(self.audio_device)
        print(f"Audio sink started with state: {self.audio_sink.state()}")

        # Setup audio queue and timer
        self.audio_queue = asyncio.Queue()
        self.audio_timer = QTimer()
        self.audio_timer.setInterval(10)  # check every 10ms
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
            # Finalize any in-progress assistant bubble before sending new user text
            self.finalize_assistant_bubble()
            self.add_message(text, True)
            asyncio.run(self.ws_client.send_message(text))
            self.text_input.clear()

    def handle_message(self, token):
        """
        Append each incoming token to a single assistant bubble.
        """
        if not self.assistant_bubble_in_progress:
            self.assistant_bubble_in_progress = MessageBubble("", is_user=False)
            self.chat_layout.insertWidget(self.chat_layout.count() - 1, self.assistant_bubble_in_progress)
        self.assistant_text_in_progress += token
        self.assistant_bubble_in_progress.update_text(self.assistant_text_in_progress)
        self.auto_scroll_chat()

    def finalize_assistant_bubble(self):
        """
        Finalize the assistant's bubble when done streaming (or when a stop is triggered).
        """
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
        """
        Toggle STT by sending a POST request to either /api/start-stt or /api/pause-stt.
        Updates the button's label based on the current STT state.
        """
        self.is_toggling_stt = True
        try:
            if not self.stt_enabled:
                resp = requests.post("http://localhost:8000/api/start-stt")
                resp.raise_for_status()
                self.stt_enabled = True
            else:
                resp = requests.post("http://localhost:8000/api/pause-stt")
                resp.raise_for_status()
                self.stt_enabled = False
            self.toggle_stt_button.setText("STT On" if self.stt_enabled else "STT Off")
        except requests.RequestException as e:
            print(f"Error toggling STT: {e}")
        finally:
            self.is_toggling_stt = False

    def toggle_tts(self):
        """
        Toggle TTS by calling /api/toggle-tts. If TTS is turned off,
        also call /api/stop-tts.
        The button's label is updated to reflect the current TTS state.
        """
        self.is_toggling_tts = True
        try:
            resp = requests.post("http://localhost:8000/api/toggle-tts")
            resp.raise_for_status()
            data = resp.json()
            self.tts_enabled = data.get("tts_enabled", self.tts_enabled)
            if not self.tts_enabled:
                stop_resp = requests.post("http://localhost:8000/api/stop-tts")
                stop_resp.raise_for_status()
            self.toggle_tts_button.setText("TTS On" if self.tts_enabled else "TTS Off")
        except requests.RequestException as e:
            print(f"Error toggling TTS: {e}")
        finally:
            self.is_toggling_tts = False

    def stop_tts_and_generation(self):
        """
        Stop both TTS playback and text generation:
         1. /api/stop-tts
         2. /api/stop-generation
        Finalizes any partial assistant bubble.
        """
        try:
            requests.post("http://localhost:8000/api/stop-tts").raise_for_status()
            requests.post("http://localhost:8000/api/stop-generation").raise_for_status()
        except requests.RequestException as e:
            print(f"Error stopping TTS and generation: {e}")
        self.finalize_assistant_bubble()

    # -----------------------------------------------------------------
    # AUDIO-RELATED CODE: Callback to store new PCM data from WebSocket
    # -----------------------------------------------------------------
    def on_audio_received(self, pcm_data: bytes):
        """Called when audio data arrives from WebSocket."""
        print(f"Frontend: Processing audio chunk of size: {len(pcm_data)} bytes")
        self.audio_queue.put_nowait(pcm_data)

    def feed_audio_data(self):
        """Called by QTimer to feed audio data to QAudioSink."""
        if self.audio_sink.state() != QAudio.State.ActiveState:
            print(f"Warning: Audio sink not active! State: {self.audio_sink.state()}")
            self.audio_sink.start(self.audio_device)  # Try to restart if not active
            return

        chunks_processed = 0
        total_bytes = 0
        
        try:
            while True:
                try:
                    pcm_chunk = self.audio_queue.get_nowait()
                    if pcm_chunk is None:  # Check for end-of-stream marker
                        print("Received end-of-stream marker")
                        break
                    chunk_size = len(pcm_chunk)
                    total_bytes += chunk_size
                    self.audio_device.audio_buffer.extend(pcm_chunk)
                    chunks_processed += 1
                except asyncio.QueueEmpty:
                    break
            
            if chunks_processed > 0:
                print(f"Audio Stats:")
                print(f"- Chunks processed: {chunks_processed}")
                print(f"- Total bytes processed: {total_bytes}")
                print(f"- Current buffer size: {len(self.audio_device.audio_buffer)}")
                print(f"- Sink state: {self.audio_sink.state()}")
                print(f"- Sink volume: {self.audio_sink.volume()}")
                
                # Check if we need to restart the audio sink
                if self.audio_sink.state() != QAudio.State.ActiveState:
                    print("Restarting audio sink...")
                    self.audio_sink.start(self.audio_device)
                    
        except Exception as e:
            print(f"Error in feed_audio_data: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ChatWindow()
    window.show()
    sys.exit(app.exec())