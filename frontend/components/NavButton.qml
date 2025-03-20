import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: navButton
    
    // Properties
    property bool isActive: false
    property string icon: ""
    property var themeColors
    
    // Styling
    implicitHeight: 40
    
    // Background
    background: Rectangle {
        color: isActive ? themeColors.primary : 
               (navButton.hovered ? Qt.darker(themeColors.surface, 1.1) : themeColors.surface)
        radius: 8
        
        // Left highlight bar for active item
        Rectangle {
            visible: isActive
            width: 4
            height: parent.height
            color: themeColors.secondary
            anchors.left: parent.left
        }
    }
    
    // Content layout
    contentItem: RowLayout {
        spacing: 10
        
        // Icon
        Image {
            source: icon
            sourceSize.width: 20
            sourceSize.height: 20
            Layout.leftMargin: 10
            visible: icon !== ""
            opacity: isActive ? 1.0 : 0.7
        }
        
        // Text
        Text {
            text: navButton.text
            color: isActive ? themeColors.text_primary : themeColors.text_secondary
            font.pixelSize: 14
            font.bold: isActive
            Layout.fillWidth: true
        }
    }
}
