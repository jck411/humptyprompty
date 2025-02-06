import os
from queue import Queue
import azure.cognitiveservices.speech as speechsdk
from fastapi import WebSocket
from typing import Set

# Global WebSocket connections set
connected_websockets: Set[WebSocket] = set()

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

        speech_config = speechsdk.SpeechConfig(
            subscription=self.speech_key,
            region=self.speech_region
        )
        speech_config.speech_recognition_language = "en-US"

        audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
        self.speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config
        )
        self.speech_recognizer.recognized.connect(self.handle_final_result)

    def handle_final_result(self, evt):
        if evt.result.text and self.is_listening:
            self.speech_queue.put(evt.result.text)

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
        except:
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
