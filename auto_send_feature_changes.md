# Auto-Send Feature Changes

## Overview

The auto-send feature has been modified according to the requirements:

1. Removed the auto-send toggle button
2. Made STT automatically enable auto-send when it's turned on
3. Added a countdown display showing the seconds remaining before STT times out due to inactivity

## Implementation Details

### 1. ChatController Changes

The `ChatController` class has been modified to automatically enable auto-send when STT is turned on:

```python
def handle_frontend_stt_enabled(self, is_enabled):
    """Handle frontend STT enabled state changes"""
    self.stt_enabled = is_enabled
    self.stt_state_changed.emit(is_enabled, self.stt_listening, self.text_chat_enabled)
    
    # If STT is turned on, automatically enable auto-send
    # If STT is turned off, also turn off auto-send
    if is_enabled and not self.auto_send_enabled:
        self.auto_send_enabled = True
        self.auto_send_state_changed.emit(True)
        logger.info("Auto-send automatically enabled with STT")
    elif not is_enabled and self.auto_send_enabled:
        self.auto_send_enabled = False
        self.auto_send_state_changed.emit(False)
        logger.info("Auto-send automatically disabled with STT")
```

This ensures that when STT is enabled, auto-send is automatically enabled as well, and when STT is disabled, auto-send is also disabled.

### 2. TopButtons Changes

The `TopButtons` class has been modified to:

1. Remove the auto-send button
2. Add a countdown label that shows the seconds remaining before STT times out
3. Implement a timer to update the countdown

Key changes:

```python
# Create countdown label (replaces auto-send button)
self.countdown_label = QLabel("0")
self.countdown_label.setFixedSize(45, 45)
self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
font = QFont()
font.setPointSize(14)
font.setBold(True)
self.countdown_label.setFont(font)
self.countdown_label.setStyleSheet("""
    QLabel {
        color: #0D6EFD;
        background-color: transparent;
        border-radius: 20px;
    }
""")
self.countdown_label.setVisible(False)  # Initially hidden

# Timer for countdown
self.countdown_timer = QTimer(self)
self.countdown_timer.setInterval(1000)  # 1 second
self.countdown_timer.timeout.connect(self.update_countdown)
self.countdown_value = 0
```

The countdown is started when auto-send is enabled:

```python
def update_auto_send_state(self, is_enabled):
    """Update the auto-send state and start countdown if enabled"""
    if is_enabled:
        self.start_countdown()
    else:
        self.countdown_timer.stop()
        self.countdown_label.setVisible(False)

def start_countdown(self, seconds=15):
    """
    Start or restart the countdown timer
    
    This countdown reflects the Deepgram keepalive timeout (default 15 seconds).
    When the countdown reaches 0, the STT will automatically disable itself.
    """
    self.countdown_timer.stop()
    self.countdown_value = seconds
    self.countdown_label.setText(str(self.countdown_value))
    self.countdown_label.setVisible(True)
    self.countdown_timer.start()
```

The countdown is also started when STT is enabled and listening:

```python
def update_stt_state(self, is_enabled, is_listening=False, is_text_chat=False):
    # ...
    
    # Show/hide countdown based on STT state
    if is_enabled and is_listening:
        # Start or restart countdown when STT is enabled and listening
        self.start_countdown()
    else:
        # Hide countdown when STT is disabled
        self.countdown_timer.stop()
        self.countdown_label.setVisible(False)
```

### 3. ChatScreen Changes

The `ChatScreen` class has been modified to remove the auto-send toggle signal connection:

```python
def connect_signals(self):
    """Connect signals between UI components and controller"""
    # Connect top buttons signals
    self.top_buttons.stt_toggled.connect(self.controller.toggle_stt)
    self.top_buttons.tts_toggled.connect(self.handle_tts_toggle)
    self.top_buttons.clear_clicked.connect(self.clear_chat)
    # Stop button - direct call to synchronous stop method instead of async
    self.top_buttons.stop_clicked.connect(self.stop_all)
    
    # ... (removed auto_send_toggled connection)
```

## How It Works

1. When the user enables STT (Speech-to-Text):
   - Auto-send is automatically enabled
   - The countdown label becomes visible and starts counting down from 15 seconds (matching the Deepgram keepalive timeout)

2. When speech is detected:
   - The Deepgram STT resets its internal activity timer
   - The countdown should ideally reset as well (though this is not currently implemented)

3. When the countdown reaches 0:
   - The countdown label is hidden
   - The STT automatically disables itself due to inactivity (handled by Deepgram's keepalive timeout)

4. When the user disables STT:
   - Auto-send is automatically disabled
   - The countdown label is hidden

This implementation ensures that when STT is turned on, it will automatically enable auto-send and show a countdown timer that reflects the STT inactivity timeout, making the user experience more intuitive and removing the need for a separate auto-send toggle button.

## Additional Improvements

To make the countdown more accurate, we've implemented a feature to reset the countdown whenever speech is detected, matching the behavior of Deepgram's internal activity timer. This ensures that the visual countdown accurately reflects the actual timeout that will occur.

This was implemented by:

1. Modifying the `handle_interim_stt_text` method in `ChatScreen` to reset the countdown:

```python
def handle_interim_stt_text(self, text):
    """Handle interim STT text"""
    if self.controller.stt_enabled and text.strip():
        # Update or create an STT transcript bubble
        self.chat_area.update_transcription(text)
        
        # Reset the countdown timer when speech is detected
        if self.controller.auto_send_enabled:
            self.top_buttons.start_countdown()
```

2. Ensuring that the `ChatController` only emits the interim text signal when there's actual content:

```python
def handle_interim_stt_text(self, text):
    """Handle interim STT text updates"""
    # Only emit if there's actual content
    if text.strip():
        # Reset the countdown timer when speech is detected
        self.interim_stt_text_received.emit(text)
```

This creates a complete feedback loop where:
1. Deepgram detects speech and resets its internal activity timer
2. The ChatController receives the interim text and emits a signal
3. The ChatScreen receives the signal and resets the countdown timer
4. The user sees the countdown reset, providing visual feedback that their speech was detected
