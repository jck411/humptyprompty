#!/usr/bin/env python3
from pydub import AudioSegment
import os
import sys

def convert_wav_to_format(input_file, output_file=None):
    """
    Convert WAV file to 24kHz mono 16-bit PCM format
    
    Args:
        input_file: Path to input WAV file
        output_file: Path to output file (if None, will use input_file name + "_converted.wav")
    """
    if not output_file:
        filename, ext = os.path.splitext(input_file)
        output_file = f"{filename}_converted.wav"
    
    # Load the audio file
    audio = AudioSegment.from_file(input_file)
    
    # Convert to mono if stereo
    if audio.channels > 1:
        audio = audio.set_channels(1)
    
    # Set sample rate to 24kHz
    audio = audio.set_frame_rate(24000)
    
    # Set sample width to 2 bytes (16-bit)
    audio = audio.set_sample_width(2)
    
    # Export the converted file
    audio.export(output_file, format="wav")
    
    print(f"Converted {input_file} to {output_file}")
    print(f"Format: 24kHz mono 16-bit PCM")
    
    return output_file

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_wav.py <input_wav_file> [output_file]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    convert_wav_to_format(input_file, output_file)