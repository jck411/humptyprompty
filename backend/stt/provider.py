from backend.config.config import CONFIG
from backend.stt.config import STTConfig
from backend.stt.azure_stt import AzureSTTProvider
from backend.stt.deepgram_stt import DeepgramSTTProvider

def create_stt_instance():
    """Create a new STT provider instance based on current config"""
    provider = CONFIG["STT_MODELS"]["PROVIDER"].lower()
    if provider == "azure":
        settings = CONFIG["STT_MODELS"]["AZURE_STT"]
    elif provider == "deepgram":
        settings = CONFIG["STT_MODELS"]["DEEPGRAM_STT"]
    else:
        raise ValueError(f"Unsupported STT provider: {provider}")

    stt_config = STTConfig(
        provider=provider,
        settings=settings,
        enabled=CONFIG["GENERAL_AUDIO"]["STT_ENABLED"]
    )

    # Clean up existing instance if needed
    try:
        if hasattr(create_stt_instance, '_current_instance'):
            old_instance = create_stt_instance._current_instance
            if old_instance.is_listening:
                old_instance.pause_listening()
            del create_stt_instance._current_instance
    except Exception as e:
        print(f"Warning: Error cleaning up old STT instance: {e}")

    # Create and store new instance
    instance = None
    if provider == "azure":
        instance = AzureSTTProvider(stt_config)
    elif provider == "deepgram":
        instance = DeepgramSTTProvider(stt_config)
    
    # Store the new instance
    create_stt_instance._current_instance = instance
    return instance

# Create initial instance
stt_instance = create_stt_instance()