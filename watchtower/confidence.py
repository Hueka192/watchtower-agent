"""Transparent confidence score: authority 40% + corroboration 25% + recency 20% + match 15%."""
from datetime import datetime, timezone
from urllib.parse import urlparse

TIER = {"gov": 1.0, "wire": 0.75, "trade": 0.55, "blog": 0.30}


def score(sig: dict, now: datetime | None = None, match: float = 1.0) -> dict:
    now = now or datetime.now(timezone.utc)
    srcs = sig["sources"]
    authority = max(TIER.get(s["tier"], 0.3) for s in srcs)
    domains = {urlparse(s["url"]).netloc for s in srcs}
    corroboration = min(len(domains), 3) / 3
    newest = max(datetime.fromisoformat(s["published"]) for s in srcs)
    age_h = max(0.0, (now - newest).total_seconds() / 3600)
    recency = 0.5 ** (age_h / 48)  # 48h half-life
    total = 0.40 * authority + 0.25 * corroboration + 0.20 * recency + 0.15 * match
    notes = []
    if len(domains) == 1:
        notes.append("single source")
    if sig.get("degraded"):
        total *= 0.85
        notes.append("a data feed was unavailable; confidence reduced")
    return {"total": round(total, 2), "authority": round(authority, 2),
            "corroboration": round(corroboration, 2), "recency": round(recency, 2),
            "match": round(match, 2), "notes": notes}


def badge(total: float) -> str:
    return "HIGH" if total >= 0.75 else "MEDIUM" if total >= 0.5 else "LOW"
