import sys
from backend.audio.singleton import PyAudioSingleton
from backend.audio.player import AudioPlayer
from backend.tts.processor import audio_player
from backend.stt.provider import stt_instance

def shutdown_audio(audio_player: AudioPlayer) -> None:
    """
    Gracefully close audio streams and terminate PyAudio.
    
    Args:
        audio_player (AudioPlayer): The audio player instance to shut down
    """
    # Stop audio playback
    if audio_player and audio_player.is_playing:
        audio_player.stop_stream()

    # Stop the STT if it's running
    if stt_instance and stt_instance.is_listening:
        stt_instance.pause_listening()

    # Terminate all PyAudio instances
    singleton = PyAudioSingleton()
    for instance in singleton.get_instances():
        instance.terminate()

    # Force immediate exit
    sys.exit(0)
