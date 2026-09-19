"""ANS verification for peer agents. Fails closed."""
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import dns.resolver
import requests

TRUSTED_LOG_HOSTS = {"transparency.ans.godaddy.com"}
CACHE_TTL_SECONDS = 60
_cache: dict = {}


class ANSVerificationError(Exception):
    """The peer agent failed ANS verification. Do not call it."""


def _parse_txt(value: str) -> dict:
    fields = {}
    for part in value.split(";"):
        if "=" in part:
            key, val = part.split("=", 1)
            fields[key.strip()] = val.strip()
    return fields


def _lookup_txt(name: str, prefix: str) -> dict:
    try:
        answers = dns.resolver.resolve(name, "TXT", lifetime=5)
    except Exception as e:
        raise ANSVerificationError(f"No ANS DNS record at {name} ({type(e).__name__})")
    for rdata in answers:
        text = b"".join(rdata.strings).decode()
        if text.startswith(prefix):
            return _parse_txt(text)
    raise ANSVerificationError(f"{name} has no {prefix} record")


def verify_agent(endpoint_url: str) -> dict:
    cached = _cache.get(endpoint_url)
    if cached and time.time() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    parsed = urlparse(endpoint_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ANSVerificationError("Endpoint must be an https URL")
    host = parsed.hostname

    # 1. Domain owner must have published an ANS badge record
    badge = _lookup_txt(f"_ans-badge.{host}", "v=ans-badge1")
    log_url = badge.get("url", "")
    log = urlparse(log_url)
    if log.scheme != "https" or log.hostname not in TRUSTED_LOG_HOSTS:
        raise ANSVerificationError("Badge points to an untrusted transparency log")

    # 2. Fetch the public transparency log entry
    try:
        resp = requests.get(log_url, timeout=10)
        resp.raise_for_status()
        entry = resp.json()
    except Exception as e:
        raise ANSVerificationError(f"Could not fetch log entry ({type(e).__name__})")

    if entry.get("status") != "ACTIVE":
        raise ANSVerificationError(f"Agent status is {entry.get('status')}, not ACTIVE")

    try:
        event = entry["payload"]["producer"]["event"]
        attest = event["attestations"]
        attested_ans = _parse_txt(attest["dnsRecordsProvisioned"][f"_ans.{host}"])
        identity_fp = attest["identityCert"]["fingerprint"]
        agent_id = event["ansId"]
        ans_name = event["ansName"]
        expires = event["expiresAt"]
        log_host = event["agent"]["host"]
    except (KeyError, TypeError):
        raise ANSVerificationError("Log entry is missing expected fields")

    # 3. Identity consistency
    if log_host != host:
        raise ANSVerificationError(f"Log entry is for {log_host}, not {host}")
    if not log_url.rstrip("/").endswith(agent_id):
        raise ANSVerificationError("Badge URL does not match the agent ID")
    expiry = datetime.fromisoformat(expires.replace("Z", "+00:00"))
    if expiry <= datetime.now(timezone.utc):
        raise ANSVerificationError("Agent registration has expired")

    # 4. Endpoint must match what was registered, in the log and in live DNS
    if attested_ans.get("url") != endpoint_url:
        raise ANSVerificationError("Endpoint differs from the registered endpoint")
    live = _lookup_txt(f"_ans.{host}", "v=ans1")
    if live.get("url") != endpoint_url:
        raise ANSVerificationError("Live DNS endpoint differs from the registered endpoint")

    result = {
        "ans_name": ans_name,
        "agent_id": agent_id,
        "status": "ACTIVE",
        "identity_cert_fingerprint": identity_fp,
        "expires": expires,
    }
    _cache[endpoint_url] = (time.time(), result)
    return result