import logging
from fastapi import APIRouter, HTTPException, Response
from backend.config.config import CONFIG
from backend.stt.provider import stt_instance, create_stt_instance
from backend.stt.base import STTState
from backend.endpoints.state import GEN_STOP_EVENT, TTS_STOP_EVENT

logger = logging.getLogger(__name__)
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
    print(f"Starting STT - Current state: {stt_instance.state}, Is listening: {stt_instance.is_listening}, Enabled: {CONFIG['GENERAL_AUDIO']['STT_ENABLED']}")
    if not stt_instance.is_listening:
        await stt_instance.start_listening()
    return {"detail": "STT is now ON."}

@router.post("/pause-stt")
async def pause_stt_endpoint():
    """
    If STT is currently listening, this pauses it.
    Otherwise it does nothing.
    """
    print(f"Pausing STT - Current state: {stt_instance.state}, Is listening: {stt_instance.is_listening}, Enabled: {CONFIG['GENERAL_AUDIO']['STT_ENABLED']}")
    if stt_instance.is_listening:
        stt_instance.pause_listening()
    return {"detail": "STT is now OFF."}

@router.post("/toggle-stt-enabled")
async def toggle_stt_enabled():
    """
    Toggle the global STT enabled state.
    When disabled, no STT provider will process audio regardless of other settings.
    """
    try:
        # Update the global config
        new_state = not CONFIG["GENERAL_AUDIO"]["STT_ENABLED"]
        CONFIG["GENERAL_AUDIO"]["STT_ENABLED"] = new_state
        
        # Update the provider's config directly
        stt_instance.config.enabled = new_state
        
        # If we're enabling STT, reinitialize the recognizer
        if new_state:
            print("Reinitializing STT recognizer...")
            stt_instance.setup_recognizer()
            stt_instance._state = STTState.READY
        # If we're disabling STT, make sure to pause listening
        else:
            if stt_instance.is_listening:
                stt_instance.pause_listening()
            stt_instance._state = STTState.PAUSED
            
        return {
            "stt_enabled": new_state,
            "detail": "STT is now globally enabled." if new_state else "STT is now globally disabled."
        }
    except Exception as e:
        print(f"Error toggling STT: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to toggle STT enabled state: {str(e)}")

@router.post("/toggle-tts")
async def toggle_tts():
    try:
        current_status = CONFIG["GENERAL_AUDIO"]["TTS_ENABLED"]
        CONFIG["GENERAL_AUDIO"]["TTS_ENABLED"] = not current_status
        return {"tts_enabled": CONFIG["GENERAL_AUDIO"]["TTS_ENABLED"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle TTS: {str(e)}")

@router.post("/stop-tts")
async def stop_tts():
    logger.info("Stop TTS requested")
    TTS_STOP_EVENT.set()
    
    # Let the audio_player completion callback handle STT resumption
    # This ensures a single path for resuming STT and prevents race conditions
    return {"status": "success", "message": "TTS stopped"}

@router.post("/stop-generation")
async def stop_generation():
    """
    Manually set the global GEN_STOP_EVENT.
    Any ongoing streaming text generation will stop soon after it checks the event.
    """
    GEN_STOP_EVENT.set()
    return {"detail": "Generation stop event triggered. Ongoing text generation will exit soon."}

@router.post("/switch-stt-provider/{provider}")
async def switch_stt_provider(provider: str):
    """
    Switch the STT provider at runtime.
    Provider can be 'azure' or 'deepgram'.
    """
    global stt_instance
    try:
        provider = provider.lower()
        if provider not in ["azure", "deepgram"]:
            raise HTTPException(status_code=400, detail="Invalid provider. Must be 'azure' or 'deepgram'")

        # Update the global config
        CONFIG["STT_MODELS"]["PROVIDER"] = provider
        
        # Store the current listening state
        was_listening = stt_instance.is_listening
        
        # If currently listening, pause first
        if was_listening:
            stt_instance.pause_listening()
        
        # Create new instance with updated provider
        stt_instance = create_stt_instance()
        
        # Restore listening state if it was listening before
        if was_listening and CONFIG["GENERAL_AUDIO"]["STT_ENABLED"]:
            await stt_instance.start_listening()
            
        return {
            "detail": f"STT provider switched to {provider}",
            "provider": provider,
            "is_listening": stt_instance.is_listening,
            "is_enabled": CONFIG["GENERAL_AUDIO"]["STT_ENABLED"]
        }
    except Exception as e:
        print(f"Error switching STT provider: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to switch STT provider: {str(e)}")
