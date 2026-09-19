from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Partner Agent")


class AgentRequest(BaseModel):
    message: str


@app.get("/")
def root():
    return {
        "agent": "Partner Agent",
        "status": "running"
    }


@app.post("/ask")
def ask_agent(request: AgentRequest):
    user_message = request.message

    response_message = f"Partner Agent received: {user_message}"

    return {
        "agent": "Partner Agent",
        "response": response_message
    }