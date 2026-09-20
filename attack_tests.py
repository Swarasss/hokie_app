"""Attack battery against Agent A's ANS verifier. Every attack must be BLOCKED."""
import copy
import sys
from unittest.mock import patch

import requests

import ans_verify
from ans_verify import verify_agent, ANSVerificationError

REAL_HOST = "seller.domainguard.us"
REAL_URL = f"https://{REAL_HOST}/ask"


class FakeResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


# Real identity material, fetched once and then tampered with per attack
_badge = ans_verify._lookup_txt(f"_ans-badge.{REAL_HOST}", "v=ans-badge1")
_entry = requests.get(_badge["url"], timeout=10).json()
_real_lookup = ans_verify._lookup_txt


def attempt(url, entry=None, badge=None):
    """Verify `url` while DNS serves `badge` and the log serves `entry`."""
    entry = _entry if entry is None else entry
    badge = _badge if badge is None else badge

    def fake_lookup(name, prefix):
        if name.startswith("_ans-badge."):
            return badge
        return _real_lookup(name, prefix)

    with patch.object(ans_verify, "_lookup_txt", fake_lookup), \
         patch.object(ans_verify.requests, "get", lambda *a, **k: FakeResp(entry)):
        verify_agent(url)


def mutated(fn):
    e = copy.deepcopy(_entry)
    fn(e["payload"]["producer"]["event"], e)
    return e


def set_status(ev, e): e["status"] = "REVOKED"
def set_expired(ev, e): ev["expiresAt"] = "2020-01-01T00:00:00.000000Z"
def set_host(ev, e): ev["agent"]["host"] = "evil.example"
def drop_attest(ev, e): del ev["attestations"]


ATTACKS = [
    ("Lookalike domain (same server, no ANS record)",
     lambda: verify_agent("https://seller-agent.onrender.com/ask")),
    ("Swapped endpoint path",
     lambda: verify_agent(f"https://{REAL_HOST}/other")),
    ("HTTPS downgrade",
     lambda: verify_agent(f"http://{REAL_HOST}/ask")),
    ("Badge points at attacker-controlled log",
     lambda: attempt(REAL_URL, badge={"url": "https://evil.example/v1/agents/x", "version": "v1.0.0"})),
    ("Copied identity on attacker domain",
     lambda: attempt("https://evil.example/ask")),
    ("Badge/agent ID mismatch",
     lambda: attempt(REAL_URL, badge={**_badge, "url": "https://transparency.ans.godaddy.com/v1/agents/00000000-0000-0000-0000-000000000000"})),
    ("Revoked agent",
     lambda: attempt(REAL_URL, entry=mutated(set_status))),
    ("Expired registration",
     lambda: attempt(REAL_URL, entry=mutated(set_expired))),
    ("Log entry claims a different host",
     lambda: attempt(REAL_URL, entry=mutated(set_host))),
    ("Truncated/malformed log entry",
     lambda: attempt(REAL_URL, entry=mutated(drop_attest))),
]

if __name__ == "__main__":
    failures = 0
    for name, fn in ATTACKS:
        ans_verify._cache.clear()
        try:
            fn()
            verdict, detail = "VULNERABLE", "attack was accepted"
        except ANSVerificationError as e:
            verdict, detail = "BLOCKED", str(e)
        except Exception as e:
            verdict, detail = "INCONCLUSIVE", f"{type(e).__name__}: {e}"
        if verdict != "BLOCKED":
            failures += 1
        print(f"[{verdict:12}] {name}\n               {detail}")
    print(f"\n{len(ATTACKS) - failures}/{len(ATTACKS)} blocked")
    sys.exit(1 if failures else 0)