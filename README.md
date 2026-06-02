# FRIDAY - A Local, Realtime AI Voice Agent

A high-performance, fully local, CPU-optimized conversational voice agent designed for realtime interaction on modest hardware.

## Overview

This project implements a production-grade, streaming-first voice agent that runs entirely on your local machine. It is specifically architected for CPU-first execution (tested on Intel i5-1334U with 16GB RAM) without requiring a dedicated GPU.

### Key Features
- **Fully Local:** Zero cloud dependency; all processing happens on-device.
- **Realtime & Low Latency:** Streaming-first architecture for immediate response.
- **Interruption-Safe:** Detects user speech while speaking and stops immediately (<300ms response).
- **Modular Design:** Decoupled components communicating via an asynchronous event bus.
- **Safety-First:** Permission-aware tool execution with sandboxing.
- **CPU Optimized:** Leverages efficient models like Qwen 2.5 3B, faster-whisper (int8), and Kokoro-82M.

## Core Tech Stack

| Layer | Technology |
| :--- | :--- |
| **VAD** | Silero VAD |
| **Wake Word** | openWakeWord |
| **STT** | faster-whisper (base.en, int8) |
| **LLM Runtime** | Ollama |
| **LLM Model** | Qwen 2.5 3B |
| **TTS** | Kokoro-82M (ONNX) |
| **Event System** | asyncio + Central Event Bus |
| **State Machine** | transitions / custom FSM |
| **Audio** | sounddevice, numpy, resampy |

## Architecture

The system follows a worker-based, streaming pipeline:

```text
Microphone → Audio Queue → VAD Worker → Wake Word → STT Worker → LLM Stream → Semantic Chunker → TTS Worker → Playback Queue → Speaker
```

### Core Principles
- **Streaming First:** Never wait for full transcriptions or responses. Everything is processed in chunks.
- **Async-First:** Built entirely on `asyncio` with bounded queues to prevent memory growth and provide backpressure.
- **State-Driven:** Explicit state management (IDLE, LISTENING, SPEAKING, etc.) ensures predictable transitions and re-arming of the wake word.

## Project Structure

```text
voice_agent/
├── audio/          # Capture, playback, and resampling
├── events/         # Central event bus and event definitions
├── llm/            # Ollama client and streaming logic
├── stt/            # Whisper engine and transcription workers
├── tts/            # Kokoro engine and synthesis streaming
├── vad/            # Silero VAD implementation
├── wakeword/       # Wake phrase detection
├── state/          # State machine and transition logic
├── tools/          # Tool registry and implementations
├── executor/       # Sandbox and permission management
├── memory/         # JSON/SQLite storage for persistence
├── metrics/        # Telemetry and performance monitoring
├── scripts/        # Utility scripts (e.g., model downloading)
└── main.py         # Application entry point
```

## Getting Started

### Prerequisites
1.  **Python 3.10+**
2.  **Ollama:** Install from [ollama.com](https://ollama.com) and pull the model:
    ```bash
    ollama pull qwen2.5:3b
    ```

### Installation
1.  Clone the repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Download required models (VAD, STT, TTS assets):
    ```bash
    python scripts/download_models.py
    ```

### Running the Agent
Start the main loop:
```bash
python main.py
```

## Performance Targets

| Metric | Target |
| :--- | :--- |
| **Wake Word Detection** | < 150ms |
| **LLM First Token** | < 700ms |
| **TTS Start Latency** | < 250ms |
| **Interruption Response** | < 300ms |
| **RAM Usage** | < 12GB |

## Roadmap
- **Phase 1 (Core):** Stable realtime voice loop and interruption handling. (Current)
- **Phase 2 (Streaming):** Enhanced semantic chunking and stability.
- **Phase 3 (Tools):** Safe local execution with structured tool calling.
- **Phase 4 (Memory):** Long-term continuity via SQLite and semantic recall.

## Security
All tool executions are subject to permission checks and run within a restricted sandbox. Direct execution of LLM output via shell is strictly prohibited.

