from fastapi import APIRouter, HTTPException, Response
from backend.config.config import CONFIG
from backend.stt.azure_stt import stt_instance, broadcast_stt_state
from backend.tts.processor import audio_player
from backend.endpoints.state import GEN_STOP_EVENT
from backend.endpoints.state import TTS_STOP_EVENT


router = APIRouter(prefix="/api")

@router.options("/options")
async def openai_options():
    return Response(status_code=200)

@router.post("/start-stt")
async def start_stt_endpoint():
    """
    If STT is currently paused, this starts listening again.
    Otherwise it does nothing.
    """
    if not stt_instance.is_listening:
        stt_instance.start_listening()
        await broadcast_stt_state()
    return {"detail": "STT is now ON."}

@router.post("/pause-stt")
async def pause_stt_endpoint():
    """
    If STT is currently listening, this pauses it.
    Otherwise it does nothing.
    """
    if stt_instance.is_listening:
        stt_instance.pause_listening()
        await broadcast_stt_state()
    return {"detail": "STT is now OFF."}

@router.post("/toggle-audio")
async def toggle_audio_playback():
    try:
        if audio_player.is_playing:
            audio_player.stop_stream()
            return {"audio_playing": False}
        else:
            audio_player.start_stream()
            return {"audio_playing": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle audio playback: {str(e)}")

@router.post("/toggle-tts")
async def toggle_tts():
    try:
        current_status = CONFIG["GENERAL_AUDIO"]["TTS_ENABLED"]
        CONFIG["GENERAL_AUDIO"]["TTS_ENABLED"] = not current_status
        await broadcast_stt_state()  # Optional: If TTS state affects is_listening
        return {"tts_enabled": CONFIG["GENERAL_AUDIO"]["TTS_ENABLED"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle TTS: {str(e)}")

@router.post("/stop-tts")
async def stop_tts():
    """
    Sets the TTS_STOP_EVENT which stops both TTS processing and audio playback
    (whether frontend or backend).
    """
    TTS_STOP_EVENT.set()
    return {
        "detail": "TTS and audio playback stopped",
        "tts_stopped": True
    }

@router.post("/stop-generation")
async def stop_generation():
    """
    Manually set the global GEN_STOP_EVENT.
    Any ongoing streaming text generation will stop soon after it checks the event.
    """

    GEN_STOP_EVENT.set()
    return {"detail": "Generation stop event triggered. Ongoing text generation will exit soon."}

@router.post("/toggle-playback-location")
async def toggle_playback_location():
    current = CONFIG["GENERAL_AUDIO"]["TTS_PLAYBACK_LOCATION"]
    # Toggle between frontend and backend
    CONFIG["GENERAL_AUDIO"]["TTS_PLAYBACK_LOCATION"] = "frontend" if current == "backend" else "backend"
    return {"playback_location": CONFIG["GENERAL_AUDIO"]["TTS_PLAYBACK_LOCATION"]}
