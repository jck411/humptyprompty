import os
import struct
import threading
import requests
import pvporcupine
import pyaudio
from dotenv import load_dotenv

def get_keyword_file_paths() -> tuple[str, str]:
    """
    Constructs the full paths to the Porcupine keyword files.
    Files are expected to be directly in the wakewords directory.
    """
    base_dir = os.path.dirname(__file__)
    stop_there_path = os.path.join(base_dir, "stop-there_en_linux_v3_0_0.ppn")
    computer_path = os.path.join(base_dir, "computer_en_linux_v3_0_0.ppn")
    return stop_there_path, computer_path

def listen_for_wake_words() -> None:
    """
    Continuously listens for wake words using Picovoice Porcupine.
    
    Two wake words are supported:
      - 'stop-there': triggers the stop endpoints for TTS and text generation.
      - 'computer': triggers the start of STT.
      
    The PPn files are loaded from the models/ subdirectory.
    """
    print("[WakeWord] Starting multi-keyword detection...")

    load_dotenv()
    access_key = os.getenv("PORCUPINE_ACCESS_KEY")
    if not access_key:
        raise ValueError("PORCUPINE_ACCESS_KEY not found in the environment.")

    # Get the full paths to the model files.
    stop_there_path, computer_path = get_keyword_file_paths()

    # Create the Porcupine instance.
    porcupine = pvporcupine.create(
        access_key=access_key,
        keyword_paths=[stop_there_path, computer_path]
    )

    # Initialize PyAudio.
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

def start_wake_word_thread() -> None:
    """
    Starts the wake word detection logic in a daemon thread.
    """
    thread = threading.Thread(target=listen_for_wake_words, daemon=True)
    thread.start()
    print("[WakeWord] Wake word detection thread started.")
