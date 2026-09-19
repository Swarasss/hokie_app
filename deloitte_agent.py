import os
from fastapi import FastAPI
from pydantic import BaseModel

from agent_client import ask_partner_agent

app = FastAPI(title="HokieHelper Agent")


class DeloitteRequest(BaseModel):
    message: str


@app.get("/")
def root():
    return {
        "agent": "Deloitte Agent",
        "status": "running"
    }

PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:8000")


@app.get("/.well-known/agent-card.json")
def agent_card():
    return {
        "name": "Hokie Helper Agent",
        "description": "Agent that delegates requests to a verified partner agent",
        "url": PUBLIC_URL,
        "version": "1.0.0",
        "capabilities": {"streaming": False},
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": [
            {
                "id": "ask",
                "name": "Delegate questions",
                "description": "Forwards questions to a partner agent",
            }
        ],
    }


@app.post("/ask")
def ask_deloitte_agent(request: DeloitteRequest):
    user_message = request.message

    partner_response = ask_partner_agent(user_message)

    return {
        "agent": "Deloitte Agent",
        "user_message": user_message,
        "partner_response": partner_response
    }

