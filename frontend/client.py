#!/usr/bin/env python3
import sys
import asyncio
from PyQt6.QtWidgets import QApplication
from qasync import QEventLoop
from frontend.main_window import MainWindow
from frontend.config import logger

if __name__ == '__main__':
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    window = MainWindow()
    window.apply_styling()
    window.show()
    
    try:
        with loop:
            loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    finally:
        logger.info("Cleaning up before exit")
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
