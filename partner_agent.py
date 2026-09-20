import os
import time

from a2a.server.routes import add_a2a_routes_to_fastapi, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.request_handlers.default_request_handler import LegacyRequestHandler
from a2a.types import AgentCard, AgentCapabilities, AgentInterface, AgentSkill

from seller_a2a import SellerAgentExecutor

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google import genai


load_dotenv()

app = FastAPI(title="Seller Agent")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


class AgentRequest(BaseModel):
    message: str


@app.get("/")
def root():
    return {"agent": "Seller Agent", "status": "running"}


MODELS = [
    os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
]


PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:8001")

a2a_card = AgentCard(
    name="Seller Agent",
    description="Independent Gemini-powered seller agent",
    supported_interfaces=[
        AgentInterface(
            url=f"{PUBLIC_URL}/a2a",
            protocol_binding="JSONRPC",
            protocol_version="1.0",
        )
    ],
    version="1.0.0",
    capabilities=AgentCapabilities(
        streaming=False,
    ),
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    skills=[
        AgentSkill(
            id="ask",
            name="Answer buyer questions",
            description="Answers questions from buyer agents",
            tags=["seller", "commerce", "qa"],
            input_modes=["text/plain"],
            output_modes=["text/plain"],
        )
    ],
)

a2a_handler = LegacyRequestHandler(
    agent_executor=SellerAgentExecutor(),
    task_store=InMemoryTaskStore(),
    agent_card=a2a_card,
)

a2a_routes = create_jsonrpc_routes(
    a2a_handler,
    rpc_url="/a2a",
)

add_a2a_routes_to_fastapi(
    app,
    jsonrpc_routes=a2a_routes,
)


@app.get("/.well-known/agent-card.json")
def agent_card():
    return {
        "name": "Seller Agent",
        "description": "Independent AI service agent powered by Gemini",
        "url": PUBLIC_URL,
        "version": "1.0.0",
        "capabilities": {"streaming": False},
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": [
            {
                "id": "ask",
                "name": "Answer questions",
                "description": "Answers short questions from other agents",
            }
        ],
    }




@app.post("/ask")
def ask_agent(request: AgentRequest):
    last_error = None
    prompt = (
        "You are Seller Agent, an independent AI service agent. "
        "Answer clearly and briefly.\n\n"
        f"User request: {request.message}"
    )

    for model in MODELS:
        for attempt in range(3):
            try:
                response = client.models.generate_content(model=model, contents=prompt)
                return {
                    "agent": "Seller Agent",
                    "model": model,
                    "response": response.text,
                }
            except Exception as e:
                last_error = e
                print(f"{model} attempt {attempt + 1} failed: {e}")
                # Only worth retrying on capacity/rate errors
                if "503" in str(e) or "429" in str(e):
                    time.sleep(2 ** attempt)
                else:
                    break  # bad model name, auth, etc: move to next model

    raise HTTPException(status_code=503, detail=f"All models unavailable: {last_error}")