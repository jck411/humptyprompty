// InputBar.qml
import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: inputBar
    width: parent.width
    height: 60
    color: inputBar.darkMode ? "#24283b" : "#FFFFFF"   // background of input bar (optional)
    property bool darkMode: false

    // Text input field
    TextArea {
        id: inputField
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: sendButton.left
        anchors.rightMargin: 5
        padding: 8
        placeholderText: "Type your message..."
        wrapMode: TextArea.WrapAtWordBoundaryOrAnywhere
        font.pixelSize: 14
        color: inputBar.darkMode ? "#a9b1d6" : "#1C1E21"
        background: Rectangle { color: inputBar.darkMode ? "#24283b" : "#FFFFFF"; radius: 4 }
        // Handle Enter key: send on Enter, newline on Shift+Enter
        Keys.onReleased: {
            if (event.key === Qt.Key_Return && !event.shiftModifier) {
                sendButton.click()
                event.accepted = true
            }
        }
    }
    // Send button
    Button {
        id: sendButton
        text: "Send"
        width: 60
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: stopButton.left
        anchors.rightMargin: 5
        onClicked: {
            backend.sendMessage(inputField.text)
            inputField.text = ""   // clear input after sending
        }
    }
    // Stop (TTS/Generation) button
    Button {
        id: stopButton
        text: "Stop"
        width: 60
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        onClicked: { backend.stopAll() }
    }

    // Update input field placeholder color based on theme (optional styling)
    Component.onCompleted: {
        if (inputBar.darkMode) {
            inputField.placeholderTextColor = "#565f89";  // using a secondary text color for placeholder in dark mode
        }
    }

    // If STT final transcription is received, update the input text (so user can edit or send it)
    Connections {
        target: stt
        onComplete_utterance_received: {
            if (text && text.length > 0) {
                inputField.text = text;
            }
        }
    }
}
