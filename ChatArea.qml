// ChatArea.qml
import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: chatArea
    property color userColor: "#3b4261"
    property color assistantColor: "#F7F9FB"
    property color textColor: "#000000"

    // Column to hold chat message bubbles, inside a ScrollView for scrolling
    ScrollView {
        id: scrollView
        anchors.fill: parent
        ScrollBar.vertical.policy: ScrollBar.AsNeeded

        // Content of the scroll – a Column of message bubbles
        Column {
            id: messageColumn
            width: scrollView.width
        }
    }

    // Helper: scroll to bottom of chat
    function scrollToBottom() {
        scrollView.scrollToPoint(0, scrollView.contentHeight)
    }

    // Add a user message bubble to the chat
    function addUserMessage(text) {
        if (!text || text.length === 0) {
            // If empty text, interpret as a command to clear chat
            // Destroy all children in messageColumn
            for (let i = messageColumn.children.length - 1; i >= 0; --i) {
                let child = messageColumn.children[i];
                if (child) child.destroy();
            }
            return;
        }
        // Create a MessageBubble for the user message
        let comp = userBubbleComponent;
        let bubble = comp.createObject(messageColumn, {
            "messageText": text,
            "isUser": true,
            "bubbleColor": chatArea.userColor,
            "textColor": chatArea.textColor
        });
        chatArea.scrollToBottom();
    }

    // Add or update the assistant message bubble (for streaming responses)
    function addAssistantMessage(text) {
        if (!assistantBubble) {
            // Create a new assistant message bubble if none exists in progress
            let comp = assistantBubbleComponent;
            assistantBubble = comp.createObject(messageColumn, {
                "messageText": text,
                "isUser": false,
                "bubbleColor": chatArea.assistantColor,
                "textColor": chatArea.textColor
            });
        } else {
            // Update existing assistant bubble's text
            assistantBubble.messageText = text;
        }
        chatArea.scrollToBottom();
    }

    // Finalize the assistant bubble when complete
    function finalizeAssistantMessage() {
        assistantBubble = null;
    }

    // Reapply styling to all bubbles (e.g., after theme change)
    function updateBubbleStyles() {
        for (let i = 0; i < messageColumn.children.length; ++i) {
            let child = messageColumn.children[i];
            if (child && child.hasOwnProperty("isUser")) {
                child.bubbleColor = child.isUser ? chatArea.userColor : chatArea.assistantColor;
                child.textColor = chatArea.textColor;
            }
        }
    }

    // Keep track of the current in-progress assistant bubble (if any)
    property var assistantBubble: null

    // Define components for message bubbles (user and assistant use same component with different properties)
    Component {
        id: userBubbleComponent
        MessageBubble { }  // see MessageBubble.qml
    }
    Component {
        id: assistantBubbleComponent
        MessageBubble { }
    }

    // Connect to backend signals to update chat UI
    Connections {
        target: backend
        onNewUserMessage: {
            chatArea.addUserMessage(text);
        }
        onAssistantTextUpdated: {
            chatArea.addAssistantMessage(text);
        }
        onAssistantResponseComplete: {
            chatArea.finalizeAssistantMessage();
        }
    }
}
