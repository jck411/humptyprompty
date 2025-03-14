#!/usr/bin/env python3
"""
Custom Porcupine implementation without audio level fallback.
This provides a compatible interface that requires a valid Porcupine instance.
A valid PORCUPINE_ACCESS_KEY must be set in the environment.

This script creates the Porcupine instance and then listens on the default
microphone. When a wake word is detected, it prints a message.
"""
import os
import logging
import struct
import time
import numpy as np
import pvporcupine
import pyaudio

def create(keyword_paths=None, sensitivities=None, model_path=None, library_path=None):
    """
    Create a Porcupine wake word detector.
    Requires the PORCUPINE_ACCESS_KEY environment variable to be set.
    """
    access_key = os.environ.get("PORCUPINE_ACCESS_KEY")
    if access_key:
        logging.info("[CustomPorcupine] Found access key in environment")
        try:
            porcupine = pvporcupine.create(
                access_key=access_key,
                keyword_paths=keyword_paths,
                sensitivities=sensitivities,
                model_path=model_path
            )
            logging.info("[CustomPorcupine] Successfully created real Porcupine instance!")
            return porcupine
        except Exception as e:
            logging.error(f"[CustomPorcupine] Error creating Porcupine with access key: {e}")
            raise e
    else:
        logging.error("[CustomPorcupine] Missing PORCUPINE_ACCESS_KEY environment variable. Cannot create Porcupine instance.")
        raise Exception("Missing PORCUPINE_ACCESS_KEY environment variable.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Replace these paths with the actual paths to your model files.
    keyword_paths = [
        "/home/jack/humptyprompty/wakeword_testing/computer_en_linux_v3_0_0.ppn",
        "/home/jack/humptyprompty/wakeword_testing/stop-there_en_linux_v3_0_0.ppn"
    ]
    sensitivities = [0.7, 0.7]
    
    try:
        detector = create(keyword_paths=keyword_paths, sensitivities=sensitivities)
        print(f"Created detector with frame_length: {detector.frame_length}, sample_rate: {detector.sample_rate}")
        
        # Initialize PyAudio
        pa = pyaudio.PyAudio()
        # Open the default audio input stream
        audio_stream = pa.open(
            rate=detector.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=detector.frame_length
        )
        
        print("Listening for wake words... Press Ctrl+C to exit")
        while True:
            # Read a frame of audio
            pcm_bytes = audio_stream.read(detector.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * detector.frame_length, pcm_bytes)
            
            # Optional: Calculate and display the RMS audio level for feedback
            rms = np.sqrt(np.mean(np.array(pcm, dtype=np.float32)**2))
            bar_len = min(int(rms / 500 * 20), 20)
            bar = '#' * bar_len + '-' * (20 - bar_len)
            print(f"\rAudio Level: [{bar}] RMS: {rms:5.0f}", end="", flush=True)
            
            # Process the audio frame for wake word detection
            keyword_index = detector.process(pcm)
            if keyword_index >= 0:
                # Derive the wake word name from the model filename (assumes filenames like "computer_...ppn")
                wake_word = os.path.basename(keyword_paths[keyword_index]).split('_')[0]
                print(f"\nDetected wake word: {wake_word}")
            
            # A tiny sleep to reduce CPU usage
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        try:
            audio_stream.close()
        except Exception:
            pass
        try:
            pa.terminate()
        except Exception:
            pass
        try:
            detector.delete()
        except Exception:
            pass
