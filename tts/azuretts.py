import os
import asyncio
import azure.cognitiveservices.speech as speechsdk
from typing import Optional

from config import CONFIG, conditional_print

class PushAudioOutputStreamCallback(speechsdk.audio.PushAudioOutputStreamCallback):
    def __init__(self, audio_queue: asyncio.Queue, stop_event: asyncio.Event):
        super().__init__()
        self.audio_queue = audio_queue
        self.stop_event = stop_event
        self.loop = asyncio.get_event_loop()

    def write(self, data: memoryview) -> int:
        if self.stop_event.is_set():
            return 0
        self.loop.call_soon_threadsafe(self.audio_queue.put_nowait, data.tobytes())
        return len(data)

    def close(self):
        self.loop.call_soon_threadsafe(self.audio_queue.put_nowait, None)

def create_ssml(phrase: str, voice: str, prosody: dict) -> str:
    return f"""
<speak version='1.0' xml:lang='en-US'>
    <voice name='{voice}'>
        <prosody rate='{prosody["rate"]}' pitch='{prosody["pitch"]}' volume='{prosody["volume"]}'>
            {phrase}
        </prosody>
    </voice>
</speak>
"""

async def azure_text_to_speech_processor(phrase_queue: asyncio.Queue,
                                       audio_queue: asyncio.Queue,
                                       stop_event: asyncio.Event):
    """
    Continuously read text from phrase_queue, convert to speech with Azure TTS,
    and push PCM data into audio_queue. Stops early if stop_event is set.
    """
    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=os.getenv("AZURE_SPEECH_KEY"),
            region=os.getenv("AZURE_SPEECH_REGION")
        )
        prosody = CONFIG["TTS_MODELS"]["AZURE_TTS"]["PROSODY"]
        voice = CONFIG["TTS_MODELS"]["AZURE_TTS"]["TTS_VOICE"]
        audio_format = getattr(
            speechsdk.SpeechSynthesisOutputFormat,
            CONFIG["TTS_MODELS"]["AZURE_TTS"]["AUDIO_FORMAT"]
        )
        speech_config.set_speech_synthesis_output_format(audio_format)
        conditional_print("Azure TTS configured successfully.", "default")

        while True:
            if stop_event.is_set():
                conditional_print("Azure TTS stop_event is set. Exiting TTS loop.", "default")
                await audio_queue.put(None)
                return

            phrase = await phrase_queue.get()
            if phrase is None or phrase.strip() == "":
                await audio_queue.put(None)
                conditional_print("Azure TTS received stop signal (None).", "default")
                return

            try:
                ssml_phrase = create_ssml(phrase, voice, prosody)
                push_stream_callback = PushAudioOutputStreamCallback(audio_queue, stop_event)
                push_stream = speechsdk.audio.PushAudioOutputStream(push_stream_callback)
                audio_cfg = speechsdk.audio.AudioOutputConfig(stream=push_stream)

                synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_cfg)
                result_future = synthesizer.speak_ssml_async(ssml_phrase)
                conditional_print(f"Azure TTS synthesizing phrase: {phrase}", "default")
                await asyncio.get_event_loop().run_in_executor(None, result_future.get)
                conditional_print("Azure TTS synthesis completed.", "default")

            except Exception as e:
                conditional_print(f"Azure TTS error: {e}", "default")
                await audio_queue.put(None)
                return

    except Exception as e:
        conditional_print(f"Azure TTS config error: {e}", "default")
        await audio_queue.put(None)
