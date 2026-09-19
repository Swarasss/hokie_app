import os

from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)


def test_tool(message: str) -> str:
    """Simple test tool that confirms it was called."""
    return f"Tool received: {message}"


config = types.GenerateContentConfig(
    tools=[test_tool]
)

chat = client.chats.create(
    model="gemini-3.8-flash",
    config=config
)

response = chat.send_message(
    "Use the test_tool with the message 'hello from Gemini', then tell me what it returned."
)

print(response.text)