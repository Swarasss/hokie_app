"""Attack battery against the Buyer's ANS verification. Every attack must be BLOCKED."""
import copy
import sys

import ans_verify
from ans_verify import verify_agent, ANSVerificationError

REAL_HOST = "seller.domainguard.us"
REAL_URL = f"https://{REAL_HOST}/ask"
LOOKALIKE_URL = "https://seller-agent.onrender.com/ask"


def run_battery() -> list:
    """Run every attack and return a list of {attack, verdict, detail}."""
    # Real identity material, fetched once and then tampered with per attack
    base_badge = ans_verify._lookup_txt(f"_ans-badge.{REAL_HOST}", "v=ans-badge1")
    base_entry = ans_verify._fetch_log_entry(base_badge["url"])

    def attempt(url, entry=None, badge=None):
        use_entry = base_entry if entry is None else entry
        use_badge = base_badge if badge is None else badge

        def lookup(name, prefix):
            if name.startswith("_ans-badge."):
                return use_badge
            return ans_verify._lookup_txt(name, prefix)

        verify_agent(url, txt_lookup=lookup, fetch_entry=lambda _url: use_entry)

    def mutated(fn):
        entry = copy.deepcopy(base_entry)
        fn(entry["payload"]["producer"]["event"], entry)
        return entry

    def set_status(ev, e): e["status"] = "REVOKED"
    def set_expired(ev, e): ev["expiresAt"] = "2020-01-01T00:00:00.000000Z"
    def set_host(ev, e): ev["agent"]["host"] = "evil.example"
    def drop_attest(ev, e): del ev["attestations"]

    attacks = [
        ("Lookalike domain (same server, no ANS record)",
         lambda: verify_agent(LOOKALIKE_URL)),
        ("Swapped endpoint path",
         lambda: verify_agent(f"https://{REAL_HOST}/other")),
        ("HTTPS downgrade",
         lambda: verify_agent(f"http://{REAL_HOST}/ask")),
        ("Badge points at attacker-controlled log",
         lambda: attempt(REAL_URL, badge={"url": "https://evil.example/v1/agents/x", "version": "v1.0.0"})),
        ("Copied identity on attacker domain",
         lambda: attempt("https://evil.example/ask")),
        ("Badge/agent ID mismatch",
         lambda: attempt(REAL_URL, badge={**base_badge, "url": "https://transparency.ans.godaddy.com/v1/agents/00000000-0000-0000-0000-000000000000"})),
        ("Revoked agent",
         lambda: attempt(REAL_URL, entry=mutated(set_status))),
        ("Expired registration",
         lambda: attempt(REAL_URL, entry=mutated(set_expired))),
        ("Log entry claims a different host",
         lambda: attempt(REAL_URL, entry=mutated(set_host))),
        ("Truncated/malformed log entry",
         lambda: attempt(REAL_URL, entry=mutated(drop_attest))),
    ]

    results = []
    for name, fn in attacks:
        try:
            fn()
            verdict, detail = "VULNERABLE", "attack was accepted"
        except ANSVerificationError as e:
            verdict, detail = "BLOCKED", str(e)
        except Exception as e:
            verdict, detail = "INCONCLUSIVE", f"{type(e).__name__}: {e}"
        results.append({"attack": name, "verdict": verdict, "detail": detail})
    return results


if __name__ == "__main__":
    results = run_battery()
    for r in results:
        print(f"[{r['verdict']:12}] {r['attack']}\n               {r['detail']}")
    blocked = sum(r["verdict"] == "BLOCKED" for r in results)
    print(f"\n{blocked}/{len(results)} blocked")
    sys.exit(0 if blocked == len(results) else 1)