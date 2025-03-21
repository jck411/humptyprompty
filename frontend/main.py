# main.py
import sys
import asyncio
import logging
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QTimer
from qasync import QEventLoop
from chat_backend import ChatBackend

# Import server configuration (used in backend)
from config import SERVER_HOST, SERVER_PORT, WEBSOCKET_PATH, HTTP_BASE_URL

# Set up root logger to show all messages
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_application():
    # Initialize the backend (which creates STT and WebSocket objects)
    logger.info("Initializing ChatBackend")
    backend = ChatBackend()
    await backend.initialize()
    
    # Set up QML engine and expose our backend objects to QML
    logger.info("Setting up QML engine")
    engine = QQmlApplicationEngine()
    
    # Register Python objects with QML
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("stt", backend.stt)
    engine.rootContext().setContextProperty("wsClient", backend.ws_client)
    
    # Load the main QML file
    logger.info("Loading QML file")
    engine.load("qml/MainWindow.qml")
    
    # Check if QML loaded successfully
    if not engine.rootObjects():
        logger.error("Failed to load QML - no root objects")
        sys.exit("Error: Failed to load QML.")
    else:
        # Get the root window
        root_obj = engine.rootObjects()[0]
        logger.info(f"QML loaded successfully")
        
        # Position window to be more visible
        root_obj.setX(100)
        root_obj.setY(100)
    
    return engine

if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    # Initialize the backend and QML engine asynchronously
    with loop:
        loop.run_until_complete(init_application())
        loop.run_forever()
