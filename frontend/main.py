# main.py
import sys, asyncio
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from qasync import QEventLoop
from chat_backend import ChatBackend

if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    # Initialize backend logic
    backend = ChatBackend()

    # Set up QML engine and context properties
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("stt", backend.stt)
    engine.rootContext().setContextProperty("wsClient", backend.ws_client)

    # Load the QML UI (MainWindow.qml)
    engine.load("MainWindow.qml")
    if not engine.rootObjects():
        sys.exit("Error: Failed to load QML")

    # Start the Qt event loop (integrated with asyncio)
    try:
        with loop:
            loop.run_forever()
    except KeyboardInterrupt:
        print("Application interrupted by user")
