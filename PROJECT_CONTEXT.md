# FRIDAY Project - Complete Context & Future Plan

---

## PART 1: PROJECT CONTEXT

### 🎯 NON-TECHNICAL PERSPECTIVE (Simple Explanation)

#### What is FRIDAY?

Think of FRIDAY as a **personal AI assistant that you can talk to**, like Siri or Alexa, but better. Here's what makes it different:

- **It lives on your computer** - Your conversations never leave your device. No internet required. Your privacy is 100% safe.
- **It listens to you** - Always ready to hear your voice command whenever you say the wake word.
- **It understands you** - Converts your speech into text, understands what you mean, and thinks about the right answer.
- **It talks back** - Generates a voice response using natural speech synthesis, so it sounds like a real person is talking to you.
- **It works on basic laptops** - No expensive GPU needed. It runs smoothly on regular home computers with Intel processors and 16GB of RAM.
- **It's fast** - Response time is under 1 second, making conversations feel natural.
- **It can do tasks** - It can execute actions (safely) like searching the web, reading files, or controlling your computer.

#### How Does It Help You?

1. **Hands-free control** - Talk instead of typing or clicking
2. **Always available** - Works offline, no waiting for cloud servers
3. **Privacy** - Nothing shared with external services
4. **Personalized** - Can learn your preferences and remember conversations
5. **Natural** - Sounds and feels like talking to a real person

---

### 💻 TECHNICAL PERSPECTIVE (Developer Explanation)

#### Core Architecture

FRIDAY is a **streaming-first, CPU-optimized voice agent** built on Python with the following pipeline:

```
Audio Capture (Microphone)
    ↓
VAD (Voice Activity Detection) - Silero VAD
    ↓
Wake Word Detection - openWakeWord
    ↓
Speech-to-Text (STT) - faster-whisper (base.en, int8)
    ↓
Conversation Manager
    ↓
Large Language Model (LLM) - Qwen 2.5 3B via Ollama
    ↓
Response Streaming
    ↓
Semantic Chunker
    ↓
Text-to-Speech (TTS) - Kokoro-82M (ONNX)
    ↓
Audio Playback (Speaker)
```

#### Key Technical Design Principles

1. **Streaming-First Architecture**
   - Never blocks waiting for complete transcriptions or responses
   - Processes audio in chunks for minimal latency
   - Bounded async queues prevent memory bloat and provide backpressure

2. **Async-Driven**
   - Built entirely on `asyncio` for concurrent task execution
   - Non-blocking I/O for all components
   - Event-driven state transitions

3. **Modular Design**
   - Decoupled components communicate via central Event Bus
   - Each component is replaceable (e.g., swap STT engines)
   - Clean separation of concerns

#### Tech Stack Breakdown

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Audio I/O | sounddevice, numpy | Capture and playback audio streams |
| Resampling | librosa, resampy | Convert audio to required sample rates |
| VAD | Silero VAD | Detect human speech vs silence |
| Wake Word | openWakeWord | "Cold start" activation (e.g., "Friday, ...") |
| STT | faster-whisper (int8) | Convert speech to text with low latency |
| LLM Runtime | Ollama | Local Large Language Model inference |
| LLM Model | Qwen 2.5 3B | Compact 3B parameter model for responses |
| TTS | Kokoro-82M (ONNX) | Convert text to natural-sounding speech |
| Event System | asyncio + custom EventBus | Pub/Sub event routing between components |
| State Machine | transitions library | FSM for tracking agent states |
| Config | pydantic-settings | Type-safe configuration management |
| Automation | playwright | Browser control for tool execution |
| Memory | JSON (Phase 1), SQLite (Phase 4) | Persistent conversation and knowledge storage |
| Embeddings | sentence-transformers | Semantic search and context retrieval |

#### Performance Targets (CPU-Optimized)

| Metric | Target |
|--------|--------|
| Wake Word Detection Latency | < 150ms |
| STT Latency (first token) | < 500ms |
| LLM First Token Latency | < 700ms |
| TTS Start Latency | < 250ms |
| Interruption Response Time | < 300ms |
| RAM Usage | < 12GB |
| CPU | Intel i5-1334U (11th gen, P-cores) |
| RAM | 16GB minimum |

#### Component Deep Dive

**VAD Worker (Voice Activity Detection)**
- Filters out silence and background noise
- Triggers STT only when actual speech is detected
- Uses Silero VAD model

**STT Worker (Speech-to-Text)**
- Converts audio chunks to text using faster-whisper
- Runs in int8 quantization for speed
- Streams results to conversation manager

**LLM Worker**
- Sends transcribed text to Ollama (local LLM inference engine)
- Uses Qwen 2.5 3B model
- Streams response token-by-token for low latency

**TTS Worker (Text-to-Speech)**
- Consumes LLM response chunks as they arrive
- Queues audio synthesis using Kokoro-82M ONNX model
- Non-blocking playback to speaker

**Event Bus**
- Central publish/subscribe system
- Routes events: `user_started_speaking`, `user_stopped_speaking`, `text_transcribed`, `llm_response_ready`, etc.
- Enables loose coupling between components

#### Why CPU-Optimized?

Traditional voice agents require GPU acceleration. FRIDAY is optimized for CPU-only because:
1. **Efficiency**: Smaller models (3B param LLM, 82M param TTS)
2. **Quantization**: int8 STT, ONNX format for TTS
3. **Parallelism**: Async I/O exploits CPU wait time
4. **Target Hardware**: Intel i5 (11th gen with P-cores) can handle streaming inference

---

## PART 2: FUTURE PLAN

### 📋 NON-TECHNICAL PERSPECTIVE (What's Coming)

#### Phase 1-2: Foundation (Now)
- ✅ Voice capture and playback working
- ✅ Speech recognition functional
- ✅ Basic AI responses
- 🔄 **Current Focus**: Get the core system stable and fast

#### Phase 3-4: Smart Features (Next)
- **Memory & Learning**
  - FRIDAY remembers past conversations
  - Gets smarter about understanding your preferences
  - Can reference earlier discussions

- **Tool Integration** (Do real tasks)
  - Send emails through your email app
  - Search the internet and read articles
  - Control your computer (open apps, files, etc.)
  - Interact with websites
  - All with your explicit permission

- **Personalization**
  - Choose different voices
  - Learn your accent
  - Adapt response style to your preference

#### Phase 5: Advanced (Future)
- **Knowledge Base**
  - FRIDAY can upload and understand documents
  - Search within your personal library
  - Summarize and extract information

- **Multi-language Support**
  - Speak in different languages
  - Automatic translation

- **Better Understanding**
  - Context awareness (remembers long conversations)
  - Emotional intelligence (detects your mood)
  - Nuanced responses to complex questions

#### Phase 6: Enterprise Ready
- **Scalability** - Handle multiple users and higher loads
- **Security** - Production-grade encryption and access control
- **Monitoring** - Track performance and usage metrics
- **Mobile Support** - Run on phones and tablets

---

### 🚀 TECHNICAL PERSPECTIVE (Development Roadmap)

#### Phase 1: Core MVP ✅ (Current)

**Status**: Audio pipeline, VAD, STT, basic LLM response working

**Tasks**:
- [x] Audio capture/playback with sounddevice
- [x] VAD integration (Silero)
- [x] STT pipeline (faster-whisper)
- [x] Ollama LLM integration (Qwen 2.5 3B)
- [x] TTS basic streaming (Kokoro-82M ONNX)
- [x] Event bus infrastructure
- [ ] Full system integration test
- [ ] Latency profiling and optimization

**Deliverable**: Fully functional streaming voice agent with < 1s response time

---

#### Phase 2: Production Hardening 🔄 (Current Focus)

**Tasks**:
- [ ] Wake word re-arming after speech
- [ ] Interruption handling (stop playback mid-response)
- [ ] Robust error recovery and retry logic
- [ ] Memory management optimization (bounded queues, garbage collection)
- [ ] Comprehensive logging and telemetry
- [ ] Configuration system (pydantic-settings)
- [ ] Unit tests for critical paths
- [ ] Performance benchmarking suite

**Deliverable**: Stable, production-grade voice agent

---

#### Phase 3: Memory & Context 📝 (Q3 2026)

**Architecture**:
```
Conversation State
    ↓
Memory Encoder (sentence-transformers)
    ↓
JSON Storage (Phase 3a) → SQLite w/ embeddings (Phase 3b)
    ↓
Semantic Search
    ↓
Context Retriever
    ↓
LLM Context Window
```

**Tasks**:
- [ ] Implement conversation history storage (JSON initially)
- [ ] Conversation embeddings (sentence-transformers)
- [ ] Semantic search for context retrieval
- [ ] Long-context support in prompts
- [ ] Multi-turn conversation state
- [ ] Export conversations (JSON/CSV)

**Deliverable**: FRIDAY remembers conversations and context across sessions

---

#### Phase 4: Tool Execution & Permissions 🛠️ (Q4 2026)

**Tool Architecture**:
```
Tool Registry (Pydantic schemas)
    ↓
Tool Dispatcher
    ↓
Permission Checker (sandboxing rules)
    ↓
Execution Engine
    ↓
Result Handler
```

**Supported Tools**:
- **File I/O** - Read/write files (with path restrictions)
- **Web Search** - DuckDuckGo API (no tracking)
- **Email** - SMTP integration (Outlook, Gmail)
- **Browser Control** - Playwright for web automation
- **System Control** - File browser, app launcher (Linux/Windows)
- **Database** - Local SQLite queries
- **Calculator** - Math/expression evaluation
- **Timer/Reminders** - Schedule tasks

**Tasks**:
- [ ] Tool schema definition system
- [ ] Permission model & sandboxing
- [ ] Tool dispatcher middleware
- [ ] Playground CLI for tool testing
- [ ] Audit logs for tool execution
- [ ] Approval workflows for sensitive tools

**Deliverable**: FRIDAY can safely execute tools with user permission control

---

#### Phase 5: Advanced NLP & Personalization 🧠 (Q1 2027)

**Tasks**:
- [ ] Speaker ID (recognize who's speaking)
- [ ] Multi-language support (code-switching)
- [ ] Sentiment analysis (detect user mood)
- [ ] Intent classification refinement
- [ ] Custom wake words
- [ ] Voice profile training (accent adaptation)
- [ ] Personality/style prompts

**Deliverable**: FRIDAY understands who you are and adapts responses

---

#### Phase 6: Knowledge Management 📚 (Q2 2027)

**Tasks**:
- [ ] RAG (Retrieval-Augmented Generation) pipeline
- [ ] Document upload & indexing
- [ ] Semantic search over knowledge base
- [ ] Citation tracking (where info came from)
- [ ] Vector database (Weaviate/Milvus integration)
- [ ] Batch indexing for large doc sets

**Deliverable**: FRIDAY can reference and summarize your documents

---

#### Phase 7: Observability & Analytics 📊 (Q2 2027)

**Tasks**:
- [ ] Complete metrics pipeline (Prometheus-style)
- [ ] Latency tracking (P50, P95, P99)
- [ ] Error rate monitoring
- [ ] Resource usage dashboards
- [ ] User interaction analytics
- [ ] Model performance tracking

**Deliverable**: Full production observability stack

---

#### Phase 8: Enterprise & Scale 🏢 (Q3 2027+)

**Tasks**:
- [ ] Multi-user support (tenant isolation)
- [ ] Distributed Ollama inference (multi-GPU clusters)
- [ ] Database migration to production DBs (PostgreSQL, MongoDB)
- [ ] API server (FastAPI/gRPC)
- [ ] Authentication & authorization (Oauth2, RBAC)
- [ ] Encryption at rest & in transit
- [ ] Backup & disaster recovery
- [ ] Kubernetes deployment manifests

**Deliverable**: Enterprise-grade deployment ready

---

### Critical Path Dependencies

```
Phase 1 (MVP) ✅
    ↓
Phase 2 (Hardening) 🔄
    ↓
Phase 3 (Memory) ← Dependency for Phase 4
    ↓
Phase 4 (Tools) ← Dependency for Phase 5
    ↓
Phase 5 (Personalization)
    ↓
Phase 6 (Knowledge) + Phase 7 (Observability) [Parallel]
    ↓
Phase 8 (Enterprise Scale)
```

### Performance Optimization Priorities (Next Quarter)

1. **Latency** - Reduce LLM first-token latency to < 500ms
2. **Memory** - Optimize bounded queues to stay under 10GB
3. **Interruption** - Sub-300ms response to speech interruption
4. **Throughput** - Handle 2+ concurrent conversations on single i5

### Known Challenges & Solutions

| Challenge | Root Cause | Solution |
|-----------|-----------|----------|
| VAD false positives | Background noise sensitivity | Threshold tuning, noise profiling |
| LLM latency spikes | Model inference variance | Batch normalization, model quantization |
| TTS quality | Kokoro phoneme handling | Voice profile training, prosody tuning |
| Interruption lag | Event queue blocking | Async queue prioritization, priority task scheduler |
| Memory creep | Unbounded loggers/caches | Bounded buffers, explicit cleanup |

---

## Summary Timeline

| Phase | Duration | Status | Key Outcome |
|-------|----------|--------|------------|
| 1 | 4 weeks | ✅ Done | Working voice agent |
| 2 | 4 weeks | 🔄 Current | Production-ready stability |
| 3 | 4 weeks | 📅 Jul 2026 | Memory & context |
| 4 | 6 weeks | 📅 Aug 2026 | Tool execution |
| 5 | 4 weeks | 📅 Oct 2026 | Personalization |
| 6-7 | 6 weeks | 📅 Nov 2026 | Knowledge + monitoring |
| 8 | 8+ weeks | 📅 Jan 2027 | Enterprise scale |

**Overall Timeline**: 3-4 months to Phase 2 MVP, 12 months to full enterprise feature set.

