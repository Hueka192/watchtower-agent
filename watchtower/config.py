import os
from dotenv import load_dotenv
from uagents.crypto import Identity

load_dotenv()

CONCIERGE_SEED = os.getenv("CONCIERGE_SEED", "change-me-concierge")
SIGNAL_SEED = os.getenv("SIGNAL_SEED", "change-me-signal")
RISK_SEED = os.getenv("RISK_SEED", "change-me-risk")
ACTION_SEED = os.getenv("ACTION_SEED", "change-me-action")


def addr(seed: str) -> str:
    return Identity.from_seed(seed, 0).address


CONCIERGE_ADDR = addr(CONCIERGE_SEED)
SIGNAL_ADDR = addr(SIGNAL_SEED)
RISK_ADDR = addr(RISK_SEED)
ACTION_ADDR = addr(ACTION_SEED)
POLL_MINUTES = int(os.getenv("POLL_MINUTES", "15"))
