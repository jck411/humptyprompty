import os
import asyncio
import azure.cognitiveservices.speech as speechsdk
from ..config.config import CONFIG

class AzureTTS:
    def __init__(self):
        self.speech_config = speechsdk.SpeechConfig(
            subscription=os.getenv("AZURE_SPEECH_KEY"),
            region=os.getenv("AZURE_SPEECH_REGION")
        )
        self.audio_format = getattr(
            speechsdk.SpeechSynthesisOutputFormat,
            CONFIG["TTS_MODELS"]["AZURE_TTS"]["AUDIO_FORMAT"]
        )
        self.speech_config.set_speech_synthesis_output_format(self.audio_format)
        
    async def stream_to_audio(self, text):
        audio_queue = asyncio.Queue()
        stop_event = asyncio.Event()
        
        push_stream_callback = PushAudioOutputStreamCallback(audio_queue, stop_event)
        push_stream = speechsdk.audio.PushAudioOutputStream(push_stream_callback)
        audio_cfg = speechsdk.audio.AudioOutputConfig(stream=push_stream)
        
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config, 
            audio_config=audio_cfg
        )
        
        ssml = self._create_ssml(text)
        result_future = synthesizer.speak_ssml_async(ssml)
        
        try:
            await asyncio.get_event_loop().run_in_executor(None, result_future.get)
            while True:
                chunk = await audio_queue.get()
                if chunk is None:
                    break
                yield chunk
        except Exception:
            stop_event.set()
            yield None
            
    def _create_ssml(self, text):
        # Popular Azure TTS voices:
        # English (US):
        #   - en-US-JennyNeural - Female, conversational
        #   - en-US-GuyNeural - Male, conversational
        #   - en-US-AriaNeural - Female, professional
        #   - en-US-DavisNeural - Male, professional
        #   - en-US-JasonNeural - Male, narration
        #   - en-US-SaraNeural - Female, casual
        #   - en-US-TonyNeural - Male, enthusiastic
        #   - en-US-NancyNeural - Female, warm
        # English (UK):
        #   - en-GB-SoniaNeural - Female, professional
        #   - en-GB-RyanNeural - Male, professional
        # English (Australia):
        #   - en-AU-NatashaNeural - Female, professional
        #   - en-AU-WilliamNeural - Male, professional
        voice = CONFIG["TTS_MODELS"]["AZURE_TTS"]["TTS_VOICE"]
        prosody = CONFIG["TTS_MODELS"]["AZURE_TTS"]["PROSODY"]
        return f"""
<speak version='1.0' xml:lang='en-US'>
    <voice name='{voice}'>
        <prosody rate='{prosody["rate"]}' pitch='{prosody["pitch"]}' volume='{prosody["volume"]}'>
            {text}
        </prosody>
    </voice>
</speak>
"""

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

async def azure_text_to_speech_processor(phrase_queue: asyncio.Queue,
                                           audio_queue: asyncio.Queue,
                                           stop_event: asyncio.Event):
    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=os.getenv("AZURE_SPEECH_KEY"),
            region=os.getenv("AZURE_SPEECH_REGION")
        )
        prosody = CONFIG["TTS_MODELS"]["AZURE_TTS"]["PROSODY"]
        # Popular Azure TTS voices:
        # English (US):
        #   - en-US-JennyNeural - Female, conversational
        #   - en-US-GuyNeural - Male, conversational
        #   - en-US-AriaNeural - Female, professional
        #   - en-US-DavisNeural - Male, professional
        #   - en-US-JasonNeural - Male, narration
        #   - en-US-SaraNeural - Female, casual
        #   - en-US-TonyNeural - Male, enthusiastic
        #   - en-US-NancyNeural - Female, warm
        # English (UK):
        #   - en-GB-SoniaNeural - Female, professional
        #   - en-GB-RyanNeural - Male, professional
        # English (Australia):
        #   - en-AU-NatashaNeural - Female, professional
        #   - en-AU-WilliamNeural - Male, professional
        voice = CONFIG["TTS_MODELS"]["AZURE_TTS"]["TTS_VOICE"]
        audio_format = getattr(
            speechsdk.SpeechSynthesisOutputFormat,
            CONFIG["TTS_MODELS"]["AZURE_TTS"]["AUDIO_FORMAT"]
        )
        speech_config.set_speech_synthesis_output_format(audio_format)

        while True:
            if stop_event.is_set():
                await audio_queue.put(None)
                return

            phrase = await phrase_queue.get()
            if phrase is None or phrase.strip() == "":
                await audio_queue.put(None)
                return

            try:
                ssml_phrase = f"""
<speak version='1.0' xml:lang='en-US'>
    <voice name='{voice}'>
        <prosody rate='{prosody["rate"]}' pitch='{prosody["pitch"]}' volume='{prosody["volume"]}'>
            {phrase}
        </prosody>
    </voice>
</speak>
"""
                push_stream_callback = PushAudioOutputStreamCallback(audio_queue, stop_event)
                push_stream = speechsdk.audio.PushAudioOutputStream(push_stream_callback)
                audio_cfg = speechsdk.audio.AudioOutputConfig(stream=push_stream)
                synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_cfg)
                result_future = synthesizer.speak_ssml_async(ssml_phrase)
                await asyncio.get_event_loop().run_in_executor(None, result_future.get)
            except Exception:
                await audio_queue.put(None)
                return

    except Exception:
        await audio_queue.put(None)
