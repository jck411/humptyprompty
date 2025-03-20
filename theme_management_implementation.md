# Consolidate Theme Management Implementation

## Overview
Theme management is currently duplicated across MainWindow and individual screens. This implementation plan outlines how to create a centralized theme manager that all components can access.

## Current Issues
- Duplication of theme switching logic in MainWindow and screens
- Inconsistent theme application across components
- Redundant color definitions and style generation
- No centralized way to add new themes or modify existing ones
- Theme state is managed independently in different components

## Implementation Steps

### 1. Create a Theme Manager Class

Create a new file `frontend/theme_manager.py` that will:
- Define a singleton ThemeManager class
- Store all theme definitions (colors, fonts, styles)
- Provide methods to switch between themes
- Emit signals when theme changes
- Support dynamic theme loading

### 2. Centralize Theme Definitions

Move all theme definitions to a central location:
- Move color definitions from style.py to theme_manager.py
- Create structured theme objects with all necessary properties
- Support light and dark themes by default
- Allow for custom theme creation

### 3. Implement Theme Application

In the ThemeManager class:
- Provide methods to apply themes to different component types
- Generate appropriate stylesheets for each component type
- Support component-specific theme overrides
- Implement theme persistence between sessions

### 4. Create Theme Access API

Implement a simple API for accessing and modifying themes:
```python
from frontend.theme_manager import theme_manager

# Get current theme colors
primary_color = theme_manager.get_color('primary')

# Apply theme to a component
theme_manager.apply_theme(my_widget)

# Switch themes
theme_manager.set_theme('dark')
```

### 5. Migrate Existing Theme Code

Update all files that currently handle themes directly:
- Replace direct theme handling in MainWindow with ThemeManager calls
- Update BaseScreen to use ThemeManager for theme updates
- Modify all screen implementations to use the centralized theme system
- Update UI components to use ThemeManager for styling

### 6. Add Theme Customization Support

Implement support for theme customization:
- Allow runtime modification of theme properties
- Support saving custom themes
- Provide a theme editor interface in the settings screen
- Implement theme import/export functionality

## Benefits
- Consistent theme application across all components
- Simplified theme switching and management
- Reduced code duplication in theme handling
- Easier to add new themes or modify existing ones
- Better user experience with consistent visual styling
