// qml/MessageBubble.qml
import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: bubbleItem
    property string messageText: ""
    property bool isUser: false
    property color bubbleColor: "#cccccc"
    property color textColor: "#000000"
    width: parent ? parent.width : 0

    Rectangle {
        id: bubbleBackground
        color: bubbleItem.bubbleColor
        radius: 8
        anchors.right: bubbleItem.isUser ? parent.right : undefined
        anchors.left: !bubbleItem.isUser ? parent.left : undefined
        anchors.top: parent.top

        Text {
            id: bubbleText
            text: bubbleItem.messageText
            color: bubbleItem.textColor
            wrapMode: Text.Wrap
            font.pixelSize: 14
            width: parent.parent ? parent.parent.width * 0.7 : 400
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.margins: 8
        }

        implicitWidth: bubbleText.paintedWidth + 16
        implicitHeight: bubbleText.paintedHeight + 16
    }
    implicitHeight: bubbleBackground.height
}
