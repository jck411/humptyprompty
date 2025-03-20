#!/usr/bin/env python3
"""
Centralized theme management system for the application.
This module provides a unified way to manage themes across all components.
"""
import json
import logging
import os
from enum import Enum
from typing import Dict, Any, Optional, List, Callable
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget, QApplication

# Configure logger
logger = logging.getLogger(__name__)

class ThemeType(Enum):
    """Enum defining theme types"""
    LIGHT = "light"
    DARK = "dark"
    CUSTOM = "custom"

class ThemeManager(QObject):
    """
    Centralized theme manager that provides theme management for all components.
    
    Features:
    - Centralized theme definitions
    - Theme switching with signals
    - Component-specific theme application
    - Theme persistence between sessions
    - Support for custom themes
    """
    # Signal emitted when theme changes
    theme_changed = pyqtSignal(dict)  # Emits the new theme colors
    
    def __init__(self):
        """Initialize the theme manager"""
        super().__init__()
        
        # Define default themes
        self._themes: Dict[str, Dict[str, Any]] = {
            "light": {
                "type": ThemeType.LIGHT.value,
                "name": "Light",
                "colors": {
                    "background_primary": "#FFFFFF",
                    "background_secondary": "#F5F5F5",
                    "text_primary": "#333333",
                    "text_secondary": "#666666",
                    "accent_primary": "#007BFF",
                    "accent_secondary": "#6C757D",
                    "success": "#28A745",
                    "warning": "#FFC107",
                    "error": "#DC3545",
                    "info": "#17A2B8",
                    "border": "#DDDDDD",
                    "shadow": "rgba(0, 0, 0, 0.1)",
                    "overlay": "rgba(0, 0, 0, 0.5)",
                    "highlight": "#E6F7FF"
                },
                "fonts": {
                    "primary": "Arial, sans-serif",
                    "secondary": "Helvetica, sans-serif",
                    "monospace": "Courier New, monospace"
                },
                "sizes": {
                    "font_small": 12,
                    "font_medium": 14,
                    "font_large": 18,
                    "font_xlarge": 24,
                    "padding_small": 5,
                    "padding_medium": 10,
                    "padding_large": 15,
                    "border_radius": 5
                }
            },
            "dark": {
                "type": ThemeType.DARK.value,
                "name": "Dark",
                "colors": {
                    "background_primary": "#121212",
                    "background_secondary": "#1E1E1E",
                    "text_primary": "#FFFFFF",
                    "text_secondary": "#AAAAAA",
                    "accent_primary": "#0D6EFD",
                    "accent_secondary": "#6C757D",
                    "success": "#198754",
                    "warning": "#FFC107",
                    "error": "#DC3545",
                    "info": "#0DCAF0",
                    "border": "#333333",
                    "shadow": "rgba(0, 0, 0, 0.3)",
                    "overlay": "rgba(0, 0, 0, 0.7)",
                    "highlight": "#1C3A57"
                },
                "fonts": {
                    "primary": "Arial, sans-serif",
                    "secondary": "Helvetica, sans-serif",
                    "monospace": "Courier New, monospace"
                },
                "sizes": {
                    "font_small": 12,
                    "font_medium": 14,
                    "font_large": 18,
                    "font_xlarge": 24,
                    "padding_small": 5,
                    "padding_medium": 10,
                    "padding_large": 15,
                    "border_radius": 5
                }
            }
        }
        
        # Current theme
        self._current_theme_name = "dark"
        self._current_theme = self._themes["dark"]
        
        # Component-specific theme overrides
        self._component_overrides: Dict[str, Dict[str, Any]] = {}
        
        # Theme change callbacks
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        # Load saved theme if available
        self._load_saved_theme()
    
    def _load_saved_theme(self) -> None:
        """Load the saved theme from settings"""
        try:
            # In a real implementation, this would load from a settings file
            # For now, we'll just use the default dark theme
            pass
        except Exception as e:
            logger.error(f"Error loading saved theme: {e}")
    
    def _save_current_theme(self) -> None:
        """Save the current theme to settings"""
        try:
            # In a real implementation, this would save to a settings file
            pass
        except Exception as e:
            logger.error(f"Error saving theme: {e}")
    
    def get_theme_names(self) -> List[str]:
        """Get a list of available theme names"""
        return list(self._themes.keys())
    
    def get_current_theme_name(self) -> str:
        """Get the name of the current theme"""
        return self._current_theme_name
    
    def get_current_theme(self) -> Dict[str, Any]:
        """Get the current theme definition"""
        return self._current_theme.copy()
    
    def get_theme(self, theme_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a theme definition by name
        
        Args:
            theme_name: Name of the theme
            
        Returns:
            Theme definition or None if not found
        """
        return self._themes.get(theme_name, {}).copy()
    
    def set_theme(self, theme_name: str) -> bool:
        """
        Set the current theme by name
        
        Args:
            theme_name: Name of the theme
            
        Returns:
            True if theme was set successfully, False otherwise
        """
        if theme_name not in self._themes:
            logger.error(f"Theme not found: {theme_name}")
            return False
            
        self._current_theme_name = theme_name
        self._current_theme = self._themes[theme_name]
        
        # Emit theme changed signal
        self.theme_changed.emit(self._current_theme["colors"])
        
        # Call registered callbacks
        for callback in self._callbacks:
            try:
                callback(self._current_theme)
            except Exception as e:
                logger.error(f"Error in theme change callback: {e}")
        
        # Save the theme preference
        self._save_current_theme()
        
        logger.info(f"Theme set to: {theme_name}")
        return True
    
    def toggle_theme(self) -> str:
        """
        Toggle between light and dark themes
        
        Returns:
            Name of the new theme
        """
        if self._current_theme_name == "light":
            self.set_theme("dark")
            return "dark"
        else:
            self.set_theme("light")
            return "light"
    
    def is_dark_theme(self) -> bool:
        """Check if the current theme is dark"""
        return self._current_theme.get("type") == ThemeType.DARK.value
    
    def get_color(self, color_name: str, default: str = "#000000") -> str:
        """
        Get a color from the current theme
        
        Args:
            color_name: Name of the color
            default: Default color if not found
            
        Returns:
            Color value
        """
        return self._current_theme.get("colors", {}).get(color_name, default)
    
    def get_font(self, font_name: str, default: str = "Arial, sans-serif") -> str:
        """
        Get a font from the current theme
        
        Args:
            font_name: Name of the font
            default: Default font if not found
            
        Returns:
            Font value
        """
        return self._current_theme.get("fonts", {}).get(font_name, default)
    
    def get_size(self, size_name: str, default: int = 0) -> int:
        """
        Get a size from the current theme
        
        Args:
            size_name: Name of the size
            default: Default size if not found
            
        Returns:
            Size value
        """
        return self._current_theme.get("sizes", {}).get(size_name, default)
    
    def register_theme_change_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Register a callback to be called when the theme changes
        
        Args:
            callback: Function to call with the new theme
        """
        if callback not in self._callbacks:
            self._callbacks.append(callback)
    
    def unregister_theme_change_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Unregister a theme change callback
        
        Args:
            callback: Function to unregister
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def add_component_override(self, component_id: str, override: Dict[str, Any]) -> None:
        """
        Add a component-specific theme override
        
        Args:
            component_id: Unique identifier for the component
            override: Theme override values
        """
        self._component_overrides[component_id] = override
    
    def get_component_theme(self, component_id: str) -> Dict[str, Any]:
        """
        Get a theme with component-specific overrides applied
        
        Args:
            component_id: Unique identifier for the component
            
        Returns:
            Theme with overrides applied
        """
        theme = self._current_theme.copy()
        
        # Apply component-specific overrides if they exist
        if component_id in self._component_overrides:
            override = self._component_overrides[component_id]
            
            # Apply overrides to each section
            for section in ["colors", "fonts", "sizes"]:
                if section in override and section in theme:
                    theme[section] = {**theme[section], **override[section]}
        
        return theme
    
    def create_custom_theme(self, name: str, base_theme: str, overrides: Dict[str, Any]) -> bool:
        """
        Create a custom theme based on an existing theme
        
        Args:
            name: Name for the new theme
            base_theme: Name of the theme to base on
            overrides: Values to override in the base theme
            
        Returns:
            True if theme was created successfully, False otherwise
        """
        if name in self._themes:
            logger.warning(f"Theme already exists: {name}")
            return False
            
        if base_theme not in self._themes:
            logger.error(f"Base theme not found: {base_theme}")
            return False
            
        # Create a copy of the base theme
        new_theme = self._themes[base_theme].copy()
        
        # Set type to custom
        new_theme["type"] = ThemeType.CUSTOM.value
        new_theme["name"] = name
        
        # Apply overrides
        for section in ["colors", "fonts", "sizes"]:
            if section in overrides and section in new_theme:
                new_theme[section] = {**new_theme[section], **overrides[section]}
        
        # Add the new theme
        self._themes[name] = new_theme
        
        logger.info(f"Created custom theme: {name}")
        return True
    
    def delete_custom_theme(self, name: str) -> bool:
        """
        Delete a custom theme
        
        Args:
            name: Name of the theme to delete
            
        Returns:
            True if theme was deleted successfully, False otherwise
        """
        if name not in self._themes:
            logger.warning(f"Theme not found: {name}")
            return False
            
        # Only allow deleting custom themes
        if self._themes[name].get("type") != ThemeType.CUSTOM.value:
            logger.error(f"Cannot delete built-in theme: {name}")
            return False
            
        # If the current theme is being deleted, switch to dark theme
        if self._current_theme_name == name:
            self.set_theme("dark")
            
        # Delete the theme
        del self._themes[name]
        
        logger.info(f"Deleted custom theme: {name}")
        return True
    
    def export_theme(self, name: str, file_path: str) -> bool:
        """
        Export a theme to a JSON file
        
        Args:
            name: Name of the theme to export
            file_path: Path to save the theme to
            
        Returns:
            True if theme was exported successfully, False otherwise
        """
        if name not in self._themes:
            logger.error(f"Theme not found: {name}")
            return False
            
        try:
            with open(file_path, 'w') as f:
                json.dump(self._themes[name], f, indent=2)
                
            logger.info(f"Exported theme {name} to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error exporting theme: {e}")
            return False
    
    def import_theme(self, file_path: str) -> Optional[str]:
        """
        Import a theme from a JSON file
        
        Args:
            file_path: Path to the theme file
            
        Returns:
            Name of the imported theme or None if import failed
        """
        try:
            with open(file_path, 'r') as f:
                theme = json.load(f)
                
            # Validate theme structure
            if not all(key in theme for key in ["name", "colors", "fonts", "sizes"]):
                logger.error("Invalid theme file: missing required sections")
                return None
                
            # Set type to custom
            theme["type"] = ThemeType.CUSTOM.value
            
            # Add the theme
            name = theme.get("name", os.path.basename(file_path).split('.')[0])
            self._themes[name] = theme
            
            logger.info(f"Imported theme: {name}")
            return name
        except Exception as e:
            logger.error(f"Error importing theme: {e}")
            return None
    
    def apply_theme_to_widget(self, widget: QWidget, component_id: Optional[str] = None) -> None:
        """
        Apply the current theme to a widget
        
        Args:
            widget: Widget to apply theme to
            component_id: Optional component ID for overrides
        """
        # Get theme with potential component overrides
        theme = self.get_component_theme(component_id) if component_id else self._current_theme
        colors = theme.get("colors", {})
        
        # Create a stylesheet based on the widget type
        stylesheet = ""
        
        # Apply general styling
        stylesheet += f"""
            * {{
                color: {colors.get('text_primary', '#000000')};
                background-color: {colors.get('background_primary', '#FFFFFF')};
                font-family: {theme.get('fonts', {}).get('primary', 'Arial, sans-serif')};
            }}
        """
        
        # Apply specific styling based on widget type
        widget_type = widget.__class__.__name__
        
        if widget_type == "QMainWindow":
            stylesheet += f"""
                QMainWindow {{
                    background-color: {colors.get('background_primary', '#FFFFFF')};
                }}
            """
        elif widget_type == "QPushButton":
            stylesheet += f"""
                QPushButton {{
                    background-color: {colors.get('accent_primary', '#007BFF')};
                    color: white;
                    border: none;
                    border-radius: {theme.get('sizes', {}).get('border_radius', 5)}px;
                    padding: {theme.get('sizes', {}).get('padding_medium', 10)}px;
                }}
                QPushButton:hover {{
                    background-color: {self._lighten_or_darken_color(colors.get('accent_primary', '#007BFF'), 20)};
                }}
                QPushButton:pressed {{
                    background-color: {self._lighten_or_darken_color(colors.get('accent_primary', '#007BFF'), -20)};
                }}
            """
        elif widget_type == "QLabel":
            stylesheet += f"""
                QLabel {{
                    color: {colors.get('text_primary', '#000000')};
                    background-color: transparent;
                }}
            """
        elif widget_type == "QLineEdit" or widget_type == "QTextEdit":
            stylesheet += f"""
                {widget_type} {{
                    background-color: {colors.get('background_secondary', '#F5F5F5')};
                    color: {colors.get('text_primary', '#000000')};
                    border: 1px solid {colors.get('border', '#DDDDDD')};
                    border-radius: {theme.get('sizes', {}).get('border_radius', 5)}px;
                    padding: {theme.get('sizes', {}).get('padding_small', 5)}px;
                }}
                {widget_type}:focus {{
                    border: 1px solid {colors.get('accent_primary', '#007BFF')};
                }}
            """
        
        # Apply the stylesheet
        widget.setStyleSheet(stylesheet)
        
        # Apply theme to child widgets recursively
        for child in widget.findChildren(QWidget):
            self.apply_theme_to_widget(child, component_id)
    
    def generate_stylesheet(self, component_id: Optional[str] = None) -> str:
        """
        Generate a stylesheet for the current theme
        
        Args:
            component_id: Optional component ID for overrides
            
        Returns:
            Stylesheet string
        """
        # Get theme with potential component overrides
        theme = self.get_component_theme(component_id) if component_id else self._current_theme
        colors = theme.get("colors", {})
        
        # Create a stylesheet
        stylesheet = f"""
            /* Main application styling */
            QWidget {{
                background-color: {colors.get('background_primary', '#FFFFFF')};
                color: {colors.get('text_primary', '#000000')};
                font-family: {theme.get('fonts', {}).get('primary', 'Arial, sans-serif')};
            }}
            
            /* Button styling */
            QPushButton {{
                background-color: {colors.get('accent_primary', '#007BFF')};
                color: white;
                border: none;
                border-radius: {theme.get('sizes', {}).get('border_radius', 5)}px;
                padding: {theme.get('sizes', {}).get('padding_medium', 10)}px;
            }}
            QPushButton:hover {{
                background-color: {self._lighten_or_darken_color(colors.get('accent_primary', '#007BFF'), 20)};
            }}
            QPushButton:pressed {{
                background-color: {self._lighten_or_darken_color(colors.get('accent_primary', '#007BFF'), -20)};
            }}
            
            /* Input styling */
            QLineEdit, QTextEdit {{
                background-color: {colors.get('background_secondary', '#F5F5F5')};
                color: {colors.get('text_primary', '#000000')};
                border: 1px solid {colors.get('border', '#DDDDDD')};
                border-radius: {theme.get('sizes', {}).get('border_radius', 5)}px;
                padding: {theme.get('sizes', {}).get('padding_small', 5)}px;
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border: 1px solid {colors.get('accent_primary', '#007BFF')};
            }}
            
            /* Label styling */
            QLabel {{
                color: {colors.get('text_primary', '#000000')};
                background-color: transparent;
            }}
            
            /* Toolbar styling */
            QToolBar {{
                background-color: {colors.get('background_secondary', '#F5F5F5')};
                border: none;
                spacing: 5px;
            }}
            
            /* Menu styling */
            QMenuBar {{
                background-color: {colors.get('background_secondary', '#F5F5F5')};
                color: {colors.get('text_primary', '#000000')};
            }}
            QMenu {{
                background-color: {colors.get('background_primary', '#FFFFFF')};
                color: {colors.get('text_primary', '#000000')};
                border: 1px solid {colors.get('border', '#DDDDDD')};
            }}
            QMenu::item:selected {{
                background-color: {colors.get('highlight', '#E6F7FF')};
            }}
            
            /* Scrollbar styling */
            QScrollBar:vertical {{
                background-color: {colors.get('background_secondary', '#F5F5F5')};
                width: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {colors.get('accent_secondary', '#6C757D')};
                min-height: 20px;
                border-radius: 6px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background-color: {colors.get('background_secondary', '#F5F5F5')};
                height: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {colors.get('accent_secondary', '#6C757D')};
                min-width: 20px;
                border-radius: 6px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
        """
        
        return stylesheet
    
    def _lighten_or_darken_color(self, color: str, amount: int) -> str:
        """
        Lighten or darken a color by a specified amount
        
        Args:
            color: Color in hex format (#RRGGBB)
            amount: Amount to lighten (positive) or darken (negative)
            
        Returns:
            Modified color in hex format
        """
        # Remove # if present
        color = color.lstrip('#')
        
        # Convert to RGB
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        
        # Lighten or darken
        r = max(0, min(255, r + amount))
        g = max(0, min(255, g + amount))
        b = max(0, min(255, b + amount))
        
        # Convert back to hex
        return f"#{r:02x}{g:02x}{b:02x}"

# Create a singleton instance
theme_manager = ThemeManager()

# Example usage:
"""
# Get the theme manager instance
from frontend.theme_manager import theme_manager

# Set the theme
theme_manager.set_theme("dark")

# Get a color from the theme
primary_color = theme_manager.get_color("accent_primary")

# Apply theme to a widget
theme_manager.apply_theme_to_widget(my_widget)

# Generate a stylesheet
stylesheet = theme_manager.generate_stylesheet()
my_widget.setStyleSheet(stylesheet)

# Toggle between light and dark themes
theme_manager.toggle_theme()

# Create a custom theme
theme_manager.create_custom_theme(
    "my_theme",
    "dark",
    {
        "colors": {
            "accent_primary": "#FF5733",
            "accent_secondary": "#C70039"
        }
    }
)
"""
