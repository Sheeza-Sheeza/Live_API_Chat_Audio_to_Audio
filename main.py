from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api import websocket_routes

app = FastAPI(title="Gemini Live Audio API")

# Mount static folder
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include WebSocket routes
app.include_router(websocket_routes.router)

@app.get("/")
async def serve_index():
    """Serve the frontend"""
    return FileResponse("static/index.html")

@app.get("/health-check")
def health_check():
    return {"status": " API is running!"}
