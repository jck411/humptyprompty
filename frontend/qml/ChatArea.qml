// qml/ChatArea.qml
import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: chatArea
    property color userColor: "#3b4261"
    property color assistantColor: "#F7F9FB"
    property color textColor: "#000000"

    ScrollView {
        id: scrollView
        anchors.fill: parent
        ScrollBar.vertical.policy: ScrollBar.AsNeeded

        Column {
            id: messageColumn
            width: scrollView.width
        }
    }

    function scrollToBottom() {
        scrollView.scrollToPoint(0, scrollView.contentHeight)
    }

    function addUserMessage(text) {
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
        scrollToBottom();
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
        scrollToBottom();
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
        onNewUserMessage: {
            addUserMessage(text);
        }
        onAssistantTextUpdated: {
            addAssistantMessage(text);
        }
        onAssistantResponseComplete: {
            finalizeAssistantMessage();
        }
    }
}
