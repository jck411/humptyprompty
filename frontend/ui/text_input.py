#!/usr/bin/env python3
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtCore import Qt

class CustomTextEdit(QTextEdit):
    """
    Custom text edit component for the chat input area.
    Handles special key events like Enter to send messages.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Type your message...")
        self.setMaximumHeight(60)
        self.setMinimumHeight(50)

    def keyPressEvent(self, event):
        """Handle key press events"""
        # Send message on Enter (without Shift)
        if event.key() == Qt.Key.Key_Return and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            main_window = self.window()
            if hasattr(main_window, "send_message"):
                main_window.send_message()
        else:
            super().keyPressEvent(event) 