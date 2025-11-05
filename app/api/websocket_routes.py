from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.gemini_live_service import GeminiLiveAudioService
from app.logs.loggers import setup_logger
import asyncio

router = APIRouter()
logger = setup_logger("WebSocket_Router")

@router.websocket("/ws/live-audio")
async def live_audio_endpoint(websocket: WebSocket):
    """
    Real-time WebSocket endpoint for Gemini Live Audio.
    Browser streams mic input → Gemini (PCM) → Browser speaker.
    """
    await websocket.accept()
    logger.info("Client connected to Gemini Live WebSocket")

    service = GeminiLiveAudioService()

    try:
        await websocket.send_text("Gemini Live Audio session starting...")
        #  Pass websocket directly to the service
        await service.run(websocket)

    except WebSocketDisconnect:
        logger.warning("WebSocket client disconnected.")
    except Exception as e:
        logger.error(f"Error in WebSocket session: {e}")
        await websocket.send_text(f"Error: {str(e)}")
