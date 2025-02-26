import os
from frontend.stt.config import STTConfig
from frontend.stt.deepgram_stt import DeepgramSTTProvider

class FrontendSTTManager:
    def __init__(self):
        self._current_instance = None
        self._tts_playing = False
        self._global_stt_enabled = True

    def create_stt_instance(self, config_settings=None):
        """Create a new STT provider instance based on provided settings"""
        # Default settings if none provided
        if config_settings is None:
            config_settings = {
                "provider": "deepgram",
                "settings": {
                    "LANGUAGE": "en-US",
                    "MODEL": "nova-2",
                    "SAMPLE_RATE": 16000,
                    "SMART_FORMAT": True,
                    "INTERIM_RESULTS": True,
                    "ENCODING": "linear16",
                    "CHANNELS": 1,
                    "ENDPOINTING": True,
                    "UTTERANCE_END_MS": 1000
                },
                "enabled": True
            }
        
        provider = config_settings["provider"].lower()
        if provider == "deepgram":
            settings = config_settings["settings"]
        else:
            raise ValueError(f"Unsupported STT provider: {provider}")

        stt_config = STTConfig(
            provider=provider,
            settings=settings,
            enabled=config_settings.get("enabled", True)
        )

        # Clean up existing instance if needed
        try:
            if self._current_instance:
                if self._current_instance.is_listening:
                    self._current_instance.pause_listening()
                self._current_instance = None
        except Exception as e:
            print(f"Warning: Error cleaning up old STT instance: {e}")

        # Create and store new instance
        instance = None
        if provider == "deepgram":
            instance = DeepgramSTTProvider(stt_config)

        # Store the new instance
        self._current_instance = instance
        return instance

    def get_instance(self):
        """Get the current STT instance, creating one if none exists"""
        if not self._current_instance:
            self._current_instance = self.create_stt_instance()
        return self._current_instance
    
    def set_tts_playing_state(self, is_playing):
        """Called when TTS starts/stops playing"""
        prev_state = self._tts_playing
        self._tts_playing = is_playing
        
        # If TTS has stopped playing and global STT is enabled, resume STT
        if prev_state and not is_playing and self._global_stt_enabled:
            if self._current_instance:
                self._current_instance.start_listening()
        
        # If TTS has started playing, pause STT
        elif not prev_state and is_playing:
            if self._current_instance and self._current_instance.is_listening:
                self._current_instance.pause_listening()
    
    def set_global_stt_enabled(self, enabled):
        """Enable or disable STT globally"""
        self._global_stt_enabled = enabled
        if self._current_instance:
            self._current_instance.config.enabled = enabled
            
            # If we're disabling globally, pause listening
            if not enabled and self._current_instance.is_listening:
                self._current_instance.pause_listening()
            
            # If we're enabling globally and TTS isn't playing, start listening
            elif enabled and not self._tts_playing:
                self._current_instance.start_listening()

# Create a singleton instance
stt_manager = FrontendSTTManager()
