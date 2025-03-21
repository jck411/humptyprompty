// MenuBar.qml
import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {  // using a Rectangle as container with a transparent background
    id: menuBar
    color: "transparent"
    width: parent.width
    height: 50

    Row {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 12

        // STT Toggle Switch
        Switch {
            id: sttSwitch
            text: "STT"
            checked: false
            onClicked: { backend.toggleSTT() }
            // Update label text when state changes
            onToggled: { text = "STT " + (checked ? "On" : "Off") }
        }
        // TTS Toggle Switch
        Switch {
            id: ttsSwitch
            text: "TTS"
            checked: false
            onClicked: { backend.toggleTTS() }
            onToggled: { text = "TTS " + (checked ? "On" : "Off") }
        }
        // Clear Chat Button
        Button {
            id: clearButton
            text: "Clear"
            onClicked: { backend.clearChat() }
        }
        // Stretch space to push theme button to far right
        Rectangle { width: 0; height: 0; Layout.fillWidth: true; color: "transparent" }
        // Theme Toggle Button (icon button)
        Button {
            id: themeButton
            text: mainWindow.darkMode ? "Light Mode" : "Dark Mode"
            onClicked: {
                mainWindow.toggleTheme()
                text = mainWindow.darkMode ? "Light Mode" : "Dark Mode"
            }
        }
    }

    // Keep STT switch in sync with backend STT state signal
    Connections {
        target: backend
        onSttEnabledChanged: {
            sttSwitch.checked = enabled;
            sttSwitch.text = "STT " + (enabled ? "On" : "Off")
        }
    }
    // Keep TTS switch in sync with backend TTS state signal
    Connections {
        target: backend
        onTtsEnabledChanged: {
            ttsSwitch.checked = enabled;
            ttsSwitch.text = "TTS " + (enabled ? "On" : "Off")
        }
    }
}
