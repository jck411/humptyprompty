# Speech-to-Text (STT) Module

## Overview
This module provides speech-to-text capabilities using the Deepgram API. It handles real-time transcription, manages audio input, and supports features like keepalive for maintaining connections during pauses.

## Configuration
Configuration settings are defined in `config.py`:
- `STT_CONFIG`: Global settings for STT functionality
- `AUDIO_CONFIG`: Configuration for audio capture
- `DEEPGRAM_CONFIG`: Deepgram-specific settings, including keepalive parameters

## Key Components

### DeepgramSTT Class
The main class that interfaces with Deepgram's API to provide STT capabilities. It manages:
- Connection lifecycle
- Audio state (enabled/disabled, paused/playing)
- Keepalive functionality
- Transcription processing

## Audio State Management

### Consolidated Approach
The class uses a consolidated `handle_audio_state` method to manage all audio state transitions:

```python
handle_audio_state(action, should_emit_signals=True)
```

#### Parameters:
- `action`: The state transition to perform
  - `'enable'`: Enable STT and start a new connection
  - `'disable'`: Disable STT and close connection
  - `'pause'`: Pause audio input
  - `'resume'`: Resume audio input
  - `'toggle_enabled'`: Toggle between enabled/disabled
- `should_emit_signals`: Whether to emit UI signals

#### Benefits:
1. **Centralized Logic**: All state transition logic is in one place
2. **Consistency**: Ensures consistent state management
3. **Reduced Redundancy**: Eliminates duplicate code
4. **Maintainability**: Easier to update and maintain

### Integration
This approach is used by higher-level methods like `set_enabled`, `set_paused`, and `toggle`, which now delegate to the central state manager rather than implementing their own state logic.

## Usage Example

```python
# Enable STT
stt.handle_audio_state('enable')

# Pause audio input
stt.handle_audio_state('pause')

# Resume audio input
stt.handle_audio_state('resume')

# Disable STT
stt.handle_audio_state('disable')
```

## Keepalive Functionality
The module supports keeping Deepgram connections open during pauses by sending periodic keepalive messages, which improves responsiveness when resuming. 