#!/usr/bin/env python3
import sys
import asyncio
import os
from PyQt6.QtWidgets import QApplication
from qasync import QEventLoop

from frontend.window_manager import WindowManager
from frontend.config import logger

if __name__ == '__main__':
    # Change to the project root directory to ensure paths are correct
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
    
    print("Starting Smart Display application...")
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    print("Creating window manager...")
    # Create window manager instead of directly creating a window
    window_manager = WindowManager()
    
    print("Initializing window manager...")
    # Initialize the window manager (will show the first window)
    window_manager.initialize()
    
    print("Starting event loop...")
    try:
        with loop:
            loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    finally:
        logger.info("Cleaning up before exit")
        window_manager.cleanup()
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
