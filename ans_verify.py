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

import os


ANS_BASE_URL = os.getenv("ANS_BASE_URL", "https://api.godaddy.com")
ANS_API_KEY = os.getenv("ANS_API_KEY")


def resolve_ans_agent(host: str, version: str = "1.0.0") -> dict:
    """Resolve an ANS-registered agent to its registered endpoint."""

    if not ANS_API_KEY:
        raise ANSVerificationError("ANS_API_KEY is not configured")

    response = requests.post(
        f"{ANS_BASE_URL}/v1/agents/resolution",
        headers={
            "Authorization": f"sso-key {ANS_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "agentHost": host,
            "version": version,
        },
        timeout=10,
    )

    if response.status_code != 200:
        raise ANSVerificationError(
            f"ANS resolution failed with HTTP {response.status_code}"
        )

    resolution = response.json()

    details_url = None

    for link in resolution.get("links", []):
        if link.get("rel") == "agent-details":
            details_url = link.get("href")
            break

    if not details_url:
        raise ANSVerificationError("ANS resolution returned no agent-details link")

    details_response = requests.get(
        details_url,
        headers={"Authorization": f"sso-key {ANS_API_KEY}"},
        timeout=10,
    )

    if details_response.status_code != 200:
        raise ANSVerificationError(
            f"Could not retrieve ANS agent details: HTTP {details_response.status_code}"
        )

    details = details_response.json()

    if details.get("agentStatus") != "ACTIVE":
        raise ANSVerificationError(
            f"Resolved agent status is {details.get('agentStatus')}, not ACTIVE"
        )

    endpoints = details.get("endpoints", [])

    if not endpoints:
        raise ANSVerificationError("Resolved agent has no registered endpoint")

    endpoint = endpoints[0].get("agentUrl")

    if not endpoint:
        raise ANSVerificationError("Resolved endpoint is missing its URL")

    return {
        "ans_name": resolution.get("ansName"),
        "agent_id": details.get("agentId"),
        "host": details.get("agentHost"),
        "endpoint": endpoint,
        "protocol": endpoints[0].get("protocol"),
        "status": details.get("agentStatus"),
    }


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


def _fetch_log_entry(log_url: str) -> dict:
    resp = requests.get(log_url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def verify_agent(endpoint_url: str, txt_lookup=None, fetch_entry=None) -> dict:
    """Verify a peer agent. txt_lookup / fetch_entry can be injected for attack tests."""
    injected = txt_lookup is not None or fetch_entry is not None
    lookup = txt_lookup or _lookup_txt
    fetch = fetch_entry or _fetch_log_entry

    if not injected:
        cached = _cache.get(endpoint_url)
        if cached and time.time() - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]

    parsed = urlparse(endpoint_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ANSVerificationError("Endpoint must be an https URL")
    host = parsed.hostname

    # 1. The domain owner must have published an ANS badge record
    badge = lookup(f"_ans-badge.{host}", "v=ans-badge1")
    log_url = badge.get("url", "")
    log = urlparse(log_url)
    if log.scheme != "https" or log.hostname not in TRUSTED_LOG_HOSTS:
        raise ANSVerificationError("Badge points to an untrusted transparency log")

    # 2. Fetch the public transparency log entry
    try:
        entry = fetch(log_url)
    except Exception as e:
        raise ANSVerificationError(f"Could not fetch log entry ({type(e).__name__})")
    if not isinstance(entry, dict):
        raise ANSVerificationError("Log entry is malformed")

    if entry.get("status") != "ACTIVE":
        raise ANSVerificationError(f"Agent status is {entry.get('status')}, not ACTIVE")

    try:
        event = entry["payload"]["producer"]["event"]
        log_host = event["agent"]["host"]
        agent_id = event["ansId"]
        ans_name = event["ansName"]
        expires = event["expiresAt"]
        attest = event["attestations"]
        identity_fp = attest["identityCert"]["fingerprint"]
    except (KeyError, TypeError):
        raise ANSVerificationError("Log entry is missing expected fields")

    # 3. Identity consistency
    if log_host != host:
        raise ANSVerificationError(f"Log entry is for {log_host}, not {host}")
    if not log_url.rstrip("/").endswith(agent_id):
        raise ANSVerificationError("Badge URL does not match the agent ID")
    try:
        expiry = datetime.fromisoformat(expires.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise ANSVerificationError("Log entry has an invalid expiry")
    if expiry <= datetime.now(timezone.utc):
        raise ANSVerificationError("Agent registration has expired")

    # 4. Endpoint must match what was registered, in the log and in live DNS
    try:
        attested_ans = _parse_txt(attest["dnsRecordsProvisioned"][f"_ans.{host}"])
    except (KeyError, TypeError):
        raise ANSVerificationError("Log entry has no attested _ans record for this host")
    if attested_ans.get("url") != endpoint_url:
        raise ANSVerificationError("Endpoint differs from the registered endpoint")
    live = lookup(f"_ans.{host}", "v=ans1")
    if live.get("url") != endpoint_url:
        raise ANSVerificationError("Live DNS endpoint differs from the registered endpoint")

    result = {
        "ans_name": ans_name,
        "agent_id": agent_id,
        "status": "ACTIVE",
        "identity_cert_fingerprint": identity_fp,
        "expires": expires,
    }
    if not injected:
        _cache[endpoint_url] = (time.time(), result)
    return result