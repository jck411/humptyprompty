import os
from queue import Queue
import azure.cognitiveservices.speech as speechsdk
from fastapi import WebSocket
from typing import Set, Any, Dict
from backend.config.config import CONFIG

# Global WebSocket connections set
connected_websockets: Set[WebSocket] = set()

# For convenience, extract backend STT settings
BACKEND_STT_SETTINGS: Dict[str, Any] = CONFIG["STT_SETTINGS"]["BACKEND_STT"]

class ContinuousSpeechRecognizer:
    def __init__(self):
        self.speech_key = os.getenv('AZURE_SPEECH_KEY')
        self.speech_region = os.getenv('AZURE_SPEECH_REGION')
        self.is_listening = False
        self.speech_queue = Queue()
        self.setup_recognizer()

    def setup_recognizer(self):
        if not self.speech_key or not self.speech_region:
            raise ValueError("Azure Speech Key or Region is not set.")

        # Create the SpeechConfig using subscription key and region.
        speech_config = speechsdk.SpeechConfig(
            subscription=self.speech_key,
            region=self.speech_region
        )
        # Configure language
        speech_config.speech_recognition_language = BACKEND_STT_SETTINGS.get("LANGUAGE", "en-US")

        # Configure auto punctuation using set_property_by_name
        if BACKEND_STT_SETTINGS.get("AUTO_PUNCTUATION", False):
            speech_config.set_property_by_name("SpeechServiceResponse_AutoPunctuation", "true")

        # Configure profanity filtering
        profanity_option = BACKEND_STT_SETTINGS.get("PROFANITY_OPTION", "raw").lower()
        if profanity_option == "raw":
            speech_config.set_profanity(speechsdk.ProfanityOption.Raw)
        elif profanity_option == "masked":
            speech_config.set_profanity(speechsdk.ProfanityOption.Masked)
        elif profanity_option == "removed":
            speech_config.set_profanity(speechsdk.ProfanityOption.Removed)

        # Create audio config from the default microphone
        audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
        self.speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config
        )

        # Connect events
        self.speech_recognizer.recognized.connect(self.handle_final_result)
        if BACKEND_STT_SETTINGS.get("INTERIM_RESULTS", False):
            self.speech_recognizer.recognizing.connect(self.handle_interim_result)

    def handle_final_result(self, evt):
        if evt.result.text and self.is_listening:
            self.speech_queue.put(evt.result.text)

    def handle_interim_result(self, evt):
        if evt.result.text and self.is_listening and BACKEND_STT_SETTINGS.get("INTERIM_RESULTS", False):
            self.speech_queue.put(f"(interim) {evt.result.text}")

    def start_listening(self):
        if not self.is_listening:
            self.is_listening = True
            self.speech_recognizer.start_continuous_recognition()
            print("Azure STT: Started listening.")

    def pause_listening(self):
        if self.is_listening:
            self.is_listening = False
            self.speech_recognizer.stop_continuous_recognition()
            print("Azure STT: Paused listening.")

    def get_speech_nowait(self):
        try:
            return self.speech_queue.get_nowait()
        except Exception:
            return None

# Create a single instance for your application
stt_instance = ContinuousSpeechRecognizer()

async def broadcast_stt_state():
    """Broadcasts the current STT state to all connected WebSocket clients"""
    message = {"is_listening": stt_instance.is_listening}
    failed_ws = set()
    
    for websocket in connected_websockets:
        try:
            await websocket.send_json(message)
        except Exception:
            failed_ws.add(websocket)
            
    connected_websockets.difference_update(failed_ws)
