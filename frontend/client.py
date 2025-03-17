#!/usr/bin/env python3
"""
Main entry point for the Smart Display application.
Creates and runs the main container window.
"""

import os
import sys
import asyncio
import signal
import qasync
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer

from frontend.config import logger
from frontend.container_window import create_container_window

def main():
    """
    Main application entry point.
    Sets up the event loop and container window.
    """
    logger.info("Starting Smart Display application...")
    
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Important: Set this flag to ensure global keyboard events are captured
    app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
    
    # Create the qasync loop
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    # Create window manager
    logger.info("Creating window manager...")
    window = create_container_window()
    
    # Initialize window manager
    logger.info("Initializing window manager...")
    
    # Set up signal handlers for clean shutdown
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        window.close()
        app.quit()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Define the cleanup coroutine
    async def cleanup_async():
        if hasattr(window, 'cleanup'):
            try:
                await window.cleanup()
            except Exception as e:
                logger.error(f"Error during window manager cleanup: {e}")
    
    # Register cleanup to run when the app is about to quit
    app.aboutToQuit.connect(lambda: asyncio.ensure_future(cleanup_async()))
    
    # Start the event loop
    logger.info("Starting event loop...")
    
    # Run the integrated event loop - this will handle both Qt and asyncio events
    with loop:
        return loop.run_forever()

if __name__ == "__main__":
    try:
        # Run the main function directly
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Error in main application: {e}")
        sys.exit(1)
