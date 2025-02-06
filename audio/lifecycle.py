from config import log_shutdown
from .singleton import PyAudioSingleton
from .player import AudioPlayer

def shutdown_audio(audio_player: AudioPlayer) -> None:
    """
    Gracefully close audio streams and terminate PyAudio.
    
    Args:
        audio_player (AudioPlayer): The audio player instance to shut down
    """
    log_shutdown("Shutting down audio subsystem...")
    audio_player.stop_stream()
    PyAudioSingleton.terminate()
    log_shutdown("Audio shutdown complete.")
