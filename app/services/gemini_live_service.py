# -*- coding: utf-8 -*-
import asyncio
import traceback
import sys
import pyaudio
from google import genai
from google.genai import types
from config import settings
from starlette.websockets import  WebSocketDisconnect
from fastapi import WebSocket
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
                            """You are a friendly and engaging AI voice assistant. Always respond only in Urdu language, no English. Speak naturally — like having a thoughtful, upbeat conversation. Be clear, warm, and easy to follow.  
                                Keep answers short and conversational, not lecture-like. If something is unclear, politely ask for clarification. End each response with a curious or friendly follow-up question  
                                to keep the chat flowing naturally."""
                            


                        )
                    )
                ],
            ),
            response_modalities=["AUDIO"],
            thinking_config=types.ThinkingConfig(
            thinking_budget=0,
            include_thoughts=False,
        ),
        )

        self.audio_in_queue = None
        self.out_queue = None
        self.session = None
        self.audio_stream = None

    # async def listen_audio(self):
    #     """ Capture microphone audio and send to Gemini in PCM format."""
    #     try:
    #         mic_info = self.pya.get_default_input_device_info()
    #         logger.info(f" Using microphone: {mic_info['name']}")

    #         self.audio_stream = await asyncio.to_thread(
    #             self.pya.open,
    #             format=self.FORMAT,
    #             channels=self.CHANNELS,
    #             rate=self.SEND_SAMPLE_RATE,
    #             input=True,
    #             input_device_index=mic_info["index"],
    #             frames_per_buffer=self.CHUNK_SIZE,
    #         )

    #         logger.info(" Mic listening started...")
    #         kwargs = {"exception_on_overflow": False} if __debug__ else {}

    #         while True:
    #             data = await asyncio.to_thread(self.audio_stream.read, self.CHUNK_SIZE, **kwargs)
    #             await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})
    #     except Exception as e:
    #         logger.error(f" listen_audio error: {e}")
    async def handle_client_input(self, websocket):
        """Receive PCM16 audio chunks from browser and push to Gemini."""
        logger.info("Receiving audio from browser client...")
        try:
            while True:
                data = await websocket.receive_bytes()
                await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})
        except WebSocketDisconnect:
            logger.info("Client disconnected")
        except Exception as e:
            if "CloseCode.NO_STATUS_RCVD" in str(e):
                logger.info(" Client stopped streaming — closing connection gracefully.")
            else:
                logger.error(f"handle_client_input error: {e}")


    async def send_realtime(self):
        """ Send microphone PCM audio to Gemini."""
        logger.info(" Sending audio to Gemini...")
        while True:
            try:
                msg = await self.out_queue.get()
                await self.session.send_realtime_input(audio=msg)
            except Exception as e:
                logger.error(f" send_realtime error: {e}")
    async def send_gemini_audio_to_client(self, websocket):
        """Send Gemini’s audio responses back to the browser client in real-time."""
        logger.info("Streaming Gemini audio back to browser client...")
        try:
            while True:
                data = await self.audio_in_queue.get()
                if not data:
                    continue

                # ✅ Check if the websocket is still connected before sending
                if websocket.client_state.name != "CONNECTED":
                    logger.info("WebSocket closed — stopping audio send loop.")
                    break

                try:
                    await websocket.send_bytes(data)
                except Exception as send_error:
                    logger.warning(f"Stopping send loop due to closed connection: {send_error}")
                    break

        except Exception as e:
            logger.error(f"send_gemini_audio_to_client error: {e}")
        finally:
            # ✅ Ensure socket is closed gracefully
            if websocket.client_state.name == "CONNECTED":
                await websocket.close()
            logger.info("Audio send loop ended.")



    async def receive_audio(self):
        """ Receive audio/text responses from Gemini."""
        logger.info(" Receiving Gemini responses...")
        while True:
            try:
                turn = self.session.receive()
                async for response in turn:
                    if data := response.data:
                        self.audio_in_queue.put_nowait(data)
                    #if text := response.text:
                        #logger.info(f" Gemini says: {text.strip()}")
            except Exception as e:
                logger.error(f" receive_audio error: {e}")

    # async def play_audio(self):
    #     """ Play Gemini’s audio responses."""
    #     try:
    #         stream = await asyncio.to_thread(
    #             self.pya.open,
    #             format=self.FORMAT,
    #             channels=self.CHANNELS,
    #             rate=self.RECEIVE_SAMPLE_RATE,
    #             output=True,
    #         )
    #         logger.info(" Playback started...")
    #         while True:
    #             bytestream = await self.audio_in_queue.get()
    #             await asyncio.to_thread(stream.write, bytestream)
    #     except Exception as e:
    #         logger.error(f" play_audio error: {e}")

    async def run(self, websocket=None):
        """Starts full bidirectional audio loop (browser mic <-> Gemini <-> browser speaker)."""
        try:
            logger.info("Connecting to Gemini Live API...")
            async with (
                self.client.aio.live.connect(model=self.model, config=self.CONFIG) as session,
                asyncio.TaskGroup() as tg,
            ):
                logger.info("Connected to Gemini Live API!")
                self.session = session
                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)

                tg.create_task(self.send_realtime())
                tg.create_task(self.receive_audio())

                #  Choose input source based on websocket
                if websocket:
                    tg.create_task(self.handle_client_input(websocket))
                    tg.create_task(self.send_gemini_audio_to_client(websocket))
                # else:
                #     tg.create_task(self.listen_audio())
                #     tg.create_task(self.play_audio())

        except asyncio.CancelledError:
            logger.warning("Audio loop cancelled")
        except asyncio.ExceptionGroup as eg:
            if self.audio_stream:
                self.audio_stream.close()
            logger.error("ExceptionGroup caught:")
            traceback.print_exception(eg)
        except Exception as e:
            logger.error(f"run() error: {e}")
