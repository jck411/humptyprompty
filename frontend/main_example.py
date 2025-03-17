#!/usr/bin/env python3
"""
Main application entry point for the Smart Display using QStackedWidget approach.

This example demonstrates how to use the ContainerWindow to manage multiple screens
within a single window, avoiding any desktop background visibility during transitions.
"""

import sys
import asyncio
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from frontend.container_window import create_container_window
from frontend.config import logger

async def main_async():
    """Async main entry point for the application."""
    # Create and set up the application
    app = QApplication(sys.argv)
    
    # Create and display the single container window
    window = create_container_window()
    
    # Configure rotation if desired
    # window.screen_manager.set_rotation_interval(30000)  # 30 seconds
    # window.screen_manager.toggle_rotation(True)
    
    # For kiosk mode (optional)
    # window.toggle_kiosk_mode()
    
    # Set up event loop integration
    def process_events():
        app.processEvents()
    
    # Create a timer to process Qt events in the asyncio loop
    event_timer = QTimer()
    event_timer.timeout.connect(process_events)
    event_timer.start(10)  # 10ms interval
    
    # Set up application exit
    app.lastWindowClosed.connect(app.quit)
    
    # Start app event loop with asyncio integration
    exit_code = 0
    try:
        # Keep the event loop running as long as the app is running
        while app.topLevelWindows():
            await asyncio.sleep(0.1)
            if not app.topLevelWindows():
                break
                
        # Clean up resources
        if hasattr(window, 'cleanup'):
            await window.cleanup()
            
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
        exit_code = 1
    finally:
        # Stop the event timer
        event_timer.stop()
        
    # Return exit code
    return exit_code

def main():
    """Main entry point for the application."""
    # Set up asyncio event loop
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Run the async main function
    exit_code = asyncio.run(main_async())
    
    # Exit with the appropriate code
    sys.exit(exit_code)

if __name__ == "__main__":
    main() 