// qml/ChatArea.qml
import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: chatArea
    property color userColor: "#3b4261"
    property color assistantColor: "#F7F9FB"
    property color textColor: "#000000"
    
    // Add a timer to scroll to bottom after content changes
    Timer {
        id: scrollTimer
        interval: 50
        onTriggered: scrollToBottom()
    }

    ScrollView {
        id: scrollView
        anchors.fill: parent
        ScrollBar.vertical.policy: ScrollBar.AsNeeded
        clip: true

        Column {
            id: messageColumn
            width: scrollView.width
            spacing: 8
            leftPadding: 8
            rightPadding: 8
            topPadding: 8
            bottomPadding: 8
        }
    }

    function scrollToBottom() {
        // Use QML's contentItem property to find the actual flickable
        if (scrollView.contentItem) {
            scrollView.contentItem.contentY = scrollView.contentHeight - scrollView.height
        }
    }

    function addUserMessage(text) {
        // Clear chat if text is empty (special case)
        if (!text || text.length === 0) {
            for (var i = messageColumn.children.length - 1; i >= 0; --i) {
                var child = messageColumn.children[i];
                if (child)
                    child.destroy();
            }
            return;
        }
        
        var comp = userBubbleComponent;
        var bubble = comp.createObject(messageColumn, {
            "messageText": text,
            "isUser": true,
            "bubbleColor": chatArea.userColor,
            "textColor": chatArea.textColor
        });
        scrollTimer.restart();
    }

    function addAssistantMessage(text) {
        if (!assistantBubble) {
            var comp = assistantBubbleComponent;
            assistantBubble = comp.createObject(messageColumn, {
                "messageText": text,
                "isUser": false,
                "bubbleColor": chatArea.assistantColor,
                "textColor": chatArea.textColor
            });
        } else {
            assistantBubble.messageText = text;
        }
        scrollTimer.restart();
    }

    function finalizeAssistantMessage() {
        assistantBubble = null;
    }

    function updateBubbleStyles() {
        for (var i = 0; i < messageColumn.children.length; ++i) {
            var child = messageColumn.children[i];
            if (child && child.hasOwnProperty("isUser")) {
                child.bubbleColor = child.isUser ? chatArea.userColor : chatArea.assistantColor;
                child.textColor = chatArea.textColor;
            }
        }
    }

    property var assistantBubble: null

    Component {
        id: userBubbleComponent
        MessageBubble { }
    }
    
    Component {
        id: assistantBubbleComponent
        MessageBubble { }
    }

    Connections {
        target: backend
        
        function onNewUserMessage(text) {
            addUserMessage(text);
        }
        
        function onAssistantTextUpdated(text) {
            addAssistantMessage(text);
        }
        
        function onAssistantResponseComplete() {
            finalizeAssistantMessage();
        }
    }
    
    // Add this to debug WebSocket connectivity
    Connections {
        target: wsClient
        
        function onConnection_status(connected) {
            console.log("WebSocket connection status changed: " + (connected ? "Connected" : "Disconnected"))
        }
    }
}
