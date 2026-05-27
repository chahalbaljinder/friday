import asyncio
import signal
import structlog
from audio.capture import AudioCapture
from audio.playback import AudioPlayback
from events.bus import EventBus
from vad.silero import VADWorker
from stt.whisper_engine import STTEngine, STTWorker
from llm.ollama_client import OllamaClient, LLMWorker
from tts.kokoro_engine import TTSEngine, TTSWorker

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ]
)
logger = structlog.get_logger()

class VoiceAgent:
    def __init__(self):
        self.event_bus = EventBus()
        
        # Queues
        self.vad_queue = asyncio.Queue(maxsize=50)
        self.stt_queue = asyncio.Queue(maxsize=50)
        self.playback_queue = asyncio.Queue(maxsize=10)
        
        # Engines
        self.stt_engine = STTEngine()
        self.ollama_client = OllamaClient()
        self.tts_engine = TTSEngine(model_path="models/kokoro-v0_19.onnx", voices_path="models/voices.json")
        
        # Workers/Components
        self.capture = AudioCapture(output_queues=[self.vad_queue, self.stt_queue])
        self.playback = AudioPlayback(playback_queue=self.playback_queue)
        self.vad_worker = VADWorker(input_queue=self.vad_queue, event_bus=self.event_bus)
        self.stt_worker = STTWorker(input_queue=self.stt_queue, event_bus=self.event_bus, engine=self.stt_engine)
        self.llm_worker = LLMWorker(event_bus=self.event_bus, client=self.ollama_client)
        self.tts_worker = TTSWorker(event_bus=self.event_bus, engine=self.tts_engine, playback_queue=self.playback_queue)
        
        self._running = False
        self._llm_buffer = ""

    async def _setup(self):
        logger.info("loading_models")
        await self.vad_worker.load_model()
        self.stt_engine.load_model()
        self.tts_engine.load_model()
        
        # Subscribe to events
        self.event_bus.subscribe("USER_STARTED_SPEAKING", self._on_user_started_speaking)
        self.event_bus.subscribe("USER_STOPPED_SPEAKING", self._on_user_stopped_speaking)
        self.event_bus.subscribe("STT_FINAL", self._on_stt_final)
        self.event_bus.subscribe("LLM_TOKEN", self._on_llm_token)
        self.event_bus.subscribe("LLM_COMPLETE", self._on_llm_complete)

    async def _on_user_started_speaking(self, data):
        logger.info("user_speech_detected")
        self.stt_worker.start_collecting()

    async def _on_user_stopped_speaking(self, data):
        logger.info("user_speech_ended")
        await self.stt_worker.stop_and_transcribe()

    async def _on_stt_final(self, text):
        logger.info("processing_stt_result", text=text)
        await self.llm_worker.handle_user_message(text)

    async def _on_llm_token(self, token):
        self._llm_buffer += token
        # Simple semantic chunking: split on punctuation
        if any(p in token for p in ".?!;"):
            chunk = self._llm_buffer.strip()
            if chunk:
                await self.tts_worker.handle_llm_chunk(chunk)
                self._llm_buffer = ""

    async def _on_llm_complete(self, response):
        logger.info("llm_response_complete")
        # Final flush of buffer if any
        if self._llm_buffer.strip():
            await self.tts_worker.handle_llm_chunk(self._llm_buffer.strip())
            self._llm_buffer = ""

    async def start(self):
        await self._setup()
        self._running = True
        
        self.event_bus.start()
        self.capture.start()
        self.playback.start()
        self.vad_worker.start()
        self.stt_worker.start() # Ensure STT worker is running
        
        logger.info("agent_ready")
        
        while self._running:
            await asyncio.sleep(1)

    async def stop(self):
        logger.info("shutting_down")
        self._running = False
        self.capture.stop()
        await self.vad_worker.stop()
        await self.stt_worker.stop()
        await self.playback.stop()
        await self.event_bus.stop()

async def main():
    agent = VoiceAgent()
    
    try:
        await agent.start()
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("interrupted_by_user")
    except Exception as e:
        logger.error("fatal_error", error=str(e))
    finally:
        await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())
