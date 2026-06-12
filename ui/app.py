from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from pathlib import Path
from urllib.parse import quote_plus
from datetime import datetime
import re
import json
import requests

from main import VoiceAgent

app = FastAPI()
agent = VoiceAgent()
ws_connections = set()


class ChatRequest(BaseModel):
    text: str
    use_web: bool = False

async def broadcast(msg: dict):
    dead = []
    for ws in list(ws_connections):
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for d in dead:
        ws_connections.discard(d)


def web_search(query: str, limit: int = 3) -> list[dict]:
    response = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": limit,
        },
        timeout=10,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    payload = response.json()
    results = []
    for item in payload.get("query", {}).get("search", []):
        title = item.get("title", "")
        snippet = re.sub(r"<.*?>", "", item.get("snippet", ""))
        results.append(
            {
                "title": title,
                "snippet": snippet,
                "url": f"https://en.wikipedia.org/wiki/{quote_plus(title.replace(' ', '_'))}",
            }
        )
    return results


def weather_summary(location: str) -> str:
    geo = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": location, "count": 1, "language": "en", "format": "json"},
        timeout=10,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    geo.raise_for_status()
    places = geo.json().get("results", [])
    if not places:
        return f"I couldn't find weather data for {location}."

    lat = places[0]["latitude"]
    lon = places[0]["longitude"]
    display_name = ", ".join(
        part for part in [
            places[0].get("name"),
            places[0].get("admin1"),
            places[0].get("country"),
        ]
        if part
    ) or location

    weather = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
            "timezone": "auto",
        },
        timeout=10,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    weather.raise_for_status()
    current = weather.json().get("current", {})
    code = current.get("weather_code", -1)
    descriptions = {
        0: "clear sky",
        1: "mostly clear",
        2: "partly cloudy",
        3: "overcast",
        45: "fog",
        48: "depositing rime fog",
        51: "light drizzle",
        53: "moderate drizzle",
        55: "dense drizzle",
        61: "light rain",
        63: "moderate rain",
        65: "heavy rain",
        71: "light snow",
        73: "moderate snow",
        75: "heavy snow",
        80: "rain showers",
        81: "heavy rain showers",
        95: "thunderstorm",
    }
    condition = descriptions.get(code, f"weather code {code}")
    temperature = current.get("temperature_2m")
    feels_like = current.get("apparent_temperature")
    wind = current.get("wind_speed_10m")
    return (
        f"Current weather for {display_name}: {condition}, "
        f"temperature {temperature}°C, feels like {feels_like}°C, wind {wind} km/h."
    )


def calendar_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "calendar.json"


def local_calendar_summary() -> str:
    path = calendar_path()
    if not path.exists():
        return "You do not have a local calendar file yet."

    try:
        events = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return "Your local calendar file could not be read."

    if not events:
        return "Your local calendar is empty."

    lines = ["Your local calendar events:"]
    for event in events[:5]:
        title = event.get("title", "Untitled event")
        start = event.get("start", "unknown time")
        end = event.get("end", "unknown time")
        lines.append(f"- {title} from {start} to {end}")
    return "\n".join(lines)


def build_tool_context(query: str) -> str:
    lowered = query.lower()
    if any(word in lowered for word in ["weather", "temperature", "forecast", "rain", "snow"]):
        match = re.search(r"weather(?: in| for)?\s+(.+)$", lowered)
        location = match.group(1).strip() if match else "your location"
        return weather_summary(location)

    if any(word in lowered for word in ["calendar", "schedule", "agenda", "events"]):
        return local_calendar_summary()

    if any(word in lowered for word in ["today", "current", "now", "latest", "news", "real world", "world"]):
        search_results = web_search(query)
        if search_results:
            return "\n".join(
                f"{i + 1}. {item['title']} - {item['snippet']} ({item['url']})"
                for i, item in enumerate(search_results)
            )

    search_results = web_search(query)
    if not search_results:
        return ""

    return "\n".join(
        f"{i + 1}. {item['title']} - {item['snippet']} ({item['url']})"
        for i, item in enumerate(search_results)
    )


@app.on_event("startup")
async def startup():
    async def on_stt_final(data):
        await broadcast({"type": "STT_FINAL", "text": data})

    async def on_llm_token(data):
        await broadcast({"type": "LLM_TOKEN", "token": data})

    async def on_llm_complete(data):
        await broadcast({"type": "LLM_COMPLETE", "text": data})

    agent.event_bus.subscribe("STT_FINAL", on_stt_final)
    agent.event_bus.subscribe("LLM_TOKEN", on_llm_token)
    agent.event_bus.subscribe("LLM_COMPLETE", on_llm_complete)
    try:
        await agent._setup()
    except Exception:
        pass


@app.get("/")
async def index():
    html = Path(__file__).parent.joinpath("templates/index.html").read_text()
    return HTMLResponse(html)


@app.post("/start")
async def start_agent():
    try:
        await agent._setup()
        return {"status": "ready"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@app.post("/stop")
async def stop_agent():
    return {"status": "stopped"}


@app.post("/chat")
async def chat(req: ChatRequest):
    text = req.text.strip()
    if not text:
        return {"status": "empty"}

    await broadcast({"type": "USER_TEXT", "text": text})
    try:
        prompt = text
        if req.use_web:
            tool_context = build_tool_context(text)
            if tool_context:
                prompt = (
                    f"Use the following live tool data to answer the user's question. "
                    f"Stay concise, factual, and conversational.\n\n"
                    f"Tool data:\n{tool_context}\n\nUser question: {text}"
                )
        response = await agent.llm_worker.handle_user_message(prompt)
        return {"status": "ok", "reply": response}
    except Exception as exc:
        fallback = f"I heard: {text}."
        await broadcast({"type": "LLM_COMPLETE", "text": fallback})
        return {"status": "ok", "reply": fallback, "detail": str(exc)}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ws_connections.add(websocket)
    try:
        while True:
            # keep connection alive; client may send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_connections.discard(websocket)
