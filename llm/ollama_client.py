import asyncio
import ollama
from typing import AsyncGenerator, List, Dict
import structlog

logger = structlog.get_logger()

class OllamaClient:
    def __init__(self, model: str = "qwen2.5:3b"):
        self.model = model
        self.client = ollama.AsyncClient()

    async def stream_chat(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Streams responses from Ollama token by token."""
        logger.info("llm_stream_start", model=self.model)
        try:
            async for part in await self.client.chat(
                model=self.model,
                messages=messages,
                stream=True
            ):
                token = part['message']['content']
                if token:
                    yield token
        except Exception as e:
            logger.error("ollama_stream_error", error=str(e))
            yield f"Error: {str(e)}"

class LLMWorker:
    def __init__(self, event_bus, client: OllamaClient):
        self.event_bus = event_bus
        self.client = client
        self.history: List[Dict[str, str]] = [
            {"role": "system", "content": "You are a realtime conversational voice assistant. Speak naturally, keep responses concise, avoid markdown, and respond conversationally."}
        ]

    async def handle_user_message(self, text: str):
        self.history.append({"role": "user", "content": text})
        
        full_response = ""
        async for token in self.client.stream_chat(self.history):
            full_response += token
            await self.event_bus.emit("LLM_TOKEN", token)
            
        self.history.append({"role": "assistant", "content": full_response})
        await self.event_bus.emit("LLM_COMPLETE", full_response)
