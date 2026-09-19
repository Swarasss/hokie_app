import os

DELOITTE_AGENT_HOST = "0.0.0.0"
DELOITTE_AGENT_PORT = 8000

PARTNER_AGENT_HOST = "0.0.0.0"
PARTNER_AGENT_PORT = 8001

PARTNER_AGENT_URL = os.getenv("PARTNER_AGENT_URL", "https://seller.domainguard.us/ask")
TRUSTED_AGENT_HOSTS = {h for h in os.getenv("TRUSTED_AGENT_HOSTS", "").split(",") if h}