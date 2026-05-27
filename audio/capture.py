import asyncio
import numpy as np
import sounddevice as sd
import resampy
from typing import Optional, Callable, List
import structlog

logger = structlog.get_logger()

class AudioCapture:
    def __init__(
        self, 
        sample_rate: Optional[int] = None, 
        channels: int = 1, 
        chunk_size_ms: int = 32,
        output_queues: Optional[List[asyncio.Queue]] = None
    ):
        self.channels = channels
        self.chunk_size_ms = chunk_size_ms
        self.output_queues = output_queues or []
        
        # Determine device sample rate
        if sample_rate is None:
            self.device_info = sd.query_devices(kind='input')
            self.source_rate = int(self.device_info['default_samplerate'])
        else:
            self.source_rate = sample_rate
            
        self.target_rate = 16000
        self.samples_per_chunk = int(self.source_rate * (chunk_size_ms / 1000))
        
        self.stream: Optional[sd.InputStream] = None
        self._running = False

    def _audio_callback(self, indata, frames, time, status):
        if status:
            logger.warning("audio_capture_status", status=status)
        
        if self.output_queues and self._running:
            # Convert to float32 and normalize
            audio_data = indata.copy().flatten().astype(np.float32)
            
            # Resample to 16kHz if necessary
            if self.source_rate != self.target_rate:
                audio_resampled = resampy.resample(audio_data, self.source_rate, self.target_rate)
            else:
                audio_resampled = audio_data
                
            for queue in self.output_queues:
                try:
                    queue.put_nowait(audio_resampled)
                except asyncio.QueueFull:
                    pass

    def start(self):
        logger.info("starting_audio_capture", source_rate=self.source_rate, target_rate=self.target_rate)
        self._running = True
        self.stream = sd.InputStream(
            samplerate=self.source_rate,
            channels=self.channels,
            callback=self._audio_callback,
            blocksize=self.samples_per_chunk
        )
        self.stream.start()

    def stop(self):
        logger.info("stopping_audio_capture")
        self._running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
