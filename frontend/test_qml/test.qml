import QtQuick 2.15
import QtQuick.Controls 2.15

ApplicationWindow {
    width: 400
    height: 300
    visible: true
    title: "Test Window"
    color: "lightblue"

    Text {
        anchors.centerIn: parent
        text: "Hello, World!"
        font.pixelSize: 24
    }
} 