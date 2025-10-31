# -*- coding: utf-8 -*-
import asyncio
import traceback
import sys
import pyaudio
from google import genai
from google.genai import types
from config import settings
from app.logs.loggers import setup_logger

logger = setup_logger("Gemini_Live_Service")

# Compatibility patch for Python < 3.11
if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup
    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup


class GeminiLiveAudioService:
    """
    Real-time audio streaming service for Gemini Live API.
    Captures microphone input (PCM), streams to Gemini, and plays AI responses.
    """

    def __init__(self):
        self.api_key = settings.GOOGLE_API_KEY
        self.client = genai.Client(api_key=self.api_key, http_options={"api_version": "v1alpha"})

        # Audio configurations
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.SEND_SAMPLE_RATE = 16000
        self.RECEIVE_SAMPLE_RATE = 24000
        self.CHUNK_SIZE = 1024
        self.model = "gemini-2.5-flash-native-audio-preview-09-2025"

        self.pya = pyaudio.PyAudio()
        self.CONFIG = types.LiveConnectConfig(
            system_instruction=types.Content(
                role="system",
                parts=[
                    types.Part(
                        text=(
                            "You are a helpful and friendly AI assistant.\n"
                            "Your default tone is helpful, engaging, and clear, with a touch of optimistic wit.\n"
                            "Anticipate user needs by clarifying ambiguous questions and always conclude your responses with an engaging follow-up question to keep the conversation flowing."
                            


                        )
                    )
                ],
            ),
            response_modalities=["AUDIO"],
        )

        self.audio_in_queue = None
        self.out_queue = None
        self.session = None
        self.audio_stream = None

    async def listen_audio(self):
        """🎙️ Capture microphone audio and send to Gemini in PCM format."""
        try:
            mic_info = self.pya.get_default_input_device_info()
            logger.info(f"🎤 Using microphone: {mic_info['name']}")

            self.audio_stream = await asyncio.to_thread(
                self.pya.open,
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.SEND_SAMPLE_RATE,
                input=True,
                input_device_index=mic_info["index"],
                frames_per_buffer=self.CHUNK_SIZE,
            )

            logger.info("🎧 Mic listening started...")
            kwargs = {"exception_on_overflow": False} if __debug__ else {}

            while True:
                data = await asyncio.to_thread(self.audio_stream.read, self.CHUNK_SIZE, **kwargs)
                await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})
        except Exception as e:
            logger.error(f"❌ listen_audio error: {e}")

    async def send_realtime(self):
        """🚀 Send microphone PCM audio to Gemini."""
        logger.info("🚀 Sending audio to Gemini...")
        while True:
            try:
                msg = await self.out_queue.get()
                await self.session.send_realtime_input(audio=msg)
            except Exception as e:
                logger.error(f"❌ send_realtime error: {e}")

    async def receive_audio(self):
        """🎧 Receive audio/text responses from Gemini."""
        logger.info("🔄 Receiving Gemini responses...")
        while True:
            try:
                turn = self.session.receive()
                async for response in turn:
                    if data := response.data:
                        self.audio_in_queue.put_nowait(data)
                    if text := response.text:
                        logger.info(f"🤖 Gemini says: {text.strip()}")
            except Exception as e:
                logger.error(f"❌ receive_audio error: {e}")

    async def play_audio(self):
        """🔉 Play Gemini’s audio responses."""
        try:
            stream = await asyncio.to_thread(
                self.pya.open,
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RECEIVE_SAMPLE_RATE,
                output=True,
            )
            logger.info("🔊 Playback started...")
            while True:
                bytestream = await self.audio_in_queue.get()
                await asyncio.to_thread(stream.write, bytestream)
        except Exception as e:
            logger.error(f"❌ play_audio error: {e}")

    async def run(self):
        """Starts full bidirectional audio loop (mic <-> Gemini <-> speaker)."""
        try:
            logger.info("🌐 Connecting to Gemini Live API...")
            async with (
                self.client.aio.live.connect(model=self.model, config=self.CONFIG) as session,
                asyncio.TaskGroup() as tg,
            ):
                logger.info("✅ Connected to Gemini Live API!")
                self.session = session
                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)

                tg.create_task(self.send_realtime())
                tg.create_task(self.listen_audio())
                tg.create_task(self.receive_audio())
                tg.create_task(self.play_audio())
        except asyncio.CancelledError:
            logger.warning("🛑 Audio loop cancelled")
        except asyncio.ExceptionGroup as eg:
            if self.audio_stream:
                self.audio_stream.close()
            logger.error("❌ ExceptionGroup caught:")
            traceback.print_exception(eg)
        except Exception as e:
            logger.error(f"❌ run() error: {e}")
