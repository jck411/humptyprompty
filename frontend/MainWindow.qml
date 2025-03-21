// MainWindow.qml
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

ApplicationWindow {
    id: mainWindow
    width: 800
    height: 600
    visible: true
    title: "Modern Chat Interface"
    color: darkMode ? "#1a1b26" : "#E8EEF5"   // Window background color (dark vs light)

    // Theme properties (light/dark)
    property bool darkMode: true
    property color backgroundColor: darkMode ? "#1a1b26" : "#E8EEF5"
    property color userBubbleColor: darkMode ? "#3b4261" : "#D0D7E1"
    property color assistantBubbleColor: darkMode ? "#24283b" : "#F7F9FB"
    property color textPrimaryColor: darkMode ? "#a9b1d6" : "#1C1E21"

    // Layout: a vertical stack of MenuBar at top, ChatArea center, InputBar at bottom
    MenuBar {
        id: menuBar
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        // Pass theme info to menu bar if needed (not used in this simple case)
    }
    ChatArea {
        id: chatArea
        anchors.top: menuBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: inputBar.top
        // Pass theme colors down to ChatArea for message bubbles
        userColor: mainWindow.userBubbleColor
        assistantColor: mainWindow.assistantBubbleColor
        textColor: mainWindow.textPrimaryColor
    }
    InputBar {
        id: inputBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        // Bind darkMode to adjust input field styling (placeholder color, etc., if desired)
        darkMode: mainWindow.darkMode
    }

    // Respond to backend signals for connection status (update window title)
    Connections {
        target: wsClient
        onConnection_status: {
            mainWindow.title = "Modern Chat Interface - " + (connected ? "Connected" : "Disconnected")
        }
    }

    // Optional: toggle dark/light theme when a theme button in MenuBar is clicked
    function toggleTheme() {
        mainWindow.darkMode = !mainWindow.darkMode;
        // Update chat bubbles' colors on theme change
        chatArea.updateBubbleStyles()
    }
}
