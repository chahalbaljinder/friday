import torch
import numpy as np
import asyncio
from typing import Optional
import structlog

logger = structlog.get_logger()

class VADWorker:
    def __init__(self, input_queue: asyncio.Queue, event_bus):
        self.input_queue = input_queue
        self.event_bus = event_bus
        self.model = None
        self.utils = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        # VAD Parameters
        self.threshold = 0.5
        self.sampling_rate = 16000
        self.min_silence_duration_ms = 300
        self.speech_pad_ms = 30

    async def load_model(self):
        logger.info("loading_silero_vad")
        # Silero VAD is loaded via torch.hub or local path
        # For local CPU execution, we ensure it's loaded efficiently
        self.model, self.utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=True
        )
        (self.get_speech_timestamps,
         self.save_audio,
         self.read_audio,
         self.VADIterator,
         self.collect_chunks) = self.utils

    async def _run(self):
        iterator = self.VADIterator(self.model, threshold=self.threshold, sampling_rate=self.sampling_rate)
        
        # Silero VAD expects chunks of 512, 1024 or 1536 samples
        VAD_FRAME_SIZE = 512
        audio_buffer = np.array([], dtype=np.float32)

        while self._running:
            try:
                audio_chunk = await self.input_queue.get()
                audio_buffer = np.concatenate([audio_buffer, audio_chunk])
                
                while len(audio_buffer) >= VAD_FRAME_SIZE:
                    # Process one frame
                    frame = audio_buffer[:VAD_FRAME_SIZE]
                    audio_buffer = audio_buffer[VAD_FRAME_SIZE:]
                    
                    speech_dict = iterator(frame, return_seconds=True)
                    
                    if speech_dict:
                        if "start" in speech_dict:
                            logger.info("user_started_speaking")
                            await self.event_bus.emit("USER_STARTED_SPEAKING")
                        if "end" in speech_dict:
                            logger.info("user_stopped_speaking")
                            await self.event_bus.emit("USER_STOPPED_SPEAKING")
                        
                self.input_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("vad_worker_error", error=str(e))

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
