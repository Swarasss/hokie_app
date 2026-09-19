import requests

from ans_verify import verify_agent, ANSVerificationError
from config import PARTNER_AGENT_URL


def ask_partner_agent(message: str):
    payload = {"message": message}

    # ANS identity check BEFORE sending anything
    try:
        identity = verify_agent(PARTNER_AGENT_URL)
    except ANSVerificationError as e:
        return {"error": "REFUSED", "reason": str(e)}

    try:
        response = requests.post(
            PARTNER_AGENT_URL,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return {"verified_identity": identity, "result": response.json()}
    except requests.RequestException as e:
        return {"error": f"Partner agent unreachable or failed: {e}"}


if __name__ == "__main__":
    print(ask_partner_agent("Hello from the HokieHelper agent"))