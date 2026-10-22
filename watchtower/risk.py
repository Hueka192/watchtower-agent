"""Deterministic stockout / exposure math. No LLM involved, so numbers are defensible."""
from datetime import date, timedelta
from math import inf

W7, W14, W30 = 0.5, 0.3, 0.2


def velocity(s: dict) -> float:
    """Weighted units/day from trailing 7/14/30-day totals."""
    return W7 * s["sales_7d"] / 7 + W14 * s["sales_14d"] / 14 + W30 * s["sales_30d"] / 30


def cover_days(s: dict) -> float:
    v = velocity(s)
    return inf if v <= 0 else s["on_hand"] / v


def assess(s: dict, delay: int = 0, tariff_pct: float = 0.0, today: date | None = None) -> dict:
    """exposure gap = (lead time + delay) - days of cover. >0 means you run out before restock lands."""
    today = today or date.today()
    v, c = velocity(s), cover_days(s)
    lead = s["lead_time_days"] + delay
    gap = lead - c
    new_cost = s["unit_cost"] * (1 + tariff_pct / 100)
    lost_units = max(0.0, gap) * v
    status = "OK" if gap <= 0 else ("AT RISK" if gap < 7 else "STOCKOUT")
    return {
        "sku": s["sku"], "name": s["name"], "velocity": round(v, 2),
        "cover_days": None if c == inf else round(c, 1),
        "lead_days": lead, "delay": delay, "gap": None if c == inf else round(gap, 1),
        "stockout": None if c == inf else (today + timedelta(days=int(c))).isoformat(),
        "arrival": (today + timedelta(days=lead)).isoformat(),
        "margin_before": round(s["price"] - s["unit_cost"], 2),
        "margin_after": round(s["price"] - new_cost, 2),
        "lost_units": round(lost_units), "lost_margin": round(lost_units * (s["price"] - new_cost)),
        "status": status,
    }


def matches(s: dict, sig: dict) -> bool:
    lane_hit = s.get("lane") in (sig.get("lanes") or [])
    hts_hit = any(s["hts"].replace(".", "").startswith(p.replace(".", ""))
                  for p in sig.get("hts_prefixes") or [])
    return lane_hit or hts_hit


def evaluate_signal(store: dict, sig: dict, today: date | None = None) -> list[dict]:
    rows = []
    for s in store["skus"]:
        if not matches(s, sig):
            continue
        tariff = sig.get("tariff_pct", 0.0) if s["country"] in (sig.get("origin_countries") or []) else 0.0
        delay = sig.get("delay_days", 0) if s.get("lane") in (sig.get("lanes") or []) else 0
        r = assess(s, delay, tariff, today)
        r["tariff_pct"] = tariff
        rows.append(r)
    return sorted(rows, key=lambda r: -(r["gap"] if r["gap"] is not None else -999))


def whatif(store: dict, delay: int = 0, tariff: float = 0.0, today: date | None = None) -> dict:
    base = [assess(s, 0, 0, today) for s in store["skus"]]
    scen = [assess(s, delay, tariff, today) for s in store["skus"]]
    return {"delay": delay, "tariff": tariff, "base": base, "scenario": scen}
