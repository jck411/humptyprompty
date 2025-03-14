#!/usr/bin/env python3
"""
adjust_mic_volume.py

This script captures audio from the default microphone, calculates its RMS level,
and adjusts the system microphone capture volume using the 'amixer' command.
It aims to keep the mic input within a target RMS range by increasing or decreasing
the system capture volume.

Note:
  - This script relies on the ALSA utility 'amixer'. Ensure it is installed on your system.
  - It may require proper configuration for your audio hardware.
  - Adjustments are made in small percentage steps to avoid drastic changes.
"""

import pyaudio
import numpy as np
import struct
import subprocess
import time
import re

# Configuration
SAMPLE_RATE = 16000         # Sample rate for capturing audio
FRAME_LENGTH = 512          # Number of samples per frame
TARGET_RMS_LOW = 8000.0     # Lower bound for acceptable RMS
TARGET_RMS_HIGH = 12000.0   # Upper bound for acceptable RMS
ADJUST_STEP = 5             # Percentage step to adjust the volume
MIN_VOLUME = 0              # Minimum system volume percentage
MAX_VOLUME = 100            # Maximum system volume percentage

def calculate_rms(pcm):
    """Calculate the root mean square (RMS) of a PCM signal."""
    pcm_array = np.array(pcm, dtype=np.float32)
    rms = np.sqrt(np.mean(pcm_array ** 2))
    return rms

def get_current_mic_volume():
    """
    Retrieve the current microphone capture volume using 'amixer'.
    This function parses the output of 'amixer get Capture' to extract a percentage.
    """
    try:
        result = subprocess.run(["amixer", "get", "Capture"],
                                capture_output=True, text=True, check=True)
        output = result.stdout
        # Look for a percentage value in the output, e.g. "[50%]"
        matches = re.findall(r"\[(\d+)%\]", output)
        if matches:
            return int(matches[0])
    except Exception as e:
        print(f"Error reading mic volume: {e}")
    return None

def set_mic_volume(volume):
    """
    Set the system microphone capture volume using 'amixer'.
    Clamps the volume between MIN_VOLUME and MAX_VOLUME.
    """
    volume = max(MIN_VOLUME, min(volume, MAX_VOLUME))
    try:
        subprocess.run(["amixer", "sset", "Capture", f"{volume}%"],
                       check=True, capture_output=True, text=True)
        print(f"\nSet mic volume to {volume}%")
    except Exception as e:
        print(f"Error setting mic volume: {e}")

def main():
    pa = pyaudio.PyAudio()
    try:
        stream = pa.open(
            rate=SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=FRAME_LENGTH
        )
    except Exception as e:
        print(f"Error opening audio stream: {e}")
        pa.terminate()
        return

    print("Adjusting system microphone volume based on input levels. Press Ctrl+C to exit.")
    
    try:
        while True:
            # Read a frame of audio
            pcm_bytes = stream.read(FRAME_LENGTH, exception_on_overflow=False)
            pcm = struct.unpack("h" * FRAME_LENGTH, pcm_bytes)
            rms = calculate_rms(pcm)
            
            current_vol = get_current_mic_volume()
            if current_vol is None:
                print("Could not read current mic volume.")
                time.sleep(1)
                continue
            
            # Display current RMS and mic volume
            print(f"RMS: {rms:8.1f} | Current Mic Volume: {current_vol}%", end="\r", flush=True)
            
            # Adjust volume if RMS is outside the target range
            if rms < TARGET_RMS_LOW:
                new_vol = current_vol + ADJUST_STEP
                set_mic_volume(new_vol)
            elif rms > TARGET_RMS_HIGH:
                new_vol = current_vol - ADJUST_STEP
                set_mic_volume(new_vol)
            
            time.sleep(1)  # Adjust once per second
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        stream.close()
        pa.terminate()

if __name__ == "__main__":
    main()
