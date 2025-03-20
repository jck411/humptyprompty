#!/usr/bin/env python3
import sys
import os
import signal

from PySide6.QtCore import QObject, Slot, Signal, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

# Import frontend config
from frontend.config import SERVER_HOST, SERVER_PORT, WEBSOCKET_PATH, HTTP_BASE_URL, logger, setup_logger

# Import models
from frontend.models.ChatModel import ChatModel
from frontend.models.AudioManager import AudioManager
from frontend.models.AppManager import AppManager

# Import STT if needed
try:
    from frontend.stt.deepgram_stt import DeepgramSTT
    has_stt = True
except ImportError:
    logger.warning("DeepgramSTT module not found, STT functionality will be disabled")
    has_stt = False

class SttBridge(QObject):
    """Bridge for Speech-to-Text functionality"""
    textReceived = Signal(str)
    stateChanged = Signal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.stt = None
        
        if has_stt:
            try:
                self.stt = DeepgramSTT()
                # Connect STT signals
                self.stt.complete_utterance_received.connect(self.handle_text)
                self.stt.state_changed.connect(self.handle_state)
                logger.info("STT initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize STT: {e}")
                self.stt = None
    
    @Slot(str)
    def handle_text(self, text):
        """Handle complete STT text"""
        if not text.strip():
            return
            
        logger.info(f"STT complete text: '{text}'")
        self.textReceived.emit(text)
    
    @Slot(bool)
    def handle_state(self, is_listening):
        """Handle STT state changes"""
        logger.info(f"STT state changed: listening = {is_listening}")
        self.stateChanged.emit(is_listening)
    
    @Slot()
    def toggle(self):
        """Toggle STT state"""
        if self.stt:
            self.stt.toggle()
            logger.info("STT toggled")
    
    @Slot(bool)
    def set_enabled(self, enabled):
        """Set STT enabled state"""
        if self.stt and self.stt.is_enabled != enabled:
            self.stt.set_enabled(enabled)
            logger.info(f"STT set to: {enabled}")
    
    def cleanup(self):
        """Clean up STT resources"""
        if self.stt:
            self.stt.stop()
            logger.info("STT shutdown completed")

class QmlBridge(QObject):
    """Main bridge between QML and Python models"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.app_manager = AppManager()
        self.stt_bridge = SttBridge()
        self.chat_model = None
        self.audio_manager = None
        
        # Connect STT bridge to app manager
        self.stt_bridge.stateChanged.connect(self.app_manager.handle_stt_state_change)
    
    @Slot()
    def initialize_models(self):
        """Initialize all models and connect signals"""
        # Initialize chat model
        self.chat_model = ChatModel()
        
        # Set up WebSocket connection
        server_url = f"ws://{SERVER_HOST}:{SERVER_PORT}{WEBSOCKET_PATH}"
        logger.info(f"Connecting to WebSocket server at {server_url}")
        
        # Store the server URL in the ChatModel for reconnection
        self.chat_model.last_server_url = server_url
        self.chat_model.connectToServer(server_url)
        
        # Initialize the audio manager
        self.audio_manager = AudioManager()
        
        # Connect signals between components
        self.chat_model.audioReceived.connect(self.audio_manager.process_audio_data)
        self.chat_model.sttStateChanged.connect(self.stt_bridge.set_enabled)
        self.stt_bridge.textReceived.connect(self.chat_model.sendMessage)
        
        # Sync initial STT state if available
        if self.stt_bridge.stt:
            self.chat_model._stt_active = self.stt_bridge.stt.is_enabled
            logger.info(f"Initialized ChatModel STT state to: {self.stt_bridge.stt.is_enabled}")
        
        return self.chat_model
    
    @Slot()
    def cleanup(self):
        """Clean up all resources before shutting down"""
        # Clean up STT
        self.stt_bridge.cleanup()
        
        # Clean up audio manager
        if self.audio_manager:
            self.audio_manager.cleanup()
        
        # Clean up chat model and WebSocket
        if self.chat_model:
            self.chat_model.cleanup()
        
        logger.info("All resources cleaned up")

def main():
    # Set up application logger
    app_logger = setup_logger("app", level=logger.level)
    
    # Create application
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Smart Display")
    app.setOrganizationName("Home Assistant")
    
    # Set up signal handling for clean shutdown
    def signal_handler(signum, frame):
        app_logger.info(f"Received signal {signum}, shutting down")
        app.quit()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Set Material style for QML
    QQuickStyle.setStyle("Material")
    
    # Create QML engine
    engine = QQmlApplicationEngine()
    
    # Create bridge and initialize models
    bridge = QmlBridge()
    chat_model = bridge.initialize_models()
    
    # Expose objects to QML
    context = engine.rootContext()
    context.setContextProperty("bridge", bridge)
    context.setContextProperty("chatModel", chat_model)
    context.setContextProperty("sttBridge", bridge.stt_bridge)
    context.setContextProperty("appManager", bridge.app_manager)
    
    # Add import paths for QML
    engine.addImportPath(os.path.dirname(os.path.abspath(__file__)))
    
    # Load main QML file
    qml_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.qml")
    engine.load(QUrl.fromLocalFile(qml_file))
    
    # Check if QML loaded successfully
    if not engine.rootObjects():
        app_logger.error("Failed to load QML")
        sys.exit(-1)
    
    # Run the application
    exit_code = app.exec()
    
    # Clean up before exit
    bridge.cleanup()
    app_logger.info("Application shut down cleanly")
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
