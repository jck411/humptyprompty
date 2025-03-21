// qml/InputBar.qml
import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: inputBar
    width: parent.width
    height: 60
    color: darkMode ? "#24283b" : "#FFFFFF"
    property bool darkMode: false

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
        color: darkMode ? "#a9b1d6" : "#1C1E21"
        background: Rectangle { color: darkMode ? "#24283b" : "#FFFFFF"; radius: 4 }
        Keys.onReleased: {
            if (event.key === Qt.Key_Return && !event.shiftModifier) {
                sendButton.click()
                event.accepted = true
            }
        }
    }
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
            inputField.text = ""
        }
    }
    Button {
        id: stopButton
        text: "Stop"
        width: 60
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        onClicked: { backend.stopAll() }
    }
    Component.onCompleted: {
        if (darkMode) {
            inputField.placeholderTextColor = "#565f89"
        }
    }
    Connections {
        target: stt
        onComplete_utterance_received: {
            if (text && text.length > 0) {
                inputField.text = text;
            }
        }
    }
}
