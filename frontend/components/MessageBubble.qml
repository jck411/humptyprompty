import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: messageBubble
    
    // Required properties to be set from parent
    property string messageText: ""
    property bool isUser: false
    property var themeColors
    
    // Auto-width based on content with limits
    implicitWidth: Math.min(messageLayout.implicitWidth + 20, parent.width * 0.8)
    implicitHeight: messageLayout.implicitHeight + 20
    radius: 15
    
    // Color based on sender (user or assistant) and theme
    color: isUser ? themeColors.user_bubble : themeColors.assistant_bubble
    
    ColumnLayout {
        id: messageLayout
        anchors {
            fill: parent
            margins: 10
        }
        spacing: 5
        
        Label {
            id: messageTextLabel
            text: messageText
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            Layout.fillHeight: true
            
            // Text color based on bubble color and theme to ensure readability
            color: isUser ? "#ffffff" : themeColors.text_primary
            font.pixelSize: 14
        }
    }
}
