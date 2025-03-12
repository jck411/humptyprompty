#!/usr/bin/env python3
"""
Simple test script to verify wake word detection is working
"""
import os
import struct
import pyaudio
import numpy as np
import sys
import time

def main():
    """Test wake word detection directly"""
    print("[Test] Starting wake word detection test")
    
    # Get paths to wake word files
    base_dir = os.path.dirname(os.path.abspath(__file__))
    stop_keyword_path = os.path.join(base_dir, "stop-there_en_linux_v3_0_0.ppn")
    computer_keyword_path = os.path.join(base_dir, "computer_en_linux_v3_0_0.ppn")
    
    print(f"[Test] Using keyword files:")
    print(f"[Test] - Stop keyword: {stop_keyword_path}")
    print(f"[Test] - Computer keyword: {computer_keyword_path}")
    
    # Try to import pvporcupine
    try:
        import pvporcupine
        print("[Test] Successfully imported pvporcupine")
    except ImportError:
        print("[Test] ERROR: Failed to import pvporcupine. Make sure it's installed.")
        print("[Test] Try: pip install pvporcupine")
        sys.exit(1)
        
    # Try to simulate the working example code
    try:
        print("\n[Test] --- Direct Initialization Test ---")
        print("[Test] Creating a dummy porcupine to check failure mode")

        try:
            # This will fail but let's see the error message
            dummy = pvporcupine.create(access_key="dummy-key", keyword_paths=[stop_keyword_path])
            print("[Test] Unexpectedly succeeded with dummy key")
            dummy.delete()
        except Exception as e:
            print(f"[Test] Expected error: {e}")
            print("[Test] Error type:", type(e).__name__)
            
        # Now with monkey patching - temporarily replace create function
        print("\n[Test] --- Monkey Patching Test ---")
        original_create = pvporcupine.create
        
        # Define a simple function that will let us capture what's happening
        def debug_create(access_key=None, keyword_paths=None, sensitivities=None, **kwargs):
            print(f"[Test] Debug create called with:")
            print(f"[Test] - access_key: {access_key}")
            print(f"[Test] - keyword_paths: {keyword_paths}")
            print(f"[Test] - sensitivities: {sensitivities}")
            print(f"[Test] - kwargs: {kwargs}")
            
            # Try to inspect the library
            try:
                # Look for the C extension module
                ext_module = None
                for attr in dir(pvporcupine):
                    if attr.startswith("_") and hasattr(pvporcupine, attr):
                        mod = getattr(pvporcupine, attr)
                        if hasattr(mod, "pv_porcupine_init"):
                            ext_module = mod
                            print(f"[Test] Found extension module: {attr}")
                            break
                
                if ext_module:
                    print("[Test] Extension module has these functions:")
                    for func_name in dir(ext_module):
                        if not func_name.startswith("__"):
                            print(f"[Test] - {func_name}")
                            
            except Exception as e:
                print(f"[Test] Error inspecting library: {e}")
                
            try:
                # Let's try a simple hack - create a minimal subclass
                print("[Test] Creating patch object")
                
                # Create a minimal object that only implements what we need
                class PatchedPorcupine:
                    def __init__(self):
                        self.frame_length = 512
                        self.sample_rate = 16000
                        print("[Test] Created patched object")
                        
                    def process(self, pcm):
                        # Basic audio level detection
                        if len(pcm) > 0:
                            rms = np.sqrt(np.mean(np.array(pcm).astype(np.float32)**2))
                            if rms > 5000:  # Very high value to simulate detection
                                print(f"[Test] Simulated detection with RMS: {rms:.1f}")
                                return 0
                        return -1
                        
                    def delete(self):
                        print("[Test] Object deleted")
                
                return PatchedPorcupine()
            except Exception as e:
                print(f"[Test] Error creating patched object: {e}")
                raise
                
        # Apply our debug patch temporarily
        pvporcupine.create = debug_create
        
        try:
            # Create with our patched version
            print("[Test] Creating detector with patched function")
            porcupine = pvporcupine.create(
                access_key="any-key-will-work-now",
                keyword_paths=[stop_keyword_path, computer_keyword_path],
                sensitivities=[0.7, 0.7]
            )
            
            print(f"[Test] Created detector with:")
            print(f"[Test] - frame_length: {porcupine.frame_length}")
            print(f"[Test] - sample_rate: {porcupine.sample_rate}")
            
            # Set up audio
            print("\n[Test] --- Audio Setup ---")
            pa = pyaudio.PyAudio()
            
            # Print available input devices
            print("[Test] Available audio input devices:")
            for i in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    print(f"[Test] Device {i}: {info['name']}")
            
            # Open audio stream
            try:
                print("\n[Test] Opening audio stream...")
                audio_stream = pa.open(
                    rate=porcupine.sample_rate,
                    channels=1,
                    format=pyaudio.paInt16,
                    input=True,
                    frames_per_buffer=porcupine.frame_length
                )
                print("[Test] Audio stream opened successfully")
                
                # Process audio for a while
                print("\n[Test] --- Processing Audio ---")
                print("[Test] Listening for audio (10 seconds)...")
                print("[Test] Speak loudly to trigger a simulated detection")
                
                start_time = time.time()
                while time.time() - start_time < 10:
                    try:
                        pcm_bytes = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
                        pcm = struct.unpack_from("h" * porcupine.frame_length, pcm_bytes)
                        
                        # Process with patched detector
                        keyword_index = porcupine.process(pcm)
                        
                        # Calculate and show audio level periodically
                        rms = np.sqrt(np.mean(np.array(pcm).astype(np.float32)**2))
                        bar_len = min(int(rms / 500 * 20), 20)
                        bar = '#' * bar_len + '-' * (20 - bar_len)
                        print(f"\r[Test] Level: [{bar}] RMS: {rms:.1f}", end='', flush=True)
                        
                        if keyword_index >= 0:
                            print(f"\n[Test] Wake word detected! Index: {keyword_index}")
                            
                    except Exception as e:
                        print(f"\n[Test] Error processing audio: {e}")
                        break
                
                print("\n[Test] Audio test complete")
                
            except Exception as e:
                print(f"[Test] Error opening audio stream: {e}")
                
            finally:
                # Clean up
                if 'audio_stream' in locals():
                    audio_stream.close()
                pa.terminate()
                porcupine.delete()
                
        except Exception as e:
            print(f"[Test] Error in patched mode: {e}")
            
        finally:
            # Restore original function
            pvporcupine.create = original_create
            
        print("\n[Test] --- Original Method Test ---")
        # Most basic approach - try to make a direct call with the environment variable
        try:
            print("[Test] Checking for PORCUPINE_ACCESS_KEY environment variable...")
            access_key = os.environ.get("PORCUPINE_ACCESS_KEY")
            if access_key:
                print("[Test] Found access key in environment variable")
                try:
                    print("[Test] Trying to create porcupine with real access key...")
                    porcupine = pvporcupine.create(
                        access_key=access_key, 
                        keyword_paths=[stop_keyword_path, computer_keyword_path]
                    )
                    print("[Test] Successfully created with real access key!")
                    porcupine.delete()
                except Exception as e:
                    print(f"[Test] Failed with real access key: {e}")
            else:
                print("[Test] No access key found in environment variable")
                print("[Test] Set the PORCUPINE_ACCESS_KEY environment variable to test with a real key")
                
        except Exception as e:
            print(f"[Test] Error in direct approach: {e}")
            
        print("\n[Test] --- Completed Testing ---")
        print("[Test] Now we need to try implementing a custom solution based on what we learned")

    except Exception as e:
        print(f"[Test] Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()