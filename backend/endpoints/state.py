# backend/endpoints/state.py
import asyncio
TTS_STOP_EVENT = asyncio.Event()
GEN_STOP_EVENT = asyncio.Event()