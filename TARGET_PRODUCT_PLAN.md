# FRIDAY Target Product Plan and Delivery Path

## 1. Product Vision
FRIDAY is a fully local, realtime voice assistant that runs on CPU-only laptops and supports natural, interruption-safe conversation without cloud dependency.

## 2. Current State (as implemented)
- Async event-driven skeleton is in place.
- Audio capture and playback components exist.
- Silero VAD worker exists and emits speaking events.
- STT worker uses faster-whisper in CPU int8 mode.
- LLM worker streams responses from Ollama (qwen2.5:3b).
- TTS worker uses Kokoro ONNX model and pushes audio to playback.
- Model asset downloader exists for Kokoro assets.

## 3. Target Product Definition
A production-ready local assistant that can:
- Listen continuously and detect user speech reliably.
- Transcribe and answer with low latency via streaming.
- Speak naturally and stop immediately when interrupted.
- Recover gracefully from component/runtime errors.
- Run safely on Windows/Linux with simple setup.
- Evolve toward tool use and memory while preserving privacy.

## 4. Success Metrics
- Wake and speech reaction latency under 150 ms.
- LLM first token under 700 ms on target hardware.
- TTS start latency under 250 ms.
- Interruption stop response under 300 ms.
- Stable operation over long sessions without queue/memory growth.

## 5. Delivery Path

### Phase A: Baseline Stability (Immediate)
- Fix startup/runtime blockers and dependency gaps.
- Verify end-to-end single-turn conversation loop.
- Add reliable startup checks (models present, Ollama reachable).
- Add structured error handling around all workers.

### Phase B: Realtime Robustness
- Improve speech start/stop reliability thresholds.
- Add interruption logic to cancel LLM and flush playback.
- Enforce queue backpressure policy and instrumentation.
- Add latency logging for each pipeline stage.

### Phase C: Product Hardening
- Add config file/env-based settings for model names, rates, thresholds.
- Add smoke tests for import/startup and key event paths.
- Add health diagnostics command for local validation.
- Improve developer setup scripts for one-command onboarding.

### Phase D: Feature Expansion
- Add tool execution layer with explicit user permission gates.
- Add short-term and long-term memory modules.
- Add optional personalization (voice choice, response style).

## 6. Engineering Workstreams
- Runtime: async coordination, cancellation, queue behavior.
- Speech: VAD tuning, STT buffering, transcript quality.
- LLM/TTS: stream chunking, low-latency synthesis, interruption.
- Platform: setup automation, dependency pinning, docs.
- Observability: logs, latency counters, startup diagnostics.

## 7. Risk Register
- CPU overload when multiple heavy stages overlap.
- VAD false positives in noisy rooms.
- Missing model artifacts causing startup failure.
- Platform-specific native dependency issues on Windows.

Mitigations:
- Bounded queues + backpressure.
- Runtime health checks before start.
- Explicit model preflight checks and clear error messages.
- Locked dependency versions and setup scripts.

## 8. Local Setup Runbook (Windows)

### Step 1: System prerequisites
- Python 3.10+ installed and on PATH.
- Ollama installed from https://ollama.com.
- Working microphone and speakers.

### Step 2: Python environment and packages
From project root:
- python -m venv .venv
- .venv\Scripts\activate
- pip install --upgrade pip setuptools wheel
- pip install -r requirements.txt

### Step 3: Ollama model
- ollama pull qwen2.5:3b
- keep Ollama running in background

### Step 4: Download local model assets
- python scripts/download_models.py

### Step 5: Playwright browser runtime
- playwright install

### Step 6: Start app
- python main.py

## 9. Validation Checklist
- App starts without import/runtime exceptions.
- Speaking triggers USER_STARTED_SPEAKING and USER_STOPPED_SPEAKING logs.
- STT emits non-empty final text.
- LLM streams token events.
- TTS emits playable audio chunks.
- Interruption during assistant speech stops playback promptly.

## 10. Near-Term Next Milestones
1. Complete startup and dependency fixes.
2. Add startup self-check command and documentation.
3. Implement robust interruption cancellation path.
4. Add latency metrics and a simple benchmark script.
