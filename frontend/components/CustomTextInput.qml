import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

TextArea {
    id: customTextInput
    
    // Properties
    property var themeColors
    property var sendCallback: null
    
    // Styling
    placeholderText: "Type your message..."
    placeholderTextColor: themeColors.text_secondary
    color: themeColors.text_primary
    wrapMode: TextEdit.Wrap
    
    // Background
    background: Rectangle {
        color: themeColors.surface
        radius: 10
        border.width: 1
        border.color: customTextInput.focus ? themeColors.primary : themeColors.text_secondary
    }
    
    // Handle key events
    Keys.onPressed: function(event) {
        // Enter without shift sends the message
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            if (!(event.modifiers & Qt.ShiftModifier)) {
                event.accepted = true;
                if (sendCallback && text.trim().length > 0) {
                    sendCallback(text.trim());
                    text = "";
                }
            }
        }
    }
}
