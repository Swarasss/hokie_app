import requests

PARTNER_AGENT_URL = "http://localhost:8001/ask"


def ask_partner_agent(message: str):
    payload = {
        "message": message
    }

    response = requests.post(
        PARTNER_AGENT_URL,
        json=payload,
        timeout=10
    )

    response.raise_for_status()

    return response.json()


if __name__ == "__main__":
    result = ask_partner_agent("Hello from the Deloitte agent")
    print(result)

    