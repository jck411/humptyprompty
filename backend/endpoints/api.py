import logging
from fastapi import APIRouter, HTTPException, Response
from backend.config.config import CONFIG
from backend.endpoints.state import GEN_STOP_EVENT, TTS_STOP_EVENT

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

@router.options("/options")
async def openai_options():
    return Response(status_code=200)

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
    return {"status": "success", "message": "TTS stopped"}

@router.post("/stop-generation")
async def stop_generation():
    """
    Manually set the global GEN_STOP_EVENT.
    Any ongoing streaming text generation will stop soon after it checks the event.
    """
    GEN_STOP_EVENT.set()
    return {"detail": "Generation stop event triggered. Ongoing text generation will exit soon."}
