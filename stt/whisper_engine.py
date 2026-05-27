import asyncio
from faster_whisper import WhisperModel
import numpy as np
import structlog
from typing import Optional

logger = structlog.get_logger()

class STTEngine:
    def __init__(self, model_size: str = "base.en", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model: Optional[WhisperModel] = None
        self._lock = asyncio.Lock()

    def load_model(self):
        logger.info("loading_whisper_model", model=self.model_size, device=self.device)
        self.model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)

    async def transcribe_chunk(self, audio_data: np.ndarray) -> str:
        """Transcribes a single chunk of audio."""
        if self.model is None:
            raise RuntimeError("Whisper model not loaded")
            
        async with self._lock:
            # transcription is CPU heavy, we run it in a thread pool to avoid blocking the event loop
            loop = asyncio.get_running_loop()
            segments, info = await loop.run_in_executor(
                None, 
                lambda: self.model.transcribe(audio_data, beam_size=5, vad_filter=True)
            )
            
            text = "".join([segment.text for segment in segments]).strip()
            return text

class STTWorker:
    def __init__(self, input_queue: asyncio.Queue, event_bus, engine: STTEngine):
        self.input_queue = input_queue
        self.event_bus = event_bus
        self.engine = engine
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._audio_buffer = []
        self._is_speaking = False

    async def _run(self):
        while self._running:
            try:
                audio_chunk = await self.input_queue.get()
                if self._is_speaking:
                    self._audio_buffer.append(audio_chunk)
                self.input_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("stt_worker_error", error=str(e))

    def start_collecting(self):
        self._is_speaking = True
        self._audio_buffer = []
        logger.debug("stt_started_collecting")

    async def stop_and_transcribe(self):
        self._is_speaking = False
        if not self._audio_buffer:
            return
            
        logger.info("stt_processing_buffer", chunks=len(self._audio_buffer))
        full_audio = np.concatenate(self._audio_buffer)
        self._audio_buffer = []
        
        text = await self.engine.transcribe_chunk(full_audio)
        if text:
            logger.info("stt_final_text", text=text)
            await self.event_bus.emit("STT_FINAL", text)

    def start(self):
        self._running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
