import requests

#from ans_verify import verify_agent, ANSVerificationError
from ans_verify import (
    verify_agent,
    resolve_ans_agent,
    ANSVerificationError,
)
from config import PARTNER_AGENT_URL


def ask_partner_agent(message: str, url: str | None = None):
    payload = {"message": message}

    try:
        if url is None:
            # Normal path: discover/resolve real Seller through ANS
            resolved = resolve_ans_agent(
                "seller.domainguard.us",
                "1.0.0"
            )
            target = resolved["endpoint"]
        else:
            # Attack/demo path: use the supplied target directly
            resolved = None
            target = url

        # Always verify before sending anything
        identity = verify_agent(target)

    except ANSVerificationError as e:
        return {
            "error": "REFUSED",
            "reason": str(e),
            "target": target,
        }

    try:
        response = requests.post(
            target,
            json=payload,
            timeout=60
        )
        response.raise_for_status()

        result = {
            "verified_identity": identity,
            "target": target,
            "result": response.json(),
        }

        if resolved is not None:
            result["resolved_through_ans"] = resolved

        return result

    except requests.RequestException as e:
        return {
            "error": f"Partner agent unreachable or failed: {e}",
            "target": target,
        }

if __name__ == "__main__":
    print(ask_partner_agent("Hello from the Buyer agent"))