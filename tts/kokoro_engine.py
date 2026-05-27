import asyncio
from kokoro_onnx import Kokoro
import numpy as np
import structlog
from typing import Optional

logger = structlog.get_logger()

class TTSEngine:
    def __init__(self, model_path: str, voices_path: str):
        self.model_path = model_path
        self.voices_path = voices_path
        self.kokoro: Optional[Kokoro] = None

    def load_model(self):
        logger.info("loading_kokoro_tts", model=self.model_path)
        self.kokoro = Kokoro(self.model_path, self.voices_path)

    async def synthesize(self, text: str, voice: str = "af_sky") -> np.ndarray:
        """Synthesizes text to 24kHz audio."""
        if self.kokoro is None:
            raise RuntimeError("Kokoro model not loaded")
            
        loop = asyncio.get_running_loop()
        # Synthesis is CPU heavy, run in executor
        samples, sample_rate = await loop.run_in_executor(
            None,
            lambda: self.kokoro.create(text, voice=voice, speed=1.0, lang="en-us")
        )
        return samples

class TTSWorker:
    def __init__(self, event_bus, engine: TTSEngine, playback_queue: asyncio.Queue):
        self.event_bus = event_bus
        self.engine = engine
        self.playback_queue = playback_queue
        self._running = False

    async def handle_llm_chunk(self, chunk: str):
        """Processes a semantic chunk from the LLM and pushes to playback."""
        try:
            audio = await self.engine.synthesize(chunk)
            await self.playback_queue.put(audio)
            await self.event_bus.emit("TTS_CHUNK_READY")
        except Exception as e:
            logger.error("tts_synthesis_error", error=str(e))
