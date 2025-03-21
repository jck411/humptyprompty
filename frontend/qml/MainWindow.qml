// qml/MainWindow.qml
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

ApplicationWindow {
    id: mainWindow
    width: 800
    height: 600
    visible: true
    title: "Modern Chat Interface"
    color: darkMode ? "#1a1b26" : "#E8EEF5"

    property bool darkMode: true
    property color backgroundColor: darkMode ? "#1a1b26" : "#E8EEF5"
    property color userBubbleColor: darkMode ? "#3b4261" : "#D0D7E1"
    property color assistantBubbleColor: darkMode ? "#24283b" : "#F7F9FB"
    property color textPrimaryColor: darkMode ? "#a9b1d6" : "#1C1E21"

    Component.onCompleted: {
        console.log("Main window initialized")
        mainWindow.raise()
        mainWindow.requestActivate()
    }

    MenuBar {
        id: menuBar
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
    }
    ChatArea {
        id: chatArea
        anchors.top: menuBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: inputBar.top
        userColor: mainWindow.userBubbleColor
        assistantColor: mainWindow.assistantBubbleColor
        textColor: mainWindow.textPrimaryColor
    }
    InputBar {
        id: inputBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        darkMode: mainWindow.darkMode
    }

    Connections {
        target: wsClient
        onConnection_status: {
            mainWindow.title = "Modern Chat Interface - " + (connected ? "Connected" : "Disconnected")
        }
    }

    function toggleTheme() {
        mainWindow.darkMode = !mainWindow.darkMode;
        chatArea.updateBubbleStyles()
    }
}
