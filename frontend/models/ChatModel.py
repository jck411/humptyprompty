import json
import asyncio
import logging
from PySide6.QtCore import QObject, Signal, Slot, Property, QUrl, QTimer
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtNetwork import QAbstractSocket

class ChatModel(QObject):
    # Signals to communicate with QML
    messageReceived = Signal(str)
    assistantMessageInProgress = Signal(str)
    sttStateChanged = Signal(bool)
    ttsStateChanged = Signal(bool)
    audioReceived = Signal(bytes)
    connectionStatusChanged = Signal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # WebSocket setup
        self.ws = QWebSocket()
        self.ws.textMessageReceived.connect(self.on_text_message)
        self.ws.binaryMessageReceived.connect(self.on_binary_message)
        self.ws.connected.connect(self.on_connected)
        self.ws.disconnected.connect(self.on_disconnected)
        self.ws.error.connect(self.on_error)
        
        # Message history
        self.messages = []
        
        # State tracking
        self._stt_active = False
        self._tts_active = True
        self._is_connected = False
        
        # Audio playing state
        self.tts_audio_playing = False
        
        # Current assistant message being built
        self.current_assistant_message = ""
        self.is_new_message = True
        
        # Store the last server URL for reconnection
        self.last_server_url = None
        
    @Slot(str)
    def connectToServer(self, server_url):
        """Connect to the WebSocket server"""
        logging.info(f"Connecting to WebSocket server at {server_url}")
        
        # Store the server URL for reconnection
        self.last_server_url = server_url
        
        # Connect to the server
        self.ws.open(QUrl(server_url))
    
    @Slot(str)
    def sendMessage(self, message):
        """Send a message to the server"""
        if self.ws.state() == QAbstractSocket.SocketState.ConnectedState:
            # Reset the current assistant message for the new conversation turn
            self.current_assistant_message = ""
            self.is_new_message = True
            
            # Add the user message to history
            self.messages.append({"sender": "user", "text": message})
            
            # Send the message to the server
            payload = json.dumps({
                "action": "chat",
                "messages": self.messages
            })
            self.ws.sendTextMessage(payload)
            logging.debug(f"Sent message: {message}")
            
            # Emit signal for the UI to display the user message
            # This is necessary for STT-generated messages to appear in the chat
            self.messageReceived.emit(message)
        else:
            logging.error("Cannot send message: WebSocket not connected")
            # Try to reconnect
            self.reconnect()
    
    @Slot()
    def clearChat(self):
        """Clear the chat history"""
        self.messages.clear()
        self.current_assistant_message = ""
        self.is_new_message = True
        logging.info("Chat history cleared")
        
    @Slot(result="QVariantList")
    def getMessageHistory(self):
        """Return the message history in a format suitable for QML ListView"""
        qml_messages = []
        for msg in self.messages:
            qml_messages.append({
                "text": msg["text"],
                "isUser": msg["sender"] == "user"
            })
        return qml_messages
    
    @Slot()
    def toggleStt(self):
        """Toggle STT state"""
        # Toggle the state
        new_state = not self._stt_active
        self._stt_active = new_state
        
        # Emit the signal with the new state
        self.sttStateChanged.emit(new_state)
        logging.info(f"STT toggled to: {new_state}")
        return new_state  # Return the new state in case it's needed
    
    @Slot()
    def toggleTts(self):
        """Toggle TTS state on the server"""
        # This will send a request to the server to toggle TTS
        if self.ws.state() == QAbstractSocket.SocketState.ConnectedState:
            payload = json.dumps({"action": "toggle-tts"})
            self.ws.sendTextMessage(payload)
            logging.info("Sent TTS toggle request to server")
        else:
            logging.error("Cannot toggle TTS: WebSocket not connected")
            # Try to reconnect
            self.reconnect()
    
    @Slot()
    def stopGeneration(self):
        """Stop text generation and audio playback"""
        if self.ws.state() == QAbstractSocket.SocketState.ConnectedState:
            stop_gen_payload = json.dumps({"action": "stop-generation"})
            stop_audio_payload = json.dumps({"action": "stop-audio"})
            
            self.ws.sendTextMessage(stop_gen_payload)
            self.ws.sendTextMessage(stop_audio_payload)
            logging.info("Sent stop generation and audio requests")
            
            # Emit signal to notify QML that audio stopped
            self.audioReceived.emit(b'audio:')  # Empty audio to mark end of stream
        else:
            logging.error("Cannot stop generation: WebSocket not connected")
            # Try to reconnect
            self.reconnect()
    
    def on_text_message(self, message):
        """Handle incoming text messages from the WebSocket"""
        try:
            data = json.loads(message)
            logging.info(f"Received message: {data}")
            
            msg_type = data.get("type")
            if msg_type == "stt":
                stt_text = data.get("stt_text", "")
                logging.info(f"Processing STT text immediately: {stt_text}")
                # Handle in QML
            elif msg_type == "stt_state":
                is_listening = data.get("is_listening", False)
                logging.info(f"Updating STT state: listening = {is_listening}")
                self._stt_active = is_listening
                self.sttStateChanged.emit(is_listening)
            elif msg_type == "tts_state":
                is_enabled = data.get("is_enabled", False)
                logging.info(f"Updating TTS state: enabled = {is_enabled}")
                self._tts_active = is_enabled
                self.ttsStateChanged.emit(is_enabled)
            elif "content" in data:
                # Get the new content token
                content_token = data["content"]
                logging.info(f"Received content token: {content_token}")
                
                # Check if this is a new message or continuing an existing one
                # If the token starts with a space or punctuation, it's likely continuing the previous message
                # Otherwise, it might be a new message (but we'll still append it)
                if self.is_new_message:
                    self.current_assistant_message = content_token
                    self.is_new_message = False
                else:
                    # Append the token to the current message, preserving exact formatting
                    self.current_assistant_message += content_token
                
                # Update the message in history
                self.handle_assistant_message(self.current_assistant_message)
                
                # Emit the signal with the full message so far
                self.assistantMessageInProgress.emit(self.current_assistant_message)
                logging.info(f"Emitted assistantMessageInProgress with full message")
                
                # If this is a "done" message, reset for the next message
                if data.get("done", False):
                    self.messageReceived.emit(self.current_assistant_message)
                    self.is_new_message = True
            else:
                logging.warning(f"Unknown message type: {data}")
        except json.JSONDecodeError:
            logging.error("Failed to parse JSON message")
            logging.error(f"Raw message: {message}")
        except Exception as e:
            logging.error(f"Error processing message: {e}")
    
    def on_binary_message(self, message):
        """Handle incoming binary messages (audio data)"""
        try:
            # Convert QByteArray to bytes
            message_bytes = bytes(message)
            
            if message_bytes.startswith(b'audio:'):
                audio_data = message_bytes[len(b'audio:'):]
                logging.debug(f"Received audio chunk of size: {len(audio_data)} bytes")
                
                # Mark TTS as playing if this is a non-empty audio chunk
                if audio_data:
                    self.tts_audio_playing = True
                else:
                    # Empty audio chunk marks end of stream
                    self.tts_audio_playing = False
                
                # Forward the audio data to QML/client
                self.audioReceived.emit(message_bytes)
            else:
                logging.warning("Received binary message without audio prefix")
                self.audioReceived.emit(b'audio:' + message_bytes)
        except Exception as e:
            logging.error(f"Error processing binary message: {e}")
    
    def on_error(self, error_code):
        """Handle WebSocket errors"""
        logging.error(f"WebSocket error: {error_code} - {self.ws.errorString()}")
        self._is_connected = False
        self.connectionStatusChanged.emit(False)
        
        # Try to reconnect after a short delay
        QTimer.singleShot(2000, self.reconnect)
    
    def handle_assistant_message(self, message):
        """Add assistant message to history"""
        # Find if there's an existing assistant message in progress
        for i, msg in enumerate(self.messages):
            if msg["sender"] == "assistant" and i == len(self.messages) - 1:
                # Update the existing message
                self.messages[i]["text"] = message
                return
                
        # If no existing message found, add a new one
        self.messages.append({"sender": "assistant", "text": message})
        
    def on_connected(self):
        """Handle WebSocket connected event"""
        logging.info("WebSocket connected successfully")
        self._is_connected = True
        self.connectionStatusChanged.emit(True)
    
    def on_disconnected(self):
        """Handle WebSocket disconnected event"""
        logging.info("WebSocket disconnected")
        self._is_connected = False
        self.connectionStatusChanged.emit(False)
        
        # Attempt to reconnect after a short delay
        QTimer.singleShot(2000, self.reconnect)
    
    def reconnect(self):
        """Attempt to reconnect to the WebSocket server"""
        if self.ws.state() != QAbstractSocket.SocketState.ConnectedState:
            logging.info("Attempting to reconnect to WebSocket server")
            
            # Use the last server URL if available, otherwise use a default URL
            if self.last_server_url:
                url = self.last_server_url
            else:
                # Get the current URL from the WebSocket
                url = self.ws.requestUrl().toString()
                if not url:
                    # Use a default URL if none is set
                    url = "ws://localhost:8000/ws"
            
            # Reconnect
            logging.info(f"Reconnecting to {url}")
            self.connectToServer(url)
    
    # Properties exposed to QML
    @Property(bool)
    def sttActive(self):
        return self._stt_active
        
    @Property(bool)
    def ttsActive(self):
        return self._tts_active
        
    @Property(bool)
    def isConnected(self):
        return self._is_connected
