import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: settingsScreen
    anchors.fill: parent
    
    // Colors and theme properties
    property var colors
    property bool isDarkMode: false
    
    Rectangle {
        anchors.fill: parent
        color: colors.background
        
        Column {
            anchors.centerIn: parent
            spacing: 20
            
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Settings Screen"
                color: colors.text_primary
                font.pixelSize: 32
                font.bold: true
            }
            
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Placeholder - Application settings will appear here"
                color: colors.text_secondary
                font.pixelSize: 18
            }
            
            Button {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Go to Chat"
                onClicked: appWindow.navigateTo("chat")
            }
        }
    }
}
