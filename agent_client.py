import requests

from config import PARTNER_AGENT_URL


def ask_partner_agent(message: str):
    payload = {"message": message}

    try:
        response = requests.post(
            PARTNER_AGENT_URL,
            json=payload,
            timeout=30,  # was 10
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"error": f"Partner agent unreachable or failed: {e}"}


if __name__ == "__main__":
    print(ask_partner_agent("Hello from the HokieHelper agent"))