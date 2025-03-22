# main.py
import sys
import asyncio
import logging
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QTimer, QCoreApplication
from qasync import QEventLoop
from chat_backend import ChatBackend

# Import server configuration (used in backend)
from config import SERVER_HOST, SERVER_PORT, WEBSOCKET_PATH, HTTP_BASE_URL

# Set up root logger to show all messages
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global event loop access
global_loop = None
global_chat_backend = None
shutdown_initiated = False

def get_event_loop():
    """Helper function to get the global event loop"""
    global global_loop
    return global_loop

def get_chat_backend():
    """Helper function to get the global chat backend instance"""
    global global_chat_backend
    return global_chat_backend

def safe_disconnect_signals(obj):
    """Safely disconnect all signals from an object"""
    if not obj:
        return
        
    # Get all signals (attributes that are Signal objects)
    for attr_name in dir(obj):
        try:
            attr = getattr(obj, attr_name)
            if isinstance(attr, type) and hasattr(attr, 'disconnect'):
                try:
                    attr.disconnect()
                except:
                    pass  # Ignore errors when disconnecting
        except:
            pass  # Skip any attribute that causes errors

async def init_application():
    """Initialize the application, UI, and backend components"""
    global global_chat_backend
    
    # Initialize the backend (which creates STT and WebSocket objects)
    # but don't start the WebSocket connection yet
    logger.info("Initializing ChatBackend")
    backend = ChatBackend()
    global_chat_backend = backend
    
    # Set up QML engine and expose our backend objects to QML
    logger.info("Setting up QML engine")
    engine = QQmlApplicationEngine()
    
    # Register Python objects with QML
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("stt", backend.stt)
    engine.rootContext().setContextProperty("wsClient", backend.ws_client)
    
    # Load the main QML file
    logger.info("Loading QML file")
    engine.load("frontend/qml/MainWindow.qml")
    
    # Check if QML loaded successfully
    if not engine.rootObjects():
        logger.error("Failed to load QML - no root objects")
        sys.exit("Error: Failed to load QML.")
    else:
        # Get the root window
        root_obj = engine.rootObjects()[0]
        logger.info("QML loaded successfully")
        
        # Position window to be more visible
        root_obj.setX(100)
        root_obj.setY(100)
    
    # Initialize backend AFTER UI is set up, with extended timeout
    try:
        # Schedule the initialization to happen after the event loop starts
        # This ensures that the WebSocket connection is established after the UI is set up
        # and the event loop is running
        asyncio.create_task(backend.initialize())
        logger.info("Backend initialization scheduled")
    except Exception as e:
        logger.error(f"Error scheduling backend initialization: {e}")
    
    return engine

def initiate_shutdown():
    """Initiate application shutdown safely without recursion"""
    global shutdown_initiated
    
    # Only do this once
    if shutdown_initiated:
        return
        
    shutdown_initiated = True
    print("Starting application shutdown...")
    
    # Mark WebSocket client as not running first
    if global_chat_backend and hasattr(global_chat_backend, 'ws_client'):
        global_chat_backend.ws_client.running = False
        
    # Cancel any running tasks
    if global_loop:
        try:
            tasks = list(asyncio.all_tasks(global_loop))
            if tasks:
                print(f"Cancelling {len(tasks)} pending tasks")
                for task in tasks:
                    if not task.done():
                        task.cancel()
        except Exception as e:
            print(f"Error cancelling tasks: {e}")
    
    # The actual quit will happen automatically as the loop exits

def signal_handler(sig, frame):
    """Handle SIGINT (Ctrl+C) to gracefully shutdown the application"""
    print("SIGINT received, shutting down...")
    if not shutdown_initiated:
        initiate_shutdown()
    QCoreApplication.quit()

if __name__ == "__main__":
    # Create the Qt application
    app = QGuiApplication(sys.argv)
    
    # Create a standard event loop for asyncio operations
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Set global event loop for access from other modules
    global_loop = loop
    
    # Connect aboutToQuit directly to our shutdown function
    app.aboutToQuit.connect(initiate_shutdown)
    
    # Initialize the backend and QML engine
    backend = ChatBackend()
    global_chat_backend = backend
    
    # Set up QML engine and expose our backend objects to QML
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("stt", backend.stt)
    engine.rootContext().setContextProperty("wsClient", backend.ws_client)
    
    # Load the main QML file
    engine.load("frontend/qml/MainWindow.qml")
    
    # Check if QML loaded successfully
    if not engine.rootObjects():
        logger.error("Failed to load QML - no root objects")
        sys.exit("Error: Failed to load QML.")
    
    # Get the root window and position it
    root_obj = engine.rootObjects()[0]
    root_obj.setX(100)
    root_obj.setY(100)
    
    # Start the WebSocket connection in a separate thread
    def run_async_init():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(backend.initialize())
    
    import threading
    init_thread = threading.Thread(target=run_async_init)
    init_thread.daemon = True
    init_thread.start()
    
    # Start the Qt event loop
    print("Application initialized and running. Close the window to exit.")
    sys.exit(app.exec())
