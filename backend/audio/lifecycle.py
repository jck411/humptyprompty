from backend.audio.singleton import PyAudioSingleton
from backend.audio.player import AudioPlayer
from backend.tts.processor import audio_player

def shutdown_audio(audio_player: AudioPlayer) -> None:
    """
    Gracefully close audio streams and terminate PyAudio.
    
    Args:
        audio_player (AudioPlayer): The audio player instance to shut down
    """
    audio_player.stop_stream()
    PyAudioSingleton.terminate()
