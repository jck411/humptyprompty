#!/usr/bin/env python3
import sys
import asyncio
from PyQt6.QtWidgets import QApplication
from qasync import QEventLoop

from frontend.main_window import MainWindow
from frontend.screen_manager import ScreenManager
from frontend.config import logger
from frontend.style import DARK_COLORS
from frontend.screens import ClockScreen, ChatScreen, WeatherScreen, CalendarScreen, PhotoScreen

if __name__ == '__main__':
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    # Create main window (always in kiosk/fullscreen mode)
    main_window = MainWindow()
    
    # Create screen manager
    screen_manager = ScreenManager(main_window)
    
    # Connect theme toggle special command
    main_window.theme_changed.connect(lambda is_dark, colors: 
                                    [screen.update_colors(colors) for _, (_, screen) in screen_manager.screens.items()])
    
    # Create and add screens - pass main_window to each screen
    clock_screen = ClockScreen(main_window.colors)
    chat_screen = ChatScreen(main_window.colors)
    weather_screen = WeatherScreen(main_window.colors)
    calendar_screen = CalendarScreen(main_window.colors)
    photo_screen = PhotoScreen(main_window.colors)
    
    # Give each screen a reference to the main window
    for screen in [clock_screen, chat_screen, weather_screen, calendar_screen, photo_screen]:
        screen.main_window = main_window
    
    # Add screens to manager
    screen_manager.add_screen(clock_screen, "clock")
    screen_manager.add_screen(chat_screen, "chat")
    screen_manager.add_screen(weather_screen, "weather")
    screen_manager.add_screen(calendar_screen, "calendar")
    screen_manager.add_screen(photo_screen, "photo")
    
    # Set up rotation sequence and interval (30 seconds)
    # Chat screen is excluded from rotation
    screen_manager.set_rotation_sequence(
        ["clock", "weather", "calendar", "photo"], 
        30000
    )
    
    # Start with clock screen
    screen_manager.show_screen("clock")
    
    # Start auto-rotation immediately
    screen_manager.start_auto_rotation()
    
    # Show main window
    main_window.show()
    
    # Handle special navigation commands
    def handle_navigation(command):
        logger.info(f"Navigation requested to: {command}")
        if command == "toggle_theme":
            logger.info("Handling toggle_theme command")
            # Toggle theme in main window, which emits theme_changed signal
            main_window.toggle_theme()
            # The lambda connected to theme_changed should update all screens
            logger.info("Theme toggle complete")
        elif command == "chat":
            # When navigating to chat, stop auto-rotation
            screen_manager.stop_auto_rotation()
            screen_manager.show_screen("chat")
        elif command in screen_manager.screens:
            # For other screens, ensure auto-rotation is running
            if command != "chat" and not screen_manager.auto_rotate:
                screen_manager.start_auto_rotation()
            screen_manager.show_screen(command)
        else:
            logger.warning(f"Unknown navigation command: {command}")
    
    # Connect navigation signal to handle special commands
    for _, (_, screen) in screen_manager.screens.items():
        screen.navigation_requested.connect(handle_navigation)
    
    # Connect screen changed signal for logging
    screen_manager.screen_changed.connect(lambda name: logger.debug(f"Screen changed to: {name}"))
    
    # Start event loop
    try:
        with loop:
            loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    finally:
        logger.info("Cleaning up before exit")
        # Clean up screen manager
        screen_manager.cleanup()
        
        # Cancel any pending tasks
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
