import os
import struct
import threading
import asyncio
import requests
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import pyaudio
import wave
import time
from backend.config.config import CONFIG

# Import our custom Porcupine implementation
from backend.wakewords.custom_porcupine import create as create_porcupine

def get_keyword_file_paths() -> tuple[str, str]:
    """Get the paths to the wake word model files"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    stop_keyword_path = os.path.join(base_dir, "stop-there_en_linux_v3_0_0.ppn")
    computer_keyword_path = os.path.join(base_dir, "computer_en_linux_v3_0_0.ppn")
    
    # Print the paths for debugging
    print(f"[WakeWord] Using keyword files at:")
    print(f"[WakeWord] - Stop keyword: {stop_keyword_path}")
    print(f"[WakeWord] - Computer keyword: {computer_keyword_path}")
    
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
        self.debug_counter = 0  # Counter for occasional debug output
        self.log_interval = 50  # Log more frequently (every 50 frames)
        self.test_mode = False  # Set to True to test with constant detection
        self.device_name = "ALC3271 Analog"  # Target device name
        
        # Audio debugging
        self.debug_recording = False
        self.debug_frames = []
        self.max_debug_frames = 1000  # About 10 seconds at 16kHz

    async def initialize(self):
        """Initialize the wake word detector without blocking the main thread"""
        try:
            stop_keyword_path, computer_keyword_path = get_keyword_file_paths()
            
            def create_porcupine_instance():
                # Create our custom Porcupine instance with higher sensitivity
                return create_porcupine(
                    keyword_paths=[stop_keyword_path, computer_keyword_path],
                    sensitivities=[0.7, 0.7]  # Increased sensitivity for better detection
                )
            
            # Create Porcupine in a non-blocking way
            self.porcupine = await self.loop.run_in_executor(self.executor, create_porcupine_instance)
            print(f"[WakeWord] Detector initialized with sample rate: {self.porcupine.sample_rate} Hz, " 
                  f"frame length: {self.porcupine.frame_length} samples")
            
            # Initialize PyAudio
            def setup_audio():
                pa = pyaudio.PyAudio()
                
                # Print available audio input devices
                print("[WakeWord] Available audio input devices:")
                selected_device = None
                device_infos = {}
                
                for i in range(pa.get_device_count()):
                    device_info = pa.get_device_info_by_index(i)
                    device_infos[i] = device_info
                    
                    if device_info['maxInputChannels'] > 0:
                        # Print more detailed info about each input device
                        print(f"  Device {i}: {device_info['name']}")
                        print(f"    Max Input Channels: {device_info['maxInputChannels']}")
                        print(f"    Default Sample Rate: {device_info['defaultSampleRate']}")
                        print(f"    Input Latency: {device_info['defaultLowInputLatency']} to {device_info['defaultHighInputLatency']}")
                        
                        # Select device that contains our target name
                        if self.device_name in device_info['name']:
                            selected_device = i
                            print(f"[WakeWord] Selected device {i}: {device_info['name']}")
                
                if selected_device is None:
                    print(f"[WakeWord] Warning: Couldn't find device with name '{self.device_name}', using default")
                    # Try to use the default input device
                    default_device = pa.get_default_input_device_info()
                    selected_device = default_device['index'] if default_device else 0
                    print(f"[WakeWord] Selected default device {selected_device}: {pa.get_device_info_by_index(selected_device)['name']}")
                
                # Get the device information
                device_info = device_infos[selected_device]
                
                # Try supported sample rates in order of preference
                # The first one is the Porcupine default, then try device's default, then try standard values
                sample_rates_to_try = [
                    self.porcupine.sample_rate,
                    int(device_info['defaultSampleRate']),
                    44100,
                    48000,
                    8000,
                    22050
                ]
                
                # Remove duplicates while preserving order
                sample_rates_to_try = list(dict.fromkeys(sample_rates_to_try))
                
                print(f"[WakeWord] Trying sample rates: {sample_rates_to_try}")
                
                # Try to open stream with different sample rates
                audio_stream = None
                successful_rate = None
                
                for rate in sample_rates_to_try:
                    try:
                        print(f"[WakeWord] Trying to open audio with sample rate {rate}...")
                        audio_stream = pa.open(
                            rate=rate,
                            channels=1,
                            format=pyaudio.paInt16,
                            input=True,
                            frames_per_buffer=1024,  # Use a standard buffer size for now
                            input_device_index=selected_device
                        )
                        print(f"[WakeWord] Successfully opened audio with sample rate {rate}")
                        successful_rate = rate
                        break
                    except Exception as e:
                        print(f"[WakeWord] Failed to open audio with rate {rate}: {e}")
                
                if audio_stream is None:
                    print("[WakeWord] Could not open audio with any sample rate! Falling back to simulated mode.")
                    # Return a dummy stream
                    class DummyStream:
                        def read(self, frames, exception_on_overflow=None):
                            time.sleep(0.05)  # Simulate audio delay
                            # Return silent audio
                            return b'\x00' * (frames * 2)  # 2 bytes per sample
                        
                        def close(self):
                            pass
                    
                    return pa, DummyStream()
                    
                # Adjust frame buffer size to match Porcupine's expected frame length
                # This might not be exactly what Porcupine expects, but we'll handle resampling if needed
                frames_per_buffer = self.porcupine.frame_length
                if successful_rate != self.porcupine.sample_rate:
                    # Scale the buffer size proportionally to the sample rate
                    frames_per_buffer = int(self.porcupine.frame_length * (successful_rate / self.porcupine.sample_rate))
                    
                # Close the initial stream and open a new one with the correct buffer size
                audio_stream.close()
                
                try:
                    audio_stream = pa.open(
                        rate=successful_rate,
                        channels=1,
                        format=pyaudio.paInt16,
                        input=True,
                        frames_per_buffer=frames_per_buffer,
                        input_device_index=selected_device
                    )
                except Exception as e:
                    print(f"[WakeWord] Error opening final audio stream: {e}")
                    print("[WakeWord] Falling back to default configuration")
                    # Try one last time with basic settings
                    audio_stream = pa.open(
                        rate=successful_rate,
                        channels=1,
                        format=pyaudio.paInt16,
                        input=True,
                        input_device_index=selected_device
                    )
                
                print(f"[WakeWord] Audio stream opened successfully with:")
                print(f"  - Sample rate: {successful_rate} Hz")
                print(f"  - Format: paInt16")
                print(f"  - Frames per buffer: {frames_per_buffer}")
                print(f"  - Device: {device_info['name']}")
                
                # Save the actual sample rate we're using
                self.actual_sample_rate = successful_rate
                self.frames_per_buffer = frames_per_buffer
                
                # Record a short sample to make sure we can read audio
                print("[WakeWord] Reading test audio sample...")
                try:
                    test_frames = audio_stream.read(frames_per_buffer, exception_on_overflow=False)
                    print(f"[WakeWord] Successfully read {len(test_frames)} bytes of audio data")
                    
                    # Check if we're getting silent audio (all zeros)
                    if all(b == 0 for b in test_frames):
                        print("[WakeWord] WARNING: Audio input seems to be silent (all zeros)")
                    
                except Exception as e:
                    print(f"[WakeWord] Error reading test audio: {e}")
                
                return pa, audio_stream
                
            self.pa, self.audio_stream = await self.loop.run_in_executor(self.executor, setup_audio)
            
            # Start debug recording to help diagnose issues
            self.debug_recording = True
            print("[WakeWord] Started debug audio recording")
            
            self.running = True
            return True
        except Exception as e:
            print(f"[WakeWord] Error initializing wake word detector: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def process_audio_chunk(self):
        """Process a single audio chunk non-blockingly"""
        if not self.running or not self.audio_stream or not self.porcupine:
            return
            
        try:
            # Read audio chunk in executor to avoid blocking
            def read_audio():
                try:
                    frames = self.audio_stream.read(self.frames_per_buffer, exception_on_overflow=False)
                    return frames
                except Exception as e:
                    print(f"[WakeWord] Error reading audio: {e}")
                    return None
                    
            pcm_data = await self.loop.run_in_executor(self.executor, read_audio)
            if pcm_data is None:
                return
            
            # Save audio for debugging if enabled
            if self.debug_recording and len(self.debug_frames) < self.max_debug_frames:
                self.debug_frames.append(pcm_data)
                
                # If we've collected enough frames, save to file
                if len(self.debug_frames) >= self.max_debug_frames:
                    def save_debug_audio():
                        try:
                            filename = f"wakeword_debug_{int(time.time())}.wav"
                            print(f"[WakeWord] Saving debug audio to {filename}")
                            wf = wave.open(filename, 'wb')
                            wf.setnchannels(1)
                            wf.setsampwidth(2)  # 2 bytes per sample
                            wf.setframerate(self.actual_sample_rate)
                            wf.writeframes(b''.join(self.debug_frames))
                            wf.close()
                            print(f"[WakeWord] Saved debug audio to {filename}")
                            self.debug_frames.clear()  # Clear frames to allow another recording
                        except Exception as e:
                            print(f"[WakeWord] Error saving debug audio: {e}")
                    
                    await self.loop.run_in_executor(self.executor, save_debug_audio)
                
            # Process audio with porcupine in executor
            def process_audio(pcm):
                # Convert bytes to PCM
                pcm_values = struct.unpack_from("h" * (len(pcm) // 2), pcm)
                
                # Resample if needed
                if hasattr(self, 'actual_sample_rate') and self.actual_sample_rate != self.porcupine.sample_rate:
                    # Simple resampling - take or duplicate samples as needed
                    ratio = self.porcupine.sample_rate / self.actual_sample_rate
                    resampled = []
                    for i in range(self.porcupine.frame_length):
                        src_idx = int(i / ratio)
                        if src_idx < len(pcm_values):
                            resampled.append(pcm_values[src_idx])
                        else:
                            resampled.append(0)
                    pcm_values = resampled
                
                # Ensure we have exactly the number of samples Porcupine expects
                if len(pcm_values) > self.porcupine.frame_length:
                    pcm_values = pcm_values[:self.porcupine.frame_length]
                elif len(pcm_values) < self.porcupine.frame_length:
                    pcm_values = list(pcm_values) + [0] * (self.porcupine.frame_length - len(pcm_values))
                
                # Print audio level more frequently for debugging
                self.debug_counter += 1
                if self.debug_counter % self.log_interval == 0:
                    # Calculate RMS audio level
                    if pcm_values:
                        pcm_array = np.array(pcm_values).astype(np.float32)
                        rms = np.sqrt(np.mean(pcm_array**2))
                        max_val = np.max(np.abs(pcm_array))
                        print(f"[WakeWord] Audio levels - RMS: {rms:.1f}, Max: {max_val:.1f}")
                        
                        # Print a mini-visualization of audio level
                        level = int(min(rms / 500 * 20, 20))
                        bar = '#' * level + '-' * (20 - level)
                        print(f"[WakeWord] Level: [{bar}]")
                        
                        # If audio level is too low, warn user
                        if rms < 100:
                            print("[WakeWord] WARNING: Audio level is very low! Check if your microphone is muted.")
                        elif rms > 10000:
                            print("[WakeWord] WARNING: Audio level is very high! Your microphone might be too sensitive.")
                    
                # For test mode, occasionally return a detection
                if self.test_mode and self.debug_counter % 100 == 0:
                    print("[WakeWord] TEST MODE: Simulating keyword detection")
                    return 0 if self.debug_counter % 200 == 0 else 1
                
                # Normal mode - process with porcupine
                try:
                    result = self.porcupine.process(pcm_values)
                    if result != -1:
                        print(f"[WakeWord] DETECTION! Result: {result}")
                    return result
                except Exception as e:
                    print(f"[WakeWord] Error in porcupine processing: {e}")
                    return -1
                
            keyword_index = await self.loop.run_in_executor(self.executor, process_audio, pcm_data)
            
            # Handle wake word detection
            if keyword_index == 0:
                print("[WakeWord] Detected 'stop there' -> stopping TTS and generation.")
                await self.make_api_request("http://localhost:8000/api/stop-audio")
                await self.make_api_request("http://localhost:8000/api/stop-generation")
            elif keyword_index == 1:
                print("[WakeWord] Detected 'computer' -> starting STT if paused.")
                await self.make_api_request("http://localhost:8000/api/start-stt")
                
        except Exception as e:
            print(f"[WakeWord] Error processing audio chunk: {e}")
            import traceback
            traceback.print_exc()
            
    async def make_api_request(self, url):
        """Make an API request without blocking"""
        try:
            def do_request():
                try:
                    response = requests.post(url)
                    print(f"[WakeWord] API call to {url} - Status: {response.status_code}")
                    return response
                except Exception as e:
                    print(f"[WakeWord] Error calling {url}: {e}")
                    return None
                    
            await self.loop.run_in_executor(self.executor, do_request)
        except Exception as e:
            print(f"[WakeWord] Error making API request to {url}: {e}")

    async def run(self):
        """Run the wake word detector in a non-blocking way"""
        self.running = True
        print("[WakeWord] Starting audio processing - speak a wake word to test!")
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
        stop_keyword_path, computer_keyword_path = get_keyword_file_paths()
        
        # Create custom Porcupine instance
        porcupine = create_porcupine(
            keyword_paths=[stop_keyword_path, computer_keyword_path],
            sensitivities=[0.7, 0.7]  # Higher sensitivity for better detection
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
                if (keyword_index == 0):
                    print("[WakeWord] Detected 'stop there' -> stopping TTS and generation.")
                    try:
                        requests.post("http://localhost:8000/api/stop-audio")
                        requests.post("http://localhost:8000/api/stop-generation")
                    except Exception as e:
                        print(f"[WakeWord] Error calling stop endpoints: {e}")
                elif (keyword_index == 1):
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
