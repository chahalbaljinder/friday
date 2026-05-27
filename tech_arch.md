# Local Realtime Voice Agent Architecture
Version: v3 (Production-Oriented CPU-First Design)

---

# Goal

Build a:

- fully local
- CPU-only
- realtime
- interruption-safe
- permission-aware
- streaming-first
- conversational voice agent

Target Hardware:

- Intel i5-1334U
- 16GB RAM
- No GPU

Primary Design Goals:

- low latency
- modular architecture
- production-grade streaming
- safe local execution
- minimal RAM usage
- extensible tool system

---

# Core Stack

| Layer              | Technology              |
| ------------------ | ----------------------- |
| Audio Input        | sounddevice             |
| Audio Processing   | numpy                   |
| Audio Resampling   | librosa / resampy        |
| VAD                | Silero VAD              |
| Wake Word          | openWakeWord            |
| STT                | faster-whisper          |
| LLM Runtime        | Ollama                  |
| LLM Model          | Qwen 2.5 3B             |
| TTS                | Kokoro-82M              |
| Event System       | asyncio + event bus     |
| Async Queues       | asyncio.Queue (bounded) |
| State Machine      | transitions / custom FSM|
| CLI UX             | Rich + Typer            |
| Tool Schemas       | Pydantic                |
| Browser Automation | Playwright              |
| Memory Store       | JSON files (SQLite in Phase 4) |
| Embeddings         | sentence-transformers   |
| Logging            | structlog / logging     |
| Config             | pydantic-settings       |

---

# High-Level Architecture

```text
Microphone
   ↓
Audio Queue (bounded)
   ↓
VAD Worker
   ↓
Wake Word Detection
   ↓
Streaming STT
   ↓
Conversation Manager
   ↓
LLM Stream
   ↓
Semantic Chunker
   ↓
Streaming TTS
   ↓
Audio Playback Queue (bounded)
   ↓
Speaker
```

---

# Core Architectural Principles

## 1. Streaming First

NEVER wait for:

- full transcription
- full LLM response
- full TTS generation

The system must continuously stream.

Correct pipeline:

```text
STT Stream
   ↓
LLM Token Stream
   ↓
Semantic Chunking
   ↓
Incremental TTS (sentence-by-sentence)
   ↓
Audio Playback
```

---

## 2. Interruption First

Realtime agents MUST support interruption.

If user speaks:

```python
stop_tts()
cancel_llm()
flush_queues()
restart_stt()
```

Interruption latency target:

```text
< 300ms
```

---

## 3. Async-First Design

DO NOT use heavy thread orchestration.

Use:

- asyncio
- bounded queues
- async workers
- cancellation-aware tasks

---

# Recommended Runtime Architecture

```text
Main Event Loop
   ↓
Async Queues (bounded)
   ↓
Dedicated Async Workers
```

## Queue Definitions

All queues MUST be bounded to prevent memory growth.

```python
audio_input_queue  = asyncio.Queue(maxsize=50)   # ~1s of 20ms frames
vad_queue          = asyncio.Queue(maxsize=50)
stt_queue          = asyncio.Queue(maxsize=10)
llm_queue          = asyncio.Queue(maxsize=100)  # token buffer
tts_queue          = asyncio.Queue(maxsize=20)   # semantic chunks
playback_queue     = asyncio.Queue(maxsize=10)   # audio segments
event_queue        = asyncio.Queue(maxsize=200)
```

## Backpressure Policy

When a queue is full, the upstream producer MUST apply backpressure.

DO NOT silently drop frames unless the pipeline is in INTERRUPTED state.

Recommended pattern:

```python
try:
    queue.put_nowait(item)
except asyncio.QueueFull:
    if state != State.INTERRUPTED:
        await asyncio.sleep(0.005)  # yield briefly
        await queue.put(item)       # blocking put with backpressure
    # else: drop frame — interruption in progress
```

---

# Audio Resampling

CRITICAL: All components expect 16kHz mono PCM.

| Component       | Expected Sample Rate |
| --------------- | -------------------- |
| Silero VAD      | 16000 Hz             |
| faster-whisper  | 16000 Hz             |
| Kokoro-82M TTS  | 24000 Hz (output)    |
| sounddevice     | system default (varies) |

## Resampling Rules

- Capture audio at the system default sample rate via sounddevice.
- Immediately resample to 16000 Hz before passing to VAD or STT.
- TTS output is at 24000 Hz — feed directly to playback without resampling.
- All internal audio buffers use float32 normalized to [-1.0, 1.0].

```python
import resampy
import numpy as np

def resample_to_16k(audio: np.ndarray, source_rate: int) -> np.ndarray:
    if source_rate == 16000:
        return audio
    return resampy.resample(audio, source_rate, 16000)
```

---

# Worker Architecture

## Audio Worker

Responsibilities:

- microphone capture
- PCM buffering
- frame chunking
- audio normalization
- resample to 16kHz immediately after capture

Chunk size recommendation:

```text
20ms–40ms at 16kHz = 320–640 samples
```

---

## VAD Worker

Use Silero VAD.

Responsibilities:

- detect speech
- detect silence
- reduce STT load
- enable interruption detection

Input must be 16kHz mono float32.

---

## Wake Word Worker

Use openWakeWord.

Responsibilities:

- passive listening
- wake phrase detection
- low CPU operation

Rules:

```text
Only run wake word in IDLE state.
After conversation ends, transition back to IDLE.
Wake word worker automatically re-arms on IDLE entry.
```

Re-arm pattern:

```python
async def on_enter_idle(self):
    await self.wake_word_worker.rearm()
```

---

## STT Worker

Use faster-whisper.

Recommended model:

```python
WhisperModel(
    "base.en",
    device="cpu",
    compute_type="int8"
)
```

Responsibilities:

- streaming transcription
- partial transcription
- incremental updates

Important:

- use chunked transcription
- avoid full audio buffering
- input must be 16kHz mono float32

---

# LLM Runtime

Use:

- Ollama
- Qwen 2.5 3B

Command:

```bash
ollama run qwen2.5:3b
```

Future benchmark candidates:

- Qwen 2.5 1.5B
- Phi-3 Mini
- Gemma 3 1B
- SmolLM2

Important Metrics:

- first token latency
- tokens/sec
- RAM usage
- interruption recovery speed

## Context Window Management

The LLM has a limited context window. The conversation history passed to Ollama MUST be trimmed on every turn.

Strategy:

- Always keep the system prompt.
- Keep the last N turns of conversation (default: 10 turns).
- If total token estimate exceeds threshold, drop oldest turns first.
- Never drop the most recent user message.

```python
MAX_HISTORY_TURNS = 10
MAX_TOKENS_ESTIMATE = 2048  # conservative for 3B model

def trim_history(history: list[dict]) -> list[dict]:
    """Keep system prompt + last N turns within token budget."""
    system = [m for m in history if m["role"] == "system"]
    turns = [m for m in history if m["role"] != "system"]
    trimmed = turns[-MAX_HISTORY_TURNS * 2:]  # each turn = user + assistant
    return system + trimmed
```

Token estimation:

```python
def estimate_tokens(messages: list[dict]) -> int:
    # Rough estimate: 1 token ≈ 4 chars
    total_chars = sum(len(m["content"]) for m in messages)
    return total_chars // 4
```

---

# Semantic Chunking

DO NOT stream:

```text
token → TTS
```

Use semantic chunk buffering.

Flush chunk when:

- punctuation detected (`. ? ! , ;`)
- phrase boundary detected
- timeout reached
- word threshold exceeded

Recommended settings:

```text
8–25 words per chunk
300ms–600ms timeout
```

Example:

```python
if punctuation_detected or word_count >= MAX_WORDS or timeout_reached:
    flush_chunk()
```

---

# Streaming TTS

Use Kokoro-82M.

## How Incremental Synthesis Works

Kokoro-82M does NOT support true token-level streaming.
Use sentence-level (semantic chunk) incremental synthesis instead.

Correct pattern:

```text
Semantic Chunk (sentence)
   ↓
Kokoro synthesize(chunk) → audio segment (float32, 24kHz)
   ↓
Push to playback_queue
   ↓
Playback worker crossfades and plays
```

DO NOT:
- Wait for full LLM response before synthesizing.
- Generate one large WAV file and play it.
- Call Kokoro per token.

DO:
- Keep Kokoro model permanently loaded in memory.
- Synthesize each semantic chunk as it arrives.
- Push audio segments to playback_queue immediately.

## Playback Requirements

- crossfade chunks to avoid audio clicks
- crossfade duration: 10ms–40ms
- maintain consistent voice across chunks
- avoid WAV file generation; work with raw float32 arrays

```python
def crossfade(prev: np.ndarray, next: np.ndarray, fade_samples: int) -> np.ndarray:
    fade_out = np.linspace(1.0, 0.0, fade_samples)
    fade_in  = np.linspace(0.0, 1.0, fade_samples)
    prev[-fade_samples:] *= fade_out
    next[:fade_samples]  *= fade_in
    return np.concatenate([prev[:-fade_samples], prev[-fade_samples:] + next[:fade_samples], next[fade_samples:]])
```

---

# State Machine Architecture

Realtime agents MUST use explicit states.

Recommended states:

```text
IDLE
LISTENING
TRANSCRIBING
THINKING
SPEAKING
INTERRUPTED
EXECUTING_TOOL
WAITING_APPROVAL
ERROR
SHUTDOWN
```

## State Transition Rules

| From         | To             | Trigger                        |
| ------------ | -------------- | ------------------------------ |
| IDLE         | LISTENING      | WAKE_WORD_DETECTED             |
| LISTENING    | TRANSCRIBING   | USER_STOPPED_SPEAKING          |
| TRANSCRIBING | THINKING       | STT_FINAL                      |
| THINKING     | SPEAKING       | LLM_COMPLETE or first TTS chunk|
| SPEAKING     | INTERRUPTED    | USER_STARTED_SPEAKING          |
| INTERRUPTED  | LISTENING      | flush complete                 |
| SPEAKING     | IDLE           | TTS_FINISHED                   |
| THINKING     | EXECUTING_TOOL | TOOL_CALL_DETECTED             |
| EXECUTING_TOOL | WAITING_APPROVAL | ADMIN_ACTION_REQUESTED      |
| WAITING_APPROVAL | EXECUTING_TOOL | USER_APPROVED                |
| ANY          | ERROR          | unrecoverable exception        |
| ANY          | SHUTDOWN       | shutdown signal                |

## Wake Word Re-Arming

After every conversation, the agent MUST return to IDLE and re-arm the wake word detector.

```python
async def on_enter_idle(self):
    await wake_word_worker.rearm()
    await flush_all_queues()
```

Benefits:

- prevents race conditions
- prevents overlapping audio
- improves debugging
- simplifies interruption handling

---

# Central Event Bus

All modules communicate through events.

DO NOT tightly couple modules.

Recommended events:

```text
USER_STARTED_SPEAKING
USER_STOPPED_SPEAKING
WAKE_WORD_DETECTED
STT_PARTIAL
STT_FINAL
LLM_TOKEN
LLM_COMPLETE
TTS_STARTED
TTS_CHUNK_READY
TTS_FINISHED
TOOL_EXECUTED
INTERRUPTION_DETECTED
ERROR_EVENT
CONVERSATION_ENDED
```

Architecture:

```text
Workers
   ↓
Event Bus
   ↓
Subscribers
```

---

# Cancellation Architecture

Every long-running task MUST support cancellation.

Critical components:

- STT
- LLM stream
- TTS generation
- audio playback
- tool execution

Pattern:

```python
if cancel_event.is_set():
    cleanup()
    return
```

---

# Tool Calling Architecture

```text
LLM
 ↓
Intent Parser
 ↓
Structured Tool Call
 ↓
Tool Registry
 ↓
Permission Manager
 ↓
Sandbox Executor
 ↓
Operating System
```

---

# CRITICAL SECURITY RULE

NEVER:

```python
os.system(llm_output)
```

LLM output must NEVER directly execute shell commands.

ALL actions must go through:

- schema validation
- permission checks
- sandbox execution

---

# Structured Tool Calling

Use strict JSON schemas.

Example:

```json
{
  "tool": "open_file",
  "args": {
    "path": "notes.txt"
  }
}
```

Validation:

- Pydantic
- strict typing
- explicit allowed arguments

---

# Permission System

## Permission Levels

| Level     | Example              |
| ----------| -------------------- |
| SAFE      | read files           |
| USER      | open applications    |
| SENSITIVE | modify files         |
| ADMIN     | install software     |
| DANGEROUS | blocked permanently  |

---

# Approval Flow

Example:

```text
⚠ ADMIN ACTION REQUESTED

Command:
winget install docker

Approve? [y/n]
```

---

# Safe Sandboxed Directories

Allowed:

```text
Documents/
Downloads/
Desktop/
Projects/
```

Restricted:

```text
System32/
Windows/
Registry/
Program Files/
```

---

# Sandbox Execution

Recommended:

- subprocess with restrictions
- timeouts
- command allowlists
- resource limits

Never allow:

- unrestricted shell access
- registry edits
- arbitrary system execution

---

# Memory Architecture

## Memory Layers

```text
Short-Term Memory
   ↓
Session Memory
   ↓
Long-Term Memory
   ↓
Semantic Recall
```

---

## Short-Term Memory

Purpose:

- maintain conversational continuity
- recent context window

Store:

- last few exchanges
- active tasks
- temporary references

Trim strategy: see Context Window Management above.

---

## Session Memory

Purpose:

- persist current session

Examples:

- user preferences
- current workflows
- active files

---

## Long-Term Memory

Use JSON file dumps for Phase 1–3. Migrate to SQLite in Phase 4.

Store:

- user preferences
- recurring tasks
- semantic summaries

## JSON Store Design

All reads and writes go through a single `MemoryStore` interface.
This ensures the swap to SQLite in Phase 4 requires zero changes outside `memory/`.

```python
class MemoryStore:
    def __init__(self, path: str = "memory/store.json"):
        self.path = Path(path)
        self._data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {"preferences": {}, "tasks": [], "summaries": []}

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        tmp.replace(self.path)  # atomic rename — prevents corruption on crash

    def get(self, key: str):
        return self._data.get(key)

    def set(self, key: str, value) -> None:
        self._data[key] = value
        self.save()
```

Rules:

- Always write via atomic rename (write to `.tmp`, then `replace`) — prevents corrupt files on crash.
- Load once at startup; keep in memory during session.
- Call `save()` after every mutation.
- Do NOT scatter raw `json.dumps` calls across the codebase — always go through `MemoryStore`.

---

## Semantic Recall

Future upgrade:

- embedding search
- vector retrieval
- episodic memory

Suggested models:

- all-MiniLM-L6-v2
- bge-small-en

---

# Observability & Metrics

MUST log:

- STT latency
- first token latency
- tokens/sec
- TTS latency
- interruption latency
- queue sizes (monitor for saturation)
- CPU usage
- memory usage

Use:

- Rich dashboards
- structured logging
- rotating logs

Example metrics:

```text
STT_LATENCY=142ms
LLM_FIRST_TOKEN=310ms
TTS_START=120ms
INTERRUPTION=180ms
QUEUE[tts_queue]=3/20
QUEUE[playback_queue]=1/10
```

---

# Error Recovery

System MUST recover gracefully.

Examples:

## TTS Failure

```python
restart_tts_worker()
```

## LLM Timeout

```python
cancel_generation()
fallback_response()
```

## Audio Failure

```python
reinitialize_audio_device()
```

## Queue Saturation

```python
if queue.full():
    log_warning("queue saturated", queue_name=name)
    # apply backpressure upstream, do not crash
```

---

# Recommended Folder Structure

```text
voice_agent/
│
├── audio/
│   ├── capture.py
│   ├── playback.py
│   ├── processing.py
│   └── resampling.py        # NEW: handles all sample rate conversion
│
├── vad/
│   └── silero.py
│
├── wakeword/
│   └── detector.py          # includes rearm() method
│
├── stt/
│   ├── whisper_engine.py
│   └── streaming.py
│
├── llm/
│   ├── ollama_client.py
│   ├── prompts.py
│   ├── streaming.py
│   └── context.py           # NEW: context window trimming
│
├── tts/
│   ├── kokoro_engine.py
│   └── streaming.py         # sentence-level incremental synthesis
│
├── tools/
│   ├── registry.py
│   ├── schemas.py
│   └── implementations/
│
├── executor/
│   ├── sandbox.py
│   ├── permissions.py
│   └── approvals.py
│
├── memory/
│   ├── store.py             # MemoryStore interface (JSON now, SQLite in Phase 4)
│   ├── store.json           # runtime data file
│   ├── session.py
│   └── embeddings.py        # Phase 4
│
├── events/
│   ├── bus.py
│   └── events.py
│
├── state/
│   └── machine.py           # includes wake word re-arm on IDLE entry
│
├── metrics/
│   └── telemetry.py
│
├── config/
│   └── settings.py
│
├── main.py
└── requirements.txt
```

---

# Recommended System Prompt

```text
You are a realtime conversational voice assistant.

Rules:
- Speak naturally
- Keep responses concise
- Avoid markdown
- Avoid long monologues
- Respond conversationally
- Prioritize realtime interaction
- If interrupted, stop speaking immediately
```

---

# Development Roadmap

## Phase 1 — Core Voice Loop

Build:

- microphone input
- audio resampling (16kHz pipeline)
- VAD
- STT
- LLM
- TTS (sentence-level incremental)
- interruption handling
- bounded queues with backpressure

NO tools yet.

Goal:

```text
Stable realtime conversation
```

---

## Phase 2 — Streaming Stability

Add:

- semantic chunking
- context window trimming
- cancellation
- event bus
- state machine with wake word re-arming
- queue saturation monitoring

Goal:

```text
Low-latency stable streaming
```

---

## Phase 3 — Tool System

Add:

- structured tool calling
- permissions
- sandboxing
- approvals

Goal:

```text
Safe local agent execution
```

---

## Phase 4 — Memory

Add:

- migrate MemoryStore from JSON to SQLite
- session persistence
- semantic memory
- embeddings
- retrieval

Migration is a single script: load `store.json`, insert into SQLite tables.
No other code changes required if `MemoryStore` interface was respected.

Goal:

```text
Long-term conversational continuity
```

---

# Performance Targets

| Metric                    | Target         |
| ------------------------- | -------------- |
| Wake Word Detection       | < 150ms        |
| STT Partial Latency       | < 300ms        |
| LLM First Token           | < 700ms        |
| TTS Start Latency         | < 250ms        |
| Interruption Response     | < 300ms        |
| RAM Usage                 | < 12GB         |
| CPU Usage                 | sustainable    |

---

# Core Engineering Principles

- streaming-first
- interruption-first
- async-first
- safety-first
- CPU optimized
- modular design
- observable systems
- explicit state management
- schema-driven tools
- cancellation-aware execution
- bounded queues everywhere
- backpressure over dropping

---

# Final Philosophy

Realtime voice agents are NOT:

```text
STT → LLM → TTS demos
```

They are:

```text
low-latency distributed realtime systems
```

The hardest problems are:

- interruptions
- latency
- streaming
- orchestration
- cancellation
- synchronization
- safety
- state management

NOT model intelligence.