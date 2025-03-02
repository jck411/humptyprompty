"""
UI components for the frontend application.
"""
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QTextEdit
from PyQt6.QtCore import Qt
from frontend.ui.styles import get_message_bubble_stylesheet

class MessageBubble(QFrame):
    """
    A message bubble widget for displaying chat messages.
    """
    def __init__(self, text, is_user=True, colors=None):
        """
        Initialize a message bubble.
        
        Args:
            text: The message text.
            is_user: Boolean indicating if the message is from the user.
            colors: Dictionary of color values for styling.
        """
        super().__init__()
        self.setObjectName("messageBubble")
        self.setProperty("isUser", is_user)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.label)
        
        if colors:
            self.setStyleSheet(get_message_bubble_stylesheet(is_user, colors))

    def update_text(self, new_text):
        """
        Update the text of the message bubble.
        
        Args:
            new_text: The new message text.
        """
        self.label.setText(new_text)

class CustomTextEdit(QTextEdit):
    """
    A custom text edit widget that handles key events.
    """
    def __init__(self, parent=None):
        """
        Initialize a custom text edit.
        
        Args:
            parent: The parent widget.
        """
        super().__init__(parent)

    def keyPressEvent(self, event):
        """
        Handle key press events.
        
        Args:
            event: The key event.
        """
        if event.key() == Qt.Key.Key_Return and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            main_window = self.window()
            if hasattr(main_window, "send_message"):
                main_window.send_message()
        else:
            super().keyPressEvent(event)
