import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "components"

ApplicationWindow {
    id: appWindow
    visible: true
    width: 800
    height: 600
    title: "Smart Display"
    
    // Property for tracking dark mode state
    property bool isDarkMode: true
    
    // Reference to ChatModel exposed from Python
    // The chatModel is set as a context property in client.py
    
    // Color scheme based on theme
    property var colors: {
        "background": isDarkMode ? "#121212" : "#f5f5f5",
        "surface": isDarkMode ? "#1e1e1e" : "#ffffff",
        "primary": isDarkMode ? "#bb86fc" : "#6200ee",
        "secondary": isDarkMode ? "#03dac6" : "#03dac6",
        "text_primary": isDarkMode ? "#ffffff" : "#000000",
        "text_secondary": isDarkMode ? "#b0b0b0" : "#666666",
        "user_bubble": isDarkMode ? "#0b93f6" : "#0084ff",
        "assistant_bubble": isDarkMode ? "#2a2a2a" : "#e5e5ea"
    }
    
    // Function to toggle between light and dark modes
    function toggleTheme() {
        isDarkMode = !isDarkMode;
    }
    
    // Background color
    color: colors.background
    
    // Main layout with sidebar and content area
    RowLayout {
        anchors.fill: parent
        spacing: 0
        
        // Navigation sidebar
        Rectangle {
            id: sidebar
            Layout.preferredWidth: 200
            Layout.fillHeight: true
            color: colors.surface
            
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 10
                
                // App title
                Text {
                    text: "Smart Display"
                    font.pixelSize: 20
                    font.bold: true
                    color: colors.text_primary
                    Layout.alignment: Qt.AlignHCenter
                    Layout.bottomMargin: 20
                }
                
                // Navigation buttons
                Button {
                    text: "Chat"
                    highlighted: stackView.currentItem.objectName === "chatScreenLoader"
                    onClicked: navigateTo("chat")
                    Layout.fillWidth: true
                }
                
                Button {
                    text: "Clock"
                    highlighted: stackView.currentItem.objectName === "clockScreenLoader"
                    onClicked: navigateTo("clock")
                    Layout.fillWidth: true
                }
                
                Button {
                    text: "Weather"
                    highlighted: stackView.currentItem.objectName === "weatherScreenLoader"
                    onClicked: navigateTo("weather")
                    Layout.fillWidth: true
                }
                
                Button {
                    text: "Calendar"
                    highlighted: stackView.currentItem.objectName === "calendarScreenLoader"
                    onClicked: navigateTo("calendar")
                    Layout.fillWidth: true
                }
                
                Button {
                    text: "Photos"
                    highlighted: stackView.currentItem.objectName === "photosScreenLoader"
                    onClicked: navigateTo("photos")
                    Layout.fillWidth: true
                }
                
                Item { Layout.fillHeight: true } // Spacer
                
                // Theme toggle button
                Button {
                    text: isDarkMode ? "Light Mode" : "Dark Mode"
                    onClicked: toggleTheme()
                    Layout.fillWidth: true
                }
            }
        }
        
        // Content area with StackView
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: colors.background
            
            // StackView for managing different screens
            StackView {
                id: stackView
                anchors.fill: parent
                initialItem: chatScreen
                
                // Prevent destroying items when they are removed from the stack
                // This helps maintain the WebSocket connection and chat history
                popEnter: Transition {
                    PropertyAnimation {
                        property: "opacity"
                        from: 0
                        to: 1
                        duration: 200
                    }
                }
                popExit: Transition {
                    PropertyAnimation {
                        property: "opacity"
                        from: 1
                        to: 0
                        duration: 200
                    }
                }
                pushEnter: Transition {
                    PropertyAnimation {
                        property: "opacity"
                        from: 0
                        to: 1
                        duration: 200
                    }
                }
                pushExit: Transition {
                    PropertyAnimation {
                        property: "opacity"
                        from: 1
                        to: 0
                        duration: 200
                    }
                }
                replaceEnter: Transition {
                    PropertyAnimation {
                        property: "opacity"
                        from: 0
                        to: 1
                        duration: 200
                    }
                }
                replaceExit: Transition {
                    PropertyAnimation {
                        property: "opacity"
                        from: 1
                        to: 0
                        duration: 200
                    }
                }
                
                // Set the initialItem to chatScreen
                // We don't need a custom property for keeping items
            }
        }
    }
    
    // Components for each screen (loaded as needed)
    Component {
        id: chatScreen
        Loader {
            objectName: "chatScreenLoader"
            source: "screens/ChatScreen.qml"
            asynchronous: true
            onLoaded: {
                console.log("ChatScreen loaded, setting properties");
                console.log("chatModel exists in main.qml: " + (typeof chatModel !== 'undefined' && chatModel !== null));
                
                item.chatModel = chatModel;
                // Create proper bindings for colors and isDarkMode so they update when the app theme changes
                item.colors = Qt.binding(function() { return colors; });
                item.isDarkMode = Qt.binding(function() { return isDarkMode; });
                
                // Connect signals from ChatModel to ChatScreen functions
                if (chatModel) {
                    console.log("Connecting ChatModel signals to ChatScreen functions");
                    chatModel.messageReceived.connect(item.receiveMessage);
                    chatModel.assistantMessageInProgress.connect(item.addTokenToMessage);
                    chatModel.sttStateChanged.connect(item.updateSttState);
                    chatModel.ttsStateChanged.connect(item.updateTtsState);
                } else {
                    console.log("chatModel is not available in main.qml onLoaded");
                }
            }
        }
    }
    
    Component {
        id: clockScreen
        Loader {
            objectName: "clockScreenLoader"
            source: "screens/ClockScreen.qml"
            asynchronous: true
            onLoaded: {
                // Create proper bindings for colors and isDarkMode so they update when the app theme changes
                item.colors = Qt.binding(function() { return colors; });
                item.isDarkMode = Qt.binding(function() { return isDarkMode; });
            }
        }
    }
    
    Component {
        id: weatherScreen
        Loader {
            objectName: "weatherScreenLoader"
            source: "screens/WeatherScreen.qml"
            asynchronous: true
            onLoaded: {
                // Create proper bindings for colors and isDarkMode so they update when the app theme changes
                item.colors = Qt.binding(function() { return colors; });
                item.isDarkMode = Qt.binding(function() { return isDarkMode; });
            }
        }
    }
    
    Component {
        id: calendarScreen
        Loader {
            objectName: "calendarScreenLoader"
            source: "screens/CalendarScreen.qml"
            asynchronous: true
            onLoaded: {
                // Create proper bindings for colors and isDarkMode so they update when the app theme changes
                item.colors = Qt.binding(function() { return colors; });
                item.isDarkMode = Qt.binding(function() { return isDarkMode; });
            }
        }
    }
    
    Component {
        id: photosScreen
        Loader {
            objectName: "photosScreenLoader"
            source: "screens/PhotosScreen.qml"
            asynchronous: true
            onLoaded: {
                // Create proper bindings for colors and isDarkMode so they update when the app theme changes
                item.colors = Qt.binding(function() { return colors; });
                item.isDarkMode = Qt.binding(function() { return isDarkMode; });
            }
        }
    }
    
    Component {
        id: settingsScreen
        Loader {
            objectName: "settingsScreenLoader"
            source: "screens/SettingsScreen.qml"
            asynchronous: true
            onLoaded: {
                // Create proper bindings for colors and isDarkMode so they update when the app theme changes
                item.colors = Qt.binding(function() { return colors; });
                item.isDarkMode = Qt.binding(function() { return isDarkMode; });
            }
        }
    }
    
    // Function to navigate to different screens
    function navigateTo(screenName) {
        // Store the current screen to check if we're navigating to the same screen
        var currentScreenName = "";
        if (stackView.currentItem) {
            currentScreenName = stackView.currentItem.objectName.replace("ScreenLoader", "");
        }
        
        // Only navigate if we're going to a different screen
        if (currentScreenName !== screenName) {
            console.log("Navigating from " + currentScreenName + " to " + screenName);
            
            // Use StackView.Immediate to avoid destroying the previous screen
            var operation = StackView.Immediate;
            
            // Instead of using options, we'll use a different approach
            // We'll use push instead of replace to add screens to the stack
            // This way, screens are not destroyed when navigating away
            
            switch(screenName) {
                case "chat":
                    // First check if the screen is already in the stack
                    var found = false;
                    for (var i = 0; i < stackView.depth; i++) {
                        if (stackView.get(i) && stackView.get(i).objectName === "chatScreenLoader") {
                            // If found, pop to that screen
                            stackView.pop(stackView.get(i), operation);
                            found = true;
                            break;
                        }
                    }
                    // If not found, push it
                    if (!found) {
                        stackView.push(chatScreen, {}, operation);
                    }
                    break;
                case "clock":
                    stackView.push(clockScreen, {}, operation);
                    break;
                case "weather":
                    stackView.push(weatherScreen, {}, operation);
                    break;
                case "calendar":
                    stackView.push(calendarScreen, {}, operation);
                    break;
                case "photos":
                    stackView.push(photosScreen, {}, operation);
                    break;
                case "settings":
                    stackView.push(settingsScreen, {}, operation);
                    break;
            }
        } else {
            console.log("Already on " + screenName + " screen, not navigating");
        }
    }
}
