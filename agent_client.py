import requests

from ans_verify import verify_agent, ANSVerificationError
from config import PARTNER_AGENT_URL


def ask_partner_agent(message: str, url: str | None = None):
    target = url or PARTNER_AGENT_URL
    payload = {"message": message}

    # ANS identity check BEFORE sending anything
    try:
        identity = verify_agent(target)
    except ANSVerificationError as e:
        return {"error": "REFUSED", "reason": str(e), "target": target}

    try:
        response = requests.post(target, json=payload, timeout=60)
        response.raise_for_status()
        return {"verified_identity": identity, "target": target, "result": response.json()}
    except requests.RequestException as e:
        return {"error": f"Partner agent unreachable or failed: {e}", "target": target}


if __name__ == "__main__":
    print(ask_partner_agent("Hello from the Buyer agent"))