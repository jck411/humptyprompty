#!/usr/bin/env python3
import os
import sounddevice as sd
from dotenv import load_dotenv
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents

def main():
    # Load the Deepgram API key from .env
    load_dotenv()
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        raise ValueError("Missing DEEPGRAM_API_KEY in environment variables")
    
    # Initialize the Deepgram client
    deepgram = DeepgramClient(api_key)
    
    # Create a live transcription WebSocket connection (v1 interface)
    dg_connection = deepgram.listen.websocket.v("1")
    
    # Register event handlers with the proper signature
    dg_connection.on(
        LiveTranscriptionEvents.Open,
        lambda client, *args, **kwargs: print("Connection established.")
    )
    dg_connection.on(
        LiveTranscriptionEvents.Close,
        lambda client, *args, **kwargs: print("Connection closed.")
    )
    dg_connection.on(
        LiveTranscriptionEvents.Warning,
        lambda client, warning, **kwargs: print("Warning:", warning)
    )
    dg_connection.on(
        LiveTranscriptionEvents.Metadata,
        lambda client, metadata, **kwargs: print("Metadata:", metadata)
    )
    dg_connection.on(
        LiveTranscriptionEvents.Error,
        lambda client, error, **kwargs: print("Error:", error)
    )
    
    # Handler for transcript events: note the client is the first argument.
    def on_transcript(client, result, **kwargs):
        transcript = result.channel.alternatives[0].transcript
        if transcript:
            print("Transcript:", transcript)
    
    dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript)
    
    # Set transcription options (remove unsupported options like 'words')
    options = LiveOptions(
        model="nova-2",         # Choose "nova-2" or "nova-3" as desired
        smart_format=True,
        language="en-US",
        interim_results=True,
        encoding="linear16",
        sample_rate=16000,
        channels=1,
        endpointing=True,
        utterance_end_ms=1000
    )
    
    print("Starting live transcription... Press Enter to stop.")
    if not dg_connection.start(options):
        print("Failed to start the transcription connection.")
        return
    
    # Audio parameters
    CHUNK = 1024   # Number of audio samples per frame
    CHANNELS = 1   # Mono audio
    RATE = 16000   # 16kHz sampling rate

    # Callback function that sends captured audio to the Deepgram connection
    def audio_callback(indata, frames, time, status):
        if status:
            print("Sounddevice status:", status)
        try:
            # Convert numpy array to bytes and send
            dg_connection.send(indata.tobytes())
        except Exception as e:
            print("Error sending audio data:", e)
    
    # Open the sounddevice input stream with the callback
    stream = sd.InputStream(
        samplerate=RATE,
        channels=CHANNELS,
        blocksize=CHUNK,
        dtype='int16',
        callback=audio_callback
    )
    
    # Using a context manager to automatically open and close the stream
    with stream:
        input()  # Wait for the user to press Enter to stop the transcription
    
    # Clean up resources
    dg_connection.finish()
    print("Transcription stopped.")

if __name__ == "__main__":
    main()
