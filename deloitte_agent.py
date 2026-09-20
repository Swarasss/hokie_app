import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google import genai
from google.genai import types

from agent_client import ask_partner_agent

load_dotenv()

app = FastAPI(title="Buyer Agent")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODELS = [
    os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
]
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:8000")

SYSTEM_PROMPT = (
    "You are a Buyer Agent. You help users by asking a Seller Agent questions "
    "through the ask_seller tool. The tool verifies the Seller's ANS identity "
    "before contacting it. Rules: (1) Use ask_seller whenever the user wants "
    "information from the seller. (2) If the tool result contains "
    "error=REFUSED, tell the user the seller failed identity verification and "
    "state the reason. Do not try to reach the seller any other way. (3) Only "
    "say the seller is verified if the tool result contains verified_identity. "
    "Answer briefly."
)


class BuyerRequest(BaseModel):
    message: str


@app.get("/")
def root():
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


@app.post("/ask")
def ask_buyer_agent(request: BuyerRequest):
    calls = []  # raw evidence of what the seller tool returned

    def ask_seller(question: str) -> dict:
        """Ask the Seller Agent a question. The Seller's ANS identity is verified first; if verification fails the request is refused and nothing is sent."""
        result = ask_partner_agent(question)
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