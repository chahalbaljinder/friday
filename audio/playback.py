import asyncio
import numpy as np
import sounddevice as sd
import structlog
from typing import Optional

logger = structlog.get_logger()

class AudioPlayback:
    def __init__(self, sample_rate: int = 24000, channels: int = 1, playback_queue: Optional[asyncio.Queue] = None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.playback_queue = playback_queue or asyncio.Queue(maxsize=10)
        self.stream: Optional[sd.OutputStream] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def _crossfade(self, prev: np.ndarray, next: np.ndarray, fade_samples: int) -> np.ndarray:
        if fade_samples <= 0:
            return np.concatenate([prev, next])
            
        fade_out = np.linspace(1.0, 0.0, fade_samples)
        fade_in  = np.linspace(0.0, 1.0, fade_samples)
        
        # Apply fades to the overlapping parts
        prev_end = prev[-fade_samples:].copy()
        next_start = next[:fade_samples].copy()
        
        prev_end *= fade_out
        next_start *= fade_in
        
        combined = prev_end + next_start
        return np.concatenate([prev[:-fade_samples], combined, next[fade_samples:]])

    async def _run(self):
        logger.info("starting_playback_worker")
        
        # Open the output stream
        self.stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype='float32'
        )
        self.stream.start()
        
        while self._running:
            try:
                audio_segment = await self.playback_queue.get()
                
                # In a real implementation with crossfading, we'd buffer 
                # and overlap chunks. For Phase 1, we'll play them sequentially.
                
                # sounddevice.write is blocking, we should ideally use a callback 
                # or run in executor to keep the event loop snappy
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, lambda: self.stream.write(audio_segment))
                
                self.playback_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("playback_error", error=str(e))

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
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
