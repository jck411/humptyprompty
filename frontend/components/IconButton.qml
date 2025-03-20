import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: iconButton
    
    // Properties
    property string iconSource: ""
    property int iconSize: 24
    property bool toggled: false
    property bool toggleButton: false
    property var themeColors
    
    // Custom styling
    implicitWidth: 45
    implicitHeight: 45
    
    // Background and highlighting
    background: Rectangle {
        id: buttonBackground
        color: iconButton.down ? Qt.darker(themeColors.surface, 1.2) : 
               (iconButton.hovered ? Qt.darker(themeColors.surface, 1.1) : themeColors.surface)
        radius: width / 2
        border.width: toggled ? 2 : 0
        border.color: toggled ? themeColors.primary : "transparent"
        
        // Ripple effect
        Rectangle {
            id: ripple
            anchors.centerIn: parent
            width: 0
            height: 0
            radius: width / 2
            color: Qt.rgba(0.5, 0.5, 0.5, 0.2)
            opacity: 0
            
            // Animation for ripple effect
            ParallelAnimation {
                id: rippleAnimation
                
                NumberAnimation {
                    target: ripple
                    properties: "width, height"
                    from: 0
                    to: buttonBackground.width * 2
                    duration: 300
                    easing.type: Easing.OutQuad
                }
                
                NumberAnimation {
                    target: ripple
                    property: "opacity"
                    from: 0.5
                    to: 0
                    duration: 300
                    easing.type: Easing.OutQuad
                }
            }
        }
    }
    
    // Icon display
    contentItem: Item {
        Image {
            anchors.centerIn: parent
            source: iconSource
            sourceSize {
                width: iconSize
                height: iconSize
            }
            
            // Apply opacity based on enabled state
            opacity: iconButton.enabled ? 1.0 : 0.5
        }
    }
    
    // Handle toggle state if this is a toggle button
    onClicked: {
        if (toggleButton) {
            toggled = !toggled;
        }
        rippleAnimation.start();
    }
}
