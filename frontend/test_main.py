#!/usr/bin/env python3
# test_main.py - A simplified version of the frontend to test

import sys
import asyncio
import logging
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QTimer
from qasync import QEventLoop
from chat_backend import ChatBackend

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
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("stt", backend.stt)
    engine.rootContext().setContextProperty("wsClient", backend.ws_client)
    
    # Load simple test QML instead of the full application
    logger.info("Loading test QML file")
    engine.load("test_qml/test.qml")
    
    # Check if QML loaded successfully
    if not engine.rootObjects():
        logger.error("Failed to load QML - no root objects")
        sys.exit("Error: Failed to load QML.")
    else:
        root_obj = engine.rootObjects()[0]
        logger.info(f"QML loaded successfully. Root object: {root_obj}")
        logger.info(f"Window visible: {root_obj.isVisible()}")
        
        # Position window in the top-left corner to ensure it's visible
        root_obj.setX(50)
        root_obj.setY(50)
        
        # Make sure it's visible
        QTimer.singleShot(1000, lambda: logger.info("Window should be visible now"))
    
    return engine

if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    logger.info(f"Created QGuiApplication instance: {app}")
    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    logger.info("Event loop created and set")

    # Initialize the backend and QML engine asynchronously
    with loop:
        logger.info("Starting application initialization")
        loop.run_until_complete(init_application())
        logger.info("Application initialized, starting event loop")
        loop.run_forever() 