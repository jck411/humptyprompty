#!/usr/bin/env python3
"""
Main client application for the frontend.

This module serves as the entry point for the frontend application.
It initializes the application, sets up the event loop, and launches the main window.
"""
import sys
import asyncio
from PyQt6.QtWidgets import QApplication
from qasync import QEventLoop

from frontend.ui.chat_window import ChatWindow
from frontend.utils.logger import get_logger

logger = get_logger(__name__)

def main():
    """
    Main entry point for the application.
    
    Initializes the application, sets up the event loop, and launches the main window.
    """
    logger.info("Starting frontend client application")
    
    # Create the application
    app = QApplication(sys.argv)
    
    # Set up the event loop
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    # Create and show the main window
    window = ChatWindow()
    window.show()
    
    # Run the event loop
    logger.info("Running event loop")
    with loop:
        loop.run_forever()

if __name__ == '__main__':
    main()
