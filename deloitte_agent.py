import os
import threading
import time
from collections import deque
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from google import genai
from google.genai import types

from agent_client import ask_partner_agent
from attack_tests import run_battery, LOOKALIKE_URL
from config import PARTNER_AGENT_URL

load_dotenv()

app = FastAPI(title="Buyer Agent")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODELS = [
    os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
]
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:8000")

# Fixed server-side targets: visitors pick a name, never a URL
TARGETS = {
    "seller": PARTNER_AGENT_URL,
    "lookalike": LOOKALIKE_URL,
}

SYSTEM_PROMPT = (
    "You are Buyer Agent. You help users by asking a Seller Agent questions "
    "through the ask_seller tool. The tool verifies the Seller's ANS identity "
    "before contacting it. Rules: (1) Use ask_seller whenever the user wants "
    "information from the seller. (2) If the tool result contains "
    "error=REFUSED, tell the user the seller failed identity verification and "
    "state the reason. Do not try to reach the seller any other way. (3) Only "
    "say the seller is verified if the tool result contains verified_identity. "
    "Answer briefly."
)

# Simple global rate limit so a public demo can't burn the Gemini quota
_hits: deque = deque()
_hits_lock = threading.Lock()


def rate_limited(limit: int = 20, window: int = 60) -> bool:
    now = time.time()
    with _hits_lock:
        while _hits and now - _hits[0] > window:
            _hits.popleft()
        if len(_hits) >= limit:
            return True
        _hits.append(now)
        return False


class BuyerRequest(BaseModel):
    message: str
    target: str = "seller"


@app.get("/", response_class=HTMLResponse)
def home():
    return (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health():
    return {"agent": "Buyer Agent", "status": "running"}


@app.get("/.well-known/agent-card.json")
def agent_card():
    return {
        "name": "Buyer Agent",
        "description": "Gemini-powered buyer agent that verifies sellers through ANS before contacting them",
        "url": PUBLIC_URL,
        "version": "1.0.0",
        "capabilities": {"streaming": False},
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": [
            {
                "id": "ask",
                "name": "Ask a verified seller",
                "description": "Forwards questions to a seller only after ANS verification",
            }
        ],
    }


_battery_cache = {"time": 0.0, "data": None}
_battery_lock = threading.Lock()


@app.get("/api/attacks")
def api_attacks():
    if rate_limited():
        raise HTTPException(status_code=429, detail="Too many requests, wait a minute.")
    with _battery_lock:
        if _battery_cache["data"] and time.time() - _battery_cache["time"] < 300:
            return _battery_cache["data"]
        try:
            results = run_battery()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Could not run battery: {e}")
        data = {
            "blocked": sum(r["verdict"] == "BLOCKED" for r in results),
            "total": len(results),
            "results": results,
        }
        _battery_cache.update(time=time.time(), data=data)
        return data


@app.post("/ask")
def ask_buyer_agent(request: BuyerRequest):
    if request.target not in TARGETS:
        raise HTTPException(status_code=400, detail="Unknown target")
    if rate_limited():
        raise HTTPException(status_code=429, detail="Too many requests, wait a minute.")
    seller_url = TARGETS[request.target]

    calls = []  # raw evidence of what the seller tool returned

    def ask_seller(question: str) -> dict:
        """Ask the Seller Agent a question. The Seller's ANS identity is verified first; if verification fails the request is refused and nothing is sent."""
        result = ask_partner_agent(question, url=seller_url)
        calls.append({"question": question, "result": result})
        return result

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[ask_seller],
    )

    last_error = None
    for model in MODELS:
        for attempt in range(3):
            try:
                calls.clear()
                chat = client.chats.create(model=model, config=config)
                response = chat.send_message(request.message)
                return {
                    "agent": "Buyer Agent",
                    "model": model,
                    "target": request.target,
                    "user_message": request.message,
                    "response": response.text or "",
                    "seller_calls": list(calls),
                }
            except Exception as e:
                last_error = e
                print(f"{model} attempt {attempt + 1} failed: {e}")
                if "503" in str(e) or "429" in str(e):
                    time.sleep(2 ** attempt)
                else:
                    break

    raise HTTPException(status_code=503, detail=f"Gemini unavailable: {last_error}")