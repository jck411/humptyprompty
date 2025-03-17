#!/usr/bin/env python3

class Themeable:
    """
    A mixin class that provides standard theme update functionality for UI components.
    
    This mixin standardizes how components handle theme updates by providing
    an update_theme method that calls the component's update_icons and/or
    update_colors methods if they exist.
    
    Components using this mixin should implement:
    - update_icons(is_dark_mode) - If they need to update icons based on theme
    - update_colors(colors) - If they need to update colors based on theme
    """
    
    def update_theme(self, is_dark_mode, colors):
        """
        Update the theme for this component.
        
        Args:
            is_dark_mode (bool): True for dark mode, False for light mode
            colors (dict): Dictionary of colors for the current theme
        """
        if hasattr(self, 'update_icons'):
            self.update_icons(is_dark_mode)
        if hasattr(self, 'update_colors'):
            self.update_colors(colors) 