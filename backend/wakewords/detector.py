import os
import struct
import threading
import asyncio
import requests
from concurrent.futures import ThreadPoolExecutor
import pvporcupine
import pyaudio
from dotenv import load_dotenv
from backend.config.config import CONFIG

def get_keyword_file_paths() -> tuple[str, str]:
    """
    Returns the file paths of the wake word models.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    stop_keyword_path = os.path.join(base_dir, "stop-there_en_linux_v3_0_0.ppn")
    computer_keyword_path = os.path.join(base_dir, "computer_en_linux_v3_0_0.ppn")
    return stop_keyword_path, computer_keyword_path

class AsyncWakeWordDetector:
    """
    Non-blocking wake word detector that runs in a separate thread but
    handles audio processing in chunks without blocking the main thread.
    """
    def __init__(self):
        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.loop = asyncio.get_event_loop()
        self.audio_stream = None
        self.pa = None
        self.porcupine = None

    async def initialize(self):
        """Initialize the wake word detector without blocking the main thread"""
        try:
            # Load environment variables for API key
            load_dotenv()
            
            # Create porcupine instance in the executor to avoid blocking
            pv_access_key = os.environ.get('PICOVOICE_API_KEY')
            
            stop_keyword_path, computer_keyword_path = get_keyword_file_paths()
            
            def create_porcupine():
                return pvporcupine.create(
                    access_key=pv_access_key,
                    keyword_paths=[stop_keyword_path, computer_keyword_path],
                )
            
            # Create Porcupine in a non-blocking way
            self.porcupine = await self.loop.run_in_executor(self.executor, create_porcupine)
            
            # Initialize PyAudio
            def setup_audio():
                pa = pyaudio.PyAudio()
                audio_stream = pa.open(
                    rate=self.porcupine.sample_rate,
                    channels=1,
                    format=pyaudio.paInt16,
                    input=True,
                    frames_per_buffer=self.porcupine.frame_length
                )
                return pa, audio_stream
                
            self.pa, self.audio_stream = await self.loop.run_in_executor(self.executor, setup_audio)
            return True
        except Exception as e:
            print(f"[WakeWord] Error initializing wake word detector: {e}")
            return False

    async def process_audio_chunk(self):
        """Process a single audio chunk non-blockingly"""
        if not self.running or not self.audio_stream or not self.porcupine:
            return
            
        try:
            # Read audio chunk in executor to avoid blocking
            def read_audio():
                try:
                    return self.audio_stream.read(self.porcupine.frame_length, exception_on_overflow=False)
                except Exception as e:
                    print(f"[WakeWord] Error reading audio: {e}")
                    return None
                    
            pcm_data = await self.loop.run_in_executor(self.executor, read_audio)
            if pcm_data is None:
                return
                
            # Process audio with porcupine in executor
            def process_audio(pcm):
                # Convert bytes to PCM
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)
                # Process with porcupine
                return self.porcupine.process(pcm)
                
            keyword_index = await self.loop.run_in_executor(self.executor, process_audio, pcm_data)
            
            # Handle wake word detection
            if keyword_index == 0:
                print("[WakeWord] Detected 'stop there' -> stopping TTS and generation.")
                await self.make_api_request("http://localhost:8000/api/stop-tts")
                await self.make_api_request("http://localhost:8000/api/stop-generation")
            elif keyword_index == 1:
                print("[WakeWord] Detected 'computer' -> starting STT if paused.")
                await self.make_api_request("http://localhost:8000/api/start-stt")
                
        except Exception as e:
            print(f"[WakeWord] Error processing audio chunk: {e}")
            
    async def make_api_request(self, url):
        """Make an API request without blocking"""
        try:
            def do_request():
                try:
                    return requests.post(url)
                except Exception as e:
                    print(f"[WakeWord] Error calling {url}: {e}")
                    return None
                    
            await self.loop.run_in_executor(self.executor, do_request)
        except Exception as e:
            print(f"[WakeWord] Error making API request to {url}: {e}")

    async def run(self):
        """Run the wake word detector in a non-blocking way"""
        self.running = True
        while self.running:
            await self.process_audio_chunk()
            # Short sleep to prevent tight loop
            await asyncio.sleep(0.01)
            
    async def stop(self):
        """Stop the wake word detector"""
        self.running = False
        if self.audio_stream:
            def cleanup():
                try:
                    if self.audio_stream:
                        self.audio_stream.close()
                    if self.pa:
                        self.pa.terminate()
                    if self.porcupine:
                        self.porcupine.delete()
                except Exception as e:
                    print(f"[WakeWord] Error cleaning up: {e}")
            
            await self.loop.run_in_executor(self.executor, cleanup)
            self.audio_stream = None
            self.pa = None
            self.porcupine = None
        
        # Shutdown executor
        self.executor.shutdown(wait=False)
        print("[WakeWord] Detector stopped.")

# Global detector instance
detector = None

def listen_for_wake_words() -> None:
    """Original blocking function kept for compatibility"""
    try:
        load_dotenv()
        pv_access_key = os.environ.get('PICOVOICE_API_KEY')
        
        stop_keyword_path, computer_keyword_path = get_keyword_file_paths()
        print(f"[WakeWord] Loading keywords from {stop_keyword_path} and {computer_keyword_path}")
        
        porcupine = pvporcupine.create(
            access_key=pv_access_key,
            keyword_paths=[stop_keyword_path, computer_keyword_path],
        )

        pa = pyaudio.PyAudio()
        audio_stream = pa.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length
        )

        try:
            while True:
                pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
                keyword_index = porcupine.process(pcm)
                # If a wake word is detected, take action.
                if keyword_index == 0:
                    print("[WakeWord] Detected 'stop there' -> stopping TTS and generation.")
                    try:
                        requests.post("http://localhost:8000/api/stop-tts")
                        requests.post("http://localhost:8000/api/stop-generation")
                    except Exception as e:
                        print(f"[WakeWord] Error calling stop endpoints: {e}")
                elif keyword_index == 1:
                    print("[WakeWord] Detected 'computer' -> starting STT if paused.")
                    try:
                        requests.post("http://localhost:8000/api/start-stt")
                    except Exception as e:
                        print(f"[WakeWord] Error calling start-stt endpoint: {e}")
        except KeyboardInterrupt:
            print("[WakeWord] Stopping on KeyboardInterrupt.")
        finally:
            audio_stream.close()
            pa.terminate()
            porcupine.delete()
            print("[WakeWord] Exiting.")
    except Exception as e:
        print(f"[WakeWord] Error: {e}")

def start_wake_word_thread() -> None:
    """
    Starts the wake word detection logic in a daemon thread if enabled in configuration.
    """
    global detector
    
    if not CONFIG["GENERAL_AUDIO"]["WAKEWORD_ENABLED"]:
        print("[WakeWord] Wake word detection disabled in configuration.")
        return
        
    # Use the new non-blocking implementation
    async def start_detector():
        global detector
        detector = AsyncWakeWordDetector()
        success = await detector.initialize()
        if success:
            print("[WakeWord] Non-blocking wake word detector initialized successfully.")
            asyncio.create_task(detector.run())
        else:
            print("[WakeWord] Failed to initialize non-blocking wake word detector.")
            detector = None
    
    # Schedule the detector to start
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.create_task(start_detector())
    else:
        # Fallback to old blocking method if no event loop is running
        print("[WakeWord] No event loop running, falling back to blocking implementation.")
        thread = threading.Thread(target=listen_for_wake_words, daemon=True)
        thread.start()
        print("[WakeWord] Wake word detection thread started.")
