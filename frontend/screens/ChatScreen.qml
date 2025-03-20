import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    id: chatScreen
    anchors.fill: parent
    
    // Colors and theme properties
    property var colors
    property bool isDarkMode: false
    
    // Update colors when isDarkMode changes
    onIsDarkModeChanged: {
        console.log("ChatScreen isDarkMode changed to: " + isDarkMode);
    }
    
    // Reference to the chatModel exposed from Python as a context property
    property var chatModel
    
    // State properties
    property bool isSttActive: false
    property bool isTtsActive: true
    property bool isConnected: false
    property string connectionStatus: isConnected ? "Connected" : "Disconnected"
    
    // Property change handler for chatModel
    onChatModelChanged: {
        console.log("chatModel changed in ChatScreen.qml");
        if (chatModel) {
            initializeChatModel();
        }
    }
    
    // Component initialization
    Component.onCompleted: {
        // The WebSocket connection is handled in the Python side
        // The chatModel is already connected when it's passed to QML
        
        console.log("Component.onCompleted in ChatScreen.qml");
        console.log("chatModel exists: " + (chatModel !== null && chatModel !== undefined));
        
        // Initialize chatModel if it exists
        if (chatModel) {
            initializeChatModel();
        } else {
            console.log("ChatModel is not available in Component.onCompleted");
            // We'll initialize it when it becomes available via onChatModelChanged
        }
    }
    
    // Function to initialize the chat model
    function initializeChatModel() {
        // Connect to ChatModel signals
        chatModel.sttStateChanged.connect(updateSttState);
        chatModel.ttsStateChanged.connect(updateTtsState);
        chatModel.connectionStatusChanged.connect(updateConnectionStatus);
        
        // Debug connection status
        console.log("Initial connection status: " + chatModel.isConnected);
        console.log("Connection status property exists: " + (typeof chatModel.isConnected !== 'undefined'));
        
        // Update the connection status
        isConnected = chatModel.isConnected;
        
        // If not connected, try to reconnect
        if (!chatModel.isConnected) {
            console.log("ChatModel is not connected, attempting to reconnect");
            // Use the reconnect method from the ChatModel
            chatModel.reconnect();
        }
        
        // Load message history from ChatModel
        console.log("Loading message history from ChatModel");
        var messages = chatModel.getMessageHistory();
        console.log("Message history length: " + messages.length);
        
        // Clear the model first to avoid duplicates
        messageListView.model.clear();
        
        // Add messages to the ListView model
        for (var i = 0; i < messages.length; i++) {
            messageListView.model.append(messages[i]);
        }
    }
    
    // Handle component destruction
    Component.onDestruction: {
        console.log("ChatScreen is being destroyed");
        // Don't disconnect signals or WebSocket here, as we want to maintain the connection
    }
    
    // Layout for entire chat screen
    ColumnLayout {
        anchors.fill: parent
        spacing: 2
        
        // Top bar with controls
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 50
            color: colors.surface
            
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 10
                
                // STT Toggle Button
                IconButton {
                    id: sttToggle
                    iconSource: isSttActive ? "../icons/stt_on.svg" : "../icons/stt_off.svg"
                    iconSize: 24
                    implicitWidth: 45
                    implicitHeight: 45
                    themeColors: colors
                    toggleButton: true
                    toggled: isSttActive
                    
                    ToolTip.visible: hovered
                    ToolTip.text: isSttActive ? "Turn STT Off" : "Turn STT On"
                    
                    onClicked: {
                        if (chatModel) {
                            chatModel.toggleStt();
                        }
                    }
                }
                
                // TTS Toggle Button
                IconButton {
                    id: ttsToggle
                    iconSource: isTtsActive ? "../icons/tts_on.svg" : "../icons/tts_off.svg"
                    iconSize: 24
                    implicitWidth: 45
                    implicitHeight: 45
                    themeColors: colors
                    toggleButton: true
                    toggled: isTtsActive
                    
                    ToolTip.visible: hovered
                    ToolTip.text: isTtsActive ? "Turn TTS Off" : "Turn TTS On"
                    
                    onClicked: {
                        if (chatModel) {
                            chatModel.toggleTts();
                        }
                    }
                }
                
                // Clear Chat Button
                IconButton {
                    id: clearChatButton
                    iconSource: "../icons/x-circle.svg"
                    iconSize: 24
                    implicitWidth: 45
                    implicitHeight: 45
                    themeColors: colors
                    
                    ToolTip.visible: hovered
                    ToolTip.text: "Clear Chat History"
                    
                    onClicked: {
                        messageListView.model.clear();
                        if (chatModel) {
                            chatModel.clearChat();
                        }
                    }
                }
                
                // Connection status indicator
                Text {
                    text: connectionStatus
                    color: isConnected ? colors.primary : "red"
                    font.pixelSize: 12
                }
                
                Item { Layout.fillWidth: true } // Spacer
            }
        }
        
        // Chat message area
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: colors.background
            
            ScrollView {
                id: chatScrollView
                anchors.fill: parent
                anchors.margins: 10
                clip: true
                ScrollBar.vertical.policy: ScrollBar.AsNeeded
                
                ListView {
                    id: messageListView
                    width: parent.width
                    height: parent.height
                    spacing: 10
                    
                    // Connect to model from Python
                    model: ListModel {}
                    
                    // Define how each message is displayed
                    delegate: Item {
                        id: delegateItem
                        width: ListView.view.width
                        height: messageBubble.height
                        
                        MessageBubble {
                            id: messageBubble
                            messageText: model.text
                            isUser: model.isUser
                            themeColors: colors
                            width: Math.min(implicitWidth, delegateItem.width * 0.8)
                            
                            // Anchor to left or right based on sender
                            anchors.right: isUser ? delegateItem.right : undefined
                            anchors.left: isUser ? undefined : delegateItem.left
                            anchors.rightMargin: isUser ? 5 : 0
                            anchors.leftMargin: isUser ? 0 : 5
                        }
                    }
                    
                    // Auto-scroll to bottom when new messages arrive
                    onCountChanged: {
                        positionViewAtEnd();
                    }
                }
            }
        }
        
        // Input area
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(Math.max(60, inputArea.implicitHeight), 120)
            color: colors.surface
            
            RowLayout {
                id: inputArea
                anchors.fill: parent
                anchors.margins: 5
                spacing: 5
                
                // Text input field
                CustomTextInput {
                    id: messageInput
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 40
                    themeColors: colors
                    
                    sendCallback: function(text) {
                        sendMessage(text);
                    }
                }
                
                // Buttons container
                ColumnLayout {
                    spacing: 5
                    
                    // Send Button
                    IconButton {
                        id: sendButton
                        iconSource: "../icons/send.svg"
                        iconSize: 24
                        implicitWidth: 45
                        implicitHeight: 45
                        themeColors: colors
                        
                        ToolTip.visible: hovered
                        ToolTip.text: "Send Message"
                        
                        onClicked: {
                            if (messageInput.text.trim().length > 0) {
                                sendMessage(messageInput.text.trim());
                                messageInput.text = "";
                            }
                        }
                    }
                    
                    // Stop Button
                    IconButton {
                        id: stopButton
                        iconSource: "../icons/stop_all.svg"
                        iconSize: 24
                        implicitWidth: 45
                        implicitHeight: 45
                        themeColors: colors
                        
                        ToolTip.visible: hovered
                        ToolTip.text: "Stop Generation & Audio"
                        
                        onClicked: {
                            if (chatModel) {
                                chatModel.stopGeneration();
                            }
                        }
                    }
                }
            }
        }
    }
    
    // Connections to handle signals from the ChatModel
    Connections {
        target: chatModel
        
        function onConnectionStatusChanged(connected) {
            console.log("Connection status changed to: " + connected);
            updateConnectionStatus(connected);
        }
    }
    
    // Connect to bridge for STT state changes
    Connections {
        target: bridge
        
        function onSttStateChanged(active) {
            isSttActive = active;
        }
    }
    
    // Function to update connection status
    function updateConnectionStatus(connected) {
        isConnected = connected;
        console.log("Connection status updated to: " + isConnected);
    }
    
    // Function to send a message
    function sendMessage(text) {
        // Add to UI
        messageListView.model.append({
            text: text,
            isUser: true
        });
        
        // Send to backend
        if (chatModel) {
            chatModel.sendMessage(text);
        }
    }
    
    // Function to receive a message from the backend (to be called from Python)
    // This is called when a complete message is received
    function receiveMessage(text) {
        console.log("receiveMessage called with text: " + text);
        // We don't need to do anything here since we're handling streaming tokens
        // in addTokenToMessage
    }
    
    // Function to add token to an in-progress assistant message
    function addTokenToMessage(text) {
        console.log("addTokenToMessage called with text: " + text);
        // If the last message is from the assistant, update it
        // Otherwise create a new message
        let model = messageListView.model;
        if (model.count > 0 && !model.get(model.count - 1).isUser) {
            console.log("Updating existing assistant message");
            model.setProperty(model.count - 1, "text", text);
        } else {
            console.log("Adding new assistant message");
            model.append({
                text: text,
                isUser: false
            });
        }
    }
    
    // Update STT state
    function updateSttState(isActive) {
        isSttActive = isActive;
    }
    
    // Update TTS state
    function updateTtsState(isActive) {
        isTtsActive = isActive;
    }
}
