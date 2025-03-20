#!/usr/bin/env python3
import sys
import os
import logging
import json
import asyncio
import signal

from PySide6.QtCore import QObject, Slot, Signal, QUrl, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType, qmlRegisterSingletonType
from PySide6.QtQuickControls2 import QQuickStyle

# Import frontend config
from frontend.config import SERVER_HOST, SERVER_PORT, WEBSOCKET_PATH, HTTP_BASE_URL, logger

# Import models
from frontend.models.ChatModel import ChatModel
from frontend.models.AudioManager import AudioManager

# Import STT if needed
try:
    from frontend.stt.deepgram_stt import DeepgramSTT
    has_stt = True
except ImportError:
    logger.warning("DeepgramSTT module not found, STT functionality will be disabled")
    has_stt = False

# QML Bridge - Handles connections between QML and Python
class QmlBridge(QObject):
    # Signals to send data to QML
    sttTextReceived = Signal(str)
    sttStateChanged = Signal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.chat_model = None
        self.audio_manager = None
        self.stt = None
        
        # Initialize STT if available
        if has_stt:
            try:
                self.stt = DeepgramSTT()
                # Connect STT signals
                self.stt.complete_utterance_received.connect(self.handle_stt_text)
                self.stt.state_changed.connect(self.handle_stt_state)
                logger.info("STT initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize STT: {e}")
                self.stt = None
    
    @Slot(str)
    def handle_stt_text(self, text):
        """Handle complete STT text"""
        logger.info(f"STT complete text: {text}")
        self.sttTextReceived.emit(text)
    
    @Slot(bool)
    def handle_stt_state(self, is_listening):
        """Handle STT state changes"""
        logger.info(f"STT state changed: listening = {is_listening}")
        self.sttStateChanged.emit(is_listening)
    
    @Slot()
    def initialize_chat_model(self):
        """Initialize the chat model and connect signals"""
        self.chat_model = ChatModel()
        
        # Set up WebSocket connection
        server_url = f"ws://{SERVER_HOST}:{SERVER_PORT}{WEBSOCKET_PATH}"
        logger.info(f"Connecting to WebSocket server at {server_url}")
        
        # Store the server URL in the ChatModel for reconnection
        self.chat_model.last_server_url = server_url
        
        # Connect to the server
        self.chat_model.connectToServer(server_url)
        
        # Initialize the audio manager
        self.audio_manager = AudioManager()
        
        # Connect signals between chat model and audio manager
        self.chat_model.audioReceived.connect(self.audio_manager.process_audio_data)
        
        # When our Python-side toggle methods are called from QML, we need to update the STT
        self.chat_model.sttStateChanged.connect(self.toggle_stt_from_model)
        
        return self.chat_model
    
    @Slot(bool)
    def toggle_stt_from_model(self, enabled):
        """Toggle STT based on model state change"""
        if self.stt:
            self.stt.set_enabled(enabled)
            logger.info(f"STT toggled from model to: {enabled}")
    
    @Slot()
    def toggle_stt(self):
        """Toggle STT state"""
        if self.stt:
            self.stt.toggle()
            logger.info("STT toggled")
    
    @Slot()
    def cleanup(self):
        """Clean up resources before shutting down"""
        if self.stt:
            self.stt.stop()
        
        if self.audio_manager:
            self.audio_manager.cleanup()
        
        # Disconnect WebSocket signals to avoid errors when the ChatModel is deleted
        if self.chat_model and hasattr(self.chat_model, 'ws'):
            try:
                # Disconnect all signals from the WebSocket
                self.chat_model.ws.connected.disconnect()
                self.chat_model.ws.disconnected.disconnect()
                self.chat_model.ws.error.disconnect()
                self.chat_model.ws.textMessageReceived.disconnect()
                self.chat_model.ws.binaryMessageReceived.disconnect()
                logger.info("WebSocket signals disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting WebSocket signals: {e}")
        
        logger.info("Resources cleaned up")

# Main entry point
def main():
    # Set up logging
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Create application
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Smart Display")
    app.setOrganizationName("Home Assistant")
    
    # Set up signal handling for clean shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down")
        app.quit()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Set Material style for QML
    QQuickStyle.setStyle("Material")
    
    # Create QML engine
    engine = QQmlApplicationEngine()
    
    # Create bridge and register singleton instance
    bridge = QmlBridge()
    
    # Register our Python types to QML
    # Create an instance of ChatModel
    chat_model = bridge.initialize_chat_model()
    
    # Expose bridge and chatModel to QML
    context = engine.rootContext()
    context.setContextProperty("bridge", bridge)
    context.setContextProperty("chatModel", chat_model)
    
    # Connect bridge signals to chatModel
    bridge.sttTextReceived.connect(lambda text: chat_model.sendMessage(text) if text.strip() else None)
    
    # Register QML components (could also be done with imports in QML)
    # qmlRegisterType(...)
    
    # Add import paths for QML - Using direct file paths instead of QRC resources
    # Note: Once PySide6 is installed, you can compile resources.qrc with:
    # pyside6-rcc frontend/resources.qrc -o frontend/resources.py
    # and then import them with: import frontend.resources
    engine.addImportPath(os.path.dirname(os.path.abspath(__file__)))
    
    # Load main QML file
    qml_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.qml")
    engine.load(QUrl.fromLocalFile(qml_file))
    
    # Check if QML loaded successfully
    if not engine.rootObjects():
        logger.error("Failed to load QML")
        sys.exit(-1)
    
    # Run the application
    exit_code = app.exec()
    
    # Clean up before exit
    bridge.cleanup()
    logger.info("Application shut down cleanly")
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
