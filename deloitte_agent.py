from fastapi import FastAPI
from pydantic import BaseModel

from agent_client import ask_partner_agent

app = FastAPI(title="Deloitte Agent")


class DeloitteRequest(BaseModel):
    message: str


@app.get("/")
def root():
    return {
        "agent": "Deloitte Agent",
        "status": "running"
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

