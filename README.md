⚙️ Requirements

Python 3.10+

(If you’re below Python 3.11, this code includes a small compatibility patch)

📦 Install dependencies
pip install fastapi uvicorn google-genai pyaudio websockets


If pyaudio fails to install on Windows, use:

pip install pipwin
pipwin install pyaudio

🔑 Setup Environment Variables

Create a .env file (or edit config.py) with your Google API Key:

GOOGLE_API_KEY=your_google_api_key_here


Or directly edit config.py:

class Settings:
    GOOGLE_API_KEY = "your_google_api_key_here"
settings = Settings()

 Run the FastAPI Server

From your project root:

uvicorn main:app --reload


You should see:

INFO:     Uvicorn running on http://127.0.0.1:8000

 Open the Frontend

Now open the test page in your browser:

http://127.0.0.1:8000/static/index.html


You’ll see:
 Gemini Live Audio Test

Click “🎙️ Start Session” to begin streaming

Speak into your mic — Gemini listens

You’ll hear Gemini’s AI voice response back!

Click “🛑 Stop” to end