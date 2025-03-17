#!/usr/bin/env python3
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from frontend.style import DARK_COLORS, LIGHT_COLORS, generate_main_stylesheet
from frontend.config import logger

class BaseWindow(QMainWindow):
    """
    Base window class that provides common functionality for all screen types.
    Subclasses should implement the setup_ui_content method to add their specific content.
    """
    # Signals
    theme_changed = pyqtSignal(bool)  # True for dark mode, False for light mode
    window_closed = pyqtSignal()
    window_switch_requested = pyqtSignal(str)  # Emitted when user wants to switch to another window
    
    # Dictionary mapping window types to their corresponding classes
    # This will be populated by each window class during module initialization
    WINDOW_CLASSES = {}
    
    @classmethod
    def register_window_class(cls, window_type, window_class):
        """Register a window class with its type identifier"""
        cls.WINDOW_CLASSES[window_type] = window_class
        
    def __init__(self, title="Smart Display"):
        super().__init__()
        self.setWindowTitle(title)
        self.setMinimumSize(800, 600)
        
        # Initialize state
        self.is_dark_mode = True
        self.colors = DARK_COLORS
        self.is_kiosk_mode = False
        self.previous_geometry = None  # Store window geometry for proper restoration
        
        # Setup UI components
        self.setup_ui()
        
        # Initialize theme
        self.apply_styling()
    
    def is_primary_window(self):
        """
        Determine if this window is the primary window (e.g., ChatWindow).
        Subclasses should override this method to return True if they are the primary window.
        
        For backward compatibility, this also checks if the class name is 'ChatWindow'.
        """
        # For backward compatibility, check the class name
        return self.__class__.__name__.lower() == 'chatwindow'
    
    def get_default_window_to_switch(self):
        """
        Return the default window to switch to when exiting this window.
        Subclasses can override this to specify a different default window.
        """
        return "chat"
    
    def setup_ui(self):
        """Setup the base UI components"""
        # Create central widget and main layout
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)
        
        # Create top layout for navigation buttons when in kiosk mode
        self.top_layout = QHBoxLayout()
        self.main_layout.addLayout(self.top_layout)
        
        # Create navigation buttons layout (hidden by default)
        self.nav_layout = QHBoxLayout()
        self.nav_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.top_layout.addWidget(QWidget())  # Placeholder for consistent layout
        self.top_layout.addLayout(self.nav_layout)
        
        # Create content area - to be filled by subclasses
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.content_widget, 1)  # Add with stretch factor
        
        # Call the method that subclasses will implement
        self.setup_ui_content()
        
        # Hide navigation buttons by default (only shown in kiosk mode)
        self.show_navigation_buttons(False)
    
    def setup_ui_content(self):
        """
        To be implemented by subclasses to add their specific content.
        """
        pass
    
    def apply_styling(self):
        """Apply stylesheet to the application"""
        self.setStyleSheet(generate_main_stylesheet(self.colors))
    
    def add_navigation_button(self, window_name, display_name):
        """
        Add a navigation button for switching to another window
        
        This method creates a button that emits the window_switch_requested signal
        when clicked, which is then handled by the WindowManager.
        
        Args:
            window_name (str): The name/type of the window to switch to
            display_name (str): The text to display on the button
            
        Returns:
            QPushButton: The created button
        """
        button = QPushButton(display_name)
        button.setFixedHeight(32)
        button.clicked.connect(lambda: self.window_switch_requested.emit(window_name))
        self.nav_layout.addWidget(button)
        return button
    
    def toggle_theme(self):
        """Toggle between light and dark themes"""
        self.is_dark_mode = not self.is_dark_mode
        self.colors = DARK_COLORS if self.is_dark_mode else LIGHT_COLORS
        self.apply_styling()
        
        # Update child components if they exist and have the appropriate update methods
        self._update_theme_in_components()
        
        # Emit signal for any external components that need to respond to theme changes
        self.theme_changed.emit(self.is_dark_mode)
    
    def _update_theme_in_components(self):
        """
        Update theme colors in all child components that support theme changes.
        This method looks for components with update_icons or update_colors methods
        and calls them with the appropriate parameters.
        """
        # Common component attribute names used in subclasses
        component_attributes = [
            'top_buttons', 'chat_area', 'input_area', 
            'clock_display', 'settings_panel',  # Add other potential components here
        ]
        
        for attr_name in component_attributes:
            component = getattr(self, attr_name, None)
            if component:
                # Update icons if the component has this method
                if hasattr(component, 'update_icons'):
                    component.update_icons(self.is_dark_mode)
                
                # Update colors if the component has this method
                if hasattr(component, 'update_colors'):
                    component.update_colors(self.colors)

    def _update_kiosk_mode_in_components(self):
        """
        Update kiosk mode state in all child components that support kiosk mode.
        This method looks for components with set_kiosk_mode method and calls it 
        with the current kiosk mode state. It also handles visibility of components
        that should be hidden in kiosk mode (like input areas).
        """
        # Common component attribute names used in subclasses
        component_attributes = [
            'top_buttons', 'chat_area', 'input_area', 
            'clock_display', 'settings_panel',  # Add other potential components here
        ]
        
        for attr_name in component_attributes:
            component = getattr(self, attr_name, None)
            if component:
                # Update kiosk mode if the component has this method
                if hasattr(component, 'set_kiosk_mode'):
                    component.set_kiosk_mode(self.is_kiosk_mode)
                
                # Special handling for input area - hide in kiosk mode
                if attr_name == 'input_area':
                    component.setVisible(not self.is_kiosk_mode)
                    logger.info(f"{self.__class__.__name__}: Input area visibility set to {not self.is_kiosk_mode}")
    
    def toggle_kiosk_mode(self):
        """Toggle fullscreen/kiosk mode"""
        # Save current state before toggling
        was_kiosk_mode = self.is_kiosk_mode
        self.is_kiosk_mode = not was_kiosk_mode
        
        logger.info(f"{self.__class__.__name__}: Toggling kiosk mode to {self.is_kiosk_mode}")
        
        # Store current geometry before changing window state if not already stored
        if not was_kiosk_mode:
            self.previous_geometry = self.geometry()
        
        # Hide the window while we change its properties
        self.hide()
        
        if self.is_kiosk_mode:
            # Enter kiosk mode
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.show()
            # Call showFullScreen directly without delay
            self.showFullScreen()
        else:
            # Exit kiosk mode
            self.setWindowFlags(Qt.WindowType.Window)
            self.show()
            # Call showNormal directly without delay
            self.showNormal()
            
            # Restore previous geometry if available
            if self.previous_geometry:
                self.setGeometry(self.previous_geometry)
            
            # Hide navigation buttons
            self.show_navigation_buttons(False)
        
        # Update all UI components based on kiosk mode
        self._update_kiosk_mode_in_components()
    
    def show_navigation_buttons(self, visible):
        """Show or hide navigation buttons"""
        for i in range(self.nav_layout.count()):
            widget = self.nav_layout.itemAt(i).widget()
            if widget:
                widget.setVisible(visible)
    
    def keyPressEvent(self, event):
        """Handle key press events"""
        # ESC key behavior
        if event.key() == Qt.Key.Key_Escape:
            # If this is the primary window (e.g., ChatWindow), toggle kiosk mode
            if self.is_primary_window():
                self.toggle_kiosk_mode()
                
                # If toggling to kiosk mode and we have at least one navigation window available,
                # switch to clock window after a short delay
                if self.is_kiosk_mode and self.nav_layout.count() > 0:
                    # Use the window_switch_requested signal to let the WindowManager handle the switch
                    # This ensures proper state management and transitions
                    window_type = "clock"
                    QTimer.singleShot(500, lambda: self.window_switch_requested.emit(window_type))
            # For other windows in kiosk mode, return to the default window (typically chat)
            elif self.is_kiosk_mode:
                window_type = self.get_default_window_to_switch()
                self.window_switch_requested.emit(window_type)
        else:
            super().keyPressEvent(event)
    
    def switch_window(self, window_type):
        """
        Switch to the specified window type using the WINDOW_CLASSES dictionary
        
        This method creates and shows a new window instance directly, without going
        through the WindowManager. For most cases, it's better to emit the 
        window_switch_requested signal to let the WindowManager handle the switch
        properly with state management and transitions.
        
        Use this method when you need direct control over window switching and
        don't need the WindowManager's features.
        
        Example:
            # Switch directly to the chat window
            self.switch_window("chat")
            
            # Or, to let the WindowManager handle it (recommended):
            self.window_switch_requested.emit("chat")
        
        Args:
            window_type (str): The type of window to switch to
            
        Returns:
            bool: True if successful, False if window type is unknown
        """
        if window_type in self.WINDOW_CLASSES:
            # Create a new instance of the window class
            new_window = self.WINDOW_CLASSES[window_type]()
            
            # Show the new window
            new_window.show()
            
            # Hide the current window
            self.hide()
            
            return True
        else:
            logger.warning(f"Unknown window type: {window_type}")
            return False
    
    def showEvent(self, event):
        """Handle window show event - ensure proper fullscreen state"""
        # If in kiosk mode, ensure the window is in fullscreen
        if self.is_kiosk_mode:
            logger.info(f"{self.__class__.__name__}: Ensuring fullscreen in kiosk mode")
            # Call showFullScreen directly without delay
            self.showFullScreen()
            
            # Ensure all components are properly updated for kiosk mode
            self._update_kiosk_mode_in_components()
            
        super().showEvent(event)
    
    def closeEvent(self, event):
        """Handle window close event"""
        logger.info(f"Closing {self.__class__.__name__}")
        
        # Only emit the window_closed signal for genuine close events, not during flag changes
        # A genuine close is when the event is spontaneous (user initiated) or when it's 
        # non-spontaneous but not coming from a window flag change operation
        if event.spontaneous() and self.isVisible():
            self.window_closed.emit()
            
        super().closeEvent(event) 