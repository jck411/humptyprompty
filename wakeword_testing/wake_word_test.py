#!/usr/bin/env python3
import os
import sys
import struct
import time
import pyaudio
import numpy as np
from pathlib import Path

# Add the backend directory to the Python path so we can import the custom Porcupine implementation
sys.path.append(str(Path(__file__).parent.parent))
from wakeword_testing.custom_porcupine import create as create_porcupine

def get_keyword_file_paths():
    """Get the paths to the wake word model files"""
    base_dir = Path(__file__).parent.parent / "backend" / "wakewords"
    stop_keyword_path = str(base_dir / "/home/jack/humptyprompty/wakeword_testing/stop-there_en_linux_v3_0_0.ppn")
    computer_keyword_path = str(base_dir / "/home/jack/humptyprompty/wakeword_testing/computer_en_linux_v3_0_0.ppn")
    return stop_keyword_path, computer_keyword_path

def main():
    """Test wake word detection in terminal"""
    print("Starting wake word detection test...")
    print("This will listen for 'computer' and 'stop there' wake words")
    print("Press Ctrl+C to exit")
    
    try:
        stop_keyword_path, computer_keyword_path = get_keyword_file_paths()
        
        # Create Porcupine instance with higher sensitivity
        porcupine = create_porcupine(
            keyword_paths=[stop_keyword_path, computer_keyword_path],
            sensitivities=[0.7, 0.7]
        )
        
        print(f"\nInitialized detector with:")
        print(f"- Sample rate: {porcupine.sample_rate} Hz")
        print(f"- Frame length: {porcupine.frame_length} samples")
        
        # Initialize PyAudio
        pa = pyaudio.PyAudio()
        
        # List available input devices
        print("\nAvailable audio input devices:")
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                print(f"Device {i}: {info['name']}")
                print(f"  Max Input Channels: {info['maxInputChannels']}")
                print(f"  Default Sample Rate: {info['defaultSampleRate']}")
        
        # Open audio stream
        audio_stream = pa.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length
        )
        
        print("\nListening for wake words...")
        print("Say 'computer' or 'stop there'")
        
        # Main detection loop
        while True:
            # Read audio
            pcm_bytes = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm_bytes)
            
            # Calculate audio level for visual feedback
            rms = np.sqrt(np.mean(np.array(pcm).astype(np.float32)**2))
            bar_len = min(int(rms / 500 * 20), 20)
            bar = '#' * bar_len + '-' * (20 - bar_len)
            print(f"\rAudio Level: [{bar}] RMS: {rms:5.0f}", end='', flush=True)
            
            # Process audio for wake word detection
            keyword_index = porcupine.process(pcm)
            
            if keyword_index == 0:
                print("\nDetected 'stop there'!")
            elif keyword_index == 1:
                print("\nDetected 'computer'!")
            
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        if 'audio_stream' in locals():
            audio_stream.close()
        if 'pa' in locals():
            pa.terminate()
        if 'porcupine' in locals():
            porcupine.delete()

if __name__ == "__main__":
    main()