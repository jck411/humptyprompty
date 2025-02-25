import os
import azure.cognitiveservices.speech as speechsdk
from backend.config.config import CONFIG
from backend.stt.base import BaseSTTProvider, STTState
from backend.stt.config import STTConfig

class AzureSTTProvider(BaseSTTProvider):
    def __init__(self, config: STTConfig):
        # Pass the entire config to the base class.
        super().__init__(config)
        self.config = config  # Ensures that we have access to all settings.
        self.speech_key = os.getenv("AZURE_SPEECH_KEY")
        self.speech_region = os.getenv("AZURE_SPEECH_REGION")
        if self.config.enabled:
            self.setup_recognizer()
            self._state = STTState.READY
        else:
            self._state = STTState.PAUSED

    def setup_recognizer(self) -> None:
        print("\nAzure STT: Setting up recognizer...")
        if not self.speech_key or not self.speech_region:
            self._state = STTState.ERROR
            print("Azure STT: Missing credentials - speech key or region not set")
            raise ValueError("Azure Speech Key or Region is not set.")

        try:
            # Create the SpeechConfig using subscription key and region.
            speech_config = speechsdk.SpeechConfig(
                subscription=self.speech_key,
                region=self.speech_region
            )
            print("Azure STT: Created speech config")
            
            # Configure language.
            speech_config.speech_recognition_language = self.config.settings.get("LANGUAGE", "en-US")

            # Configure auto punctuation.
            if self.config.settings.get("AUTO_PUNCTUATION", False):
                speech_config.set_property_by_name("SpeechServiceResponse_AutoPunctuation", "true")

            # Configure profanity filtering.
            profanity_option = self.config.settings.get("PROFANITY_OPTION", "raw").lower()
            if profanity_option == "raw":
                speech_config.set_profanity(speechsdk.ProfanityOption.Raw)
            elif profanity_option == "masked":
                speech_config.set_profanity(speechsdk.ProfanityOption.Masked)
            elif profanity_option == "removed":
                speech_config.set_profanity(speechsdk.ProfanityOption.Removed)

            # Create audio config from the default microphone.
            audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
            self.speech_recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config
            )

            # Connect events.
            self.speech_recognizer.recognized.connect(self.handle_final_result)
            self.speech_recognizer.recognizing.connect(self.handle_interim_result)
            self.speech_recognizer.session_started.connect(
                lambda evt: print(f"\nAzure STT: Session started (SessionId: {evt.session_id})")
            )
            self.speech_recognizer.session_stopped.connect(
                lambda evt: print(f"\nAzure STT: Session stopped (SessionId: {evt.session_id})")
            )
            self.speech_recognizer.canceled.connect(
                lambda evt: print(f"\nAzure STT: Canceled - Reason: {evt.cancellation_details.reason}, Details: {evt.cancellation_details.error_details}")
            )

            self._state = STTState.READY
            print("Azure STT: Setup complete - State: READY")
        except Exception as e:
            self._state = STTState.ERROR
            raise ValueError(f"Failed to setup Azure recognizer: {str(e)}")

    def handle_final_result(self, evt) -> None:
        if evt.result.text:
            print(f"\nAzure STT [Final]: {evt.result.text}")
            if self.is_listening and self.config.enabled:
                # Don't clear interim results - just put the final result
                self.speech_queue.put_nowait(f"[final] {evt.result.text}")

    def handle_interim_result(self, evt) -> None:
        if evt.result.text:
            print(f"\rAzure STT [Interim]: {evt.result.text}", end="", flush=True)
            if (self.is_listening and self.config.enabled and 
                self.config.settings.get("INTERIM_RESULTS", False)):
                # Don't clear previous interim results
                self.speech_queue.put_nowait(f"(interim) {evt.result.text}")

    def _start_listening_impl(self) -> None:
        try:
            print("Azure STT: Starting continuous recognition...")
            # Don't clear queue here - let the speech listener handle it
            self.speech_recognizer.start_continuous_recognition()
        except Exception as e:
            print(f"Azure STT: Error starting recognition: {e}")
            self._state = STTState.ERROR

    def _stop_listening_impl(self) -> None:
        try:
            print("Azure STT: Stopping continuous recognition...")
            self.speech_recognizer.stop_continuous_recognition()
        except Exception as e:
            print(f"Azure STT: Error stopping recognition: {e}")
            self._state = STTState.ERROR

    def _pause_listening_impl(self) -> None:
        try:
            print("Azure STT: Pausing continuous recognition...")
            self.speech_recognizer.stop_continuous_recognition()
        except Exception as e:
            print(f"Azure STT: Error during pause: {e}")
            self._state = STTState.ERROR

# Create configuration from global config.
stt_config = STTConfig(
    provider="azure",
    settings=CONFIG["STT_MODELS"]["AZURE_STT"],
    enabled=CONFIG["GENERAL_AUDIO"]["STT_ENABLED"]
)

# Create a single instance for your application.
stt_instance = AzureSTTProvider(stt_config)
