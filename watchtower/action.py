"""Action tools: landed-cost comparison, RFQ drafting, send-with-fallback."""
import math
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from .data import BACKUPS, DUTY
from .risk import velocity

COVER_TARGET_DAYS = 60


def landed_cost(unit_cost: float, country: str, freight: float, extra_duty_pct: float = 0.0) -> dict:
    duty = DUTY.get(country, 15.0) + extra_duty_pct
    total = unit_cost * (1 + duty / 100) + freight
    return {"duty_pct": duty, "landed": round(total, 2)}


def plan(sku: dict, sig: dict, store_name: str) -> dict:
    """Compare current supplier (under the disruption) vs pre-vetted backups; draft RFQs (not sent)."""
    delay = sig.get("delay_days", 0) if sku.get("lane") in (sig.get("lanes") or []) else 0
    extra = sig.get("tariff_pct", 0.0) if sku["country"] in (sig.get("origin_countries") or []) else 0.0
    cur = landed_cost(sku["unit_cost"], sku["country"], 1.5, extra)
    options = [{"name": f'{sku["supplier"]} (current)', "country": sku["country"], "landed": cur["landed"],
                "duty_pct": cur["duty_pct"], "lead_days": sku["lead_time_days"] + delay, "moq": None,
                "email": None, "current": True}]
    qty_target = math.ceil(velocity(sku) * COVER_TARGET_DAYS)
    rfqs = []
    for b in BACKUPS.get(sku["hts"].replace(".", "")[:4], []):
        lc = landed_cost(b["unit_cost"], b["country"], b["freight_per_unit"])
        qty = max(qty_target, b["moq"])
        options.append({"name": b["name"], "country": b["country"], "landed": lc["landed"],
                        "duty_pct": lc["duty_pct"], "lead_days": b["lead_time_days"], "moq": b["moq"],
                        "email": b["email"], "current": False})
        rfqs.append(draft_rfq(store_name, sku, b, qty, sig))
    options.sort(key=lambda o: o["landed"])
    return {"sku": sku["sku"], "options": options, "rfqs": rfqs, "qty": qty_target}


def draft_rfq(store_name: str, sku: dict, supplier: dict, qty: int, sig: dict) -> dict:
    subject = f'RFQ: {qty} x {sku["name"]} (HTS {sku["hts"]}) - {store_name}'
    body = (f"Hello {supplier['name']} team,\n\n"
            f"{store_name} is qualifying additional suppliers for {sku['name']} (HTS {sku['hts']}).\n"
            f"Please quote for {qty} units: unit price, MOQ, production + shipping lead time, "
            f"payment terms, and an available sample.\n\n"
            f"Context: supply-chain disruption on our current lane ({sig.get('title', 'n/a')}); "
            f"we are looking to place an initial order within 2 weeks if terms fit.\n\n"
            f"Best regards,\nProcurement, {store_name}")
    return {"to": supplier["email"], "supplier": supplier["name"], "subject": subject, "body": body}


def send_all(rfqs: list[dict]) -> list[dict]:
    """Send via SMTP if configured; on ANY failure fall back to writing ./outbox/*.txt so nothing is lost."""
    results = []
    host = os.getenv("SMTP_HOST")
    override = os.getenv("RFQ_OVERRIDE_TO")
    for r in rfqs:
        to = override or r["to"]
        status = "queued-to-outbox"
        if host:
            try:
                m = EmailMessage()
                m["From"], m["To"], m["Subject"] = os.getenv("RFQ_FROM", "procurement@example.com"), to, r["subject"]
                m.set_content(r["body"])
                with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=10) as s:
                    s.starttls()
                    if os.getenv("SMTP_USER"):
                        s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS", ""))
                    s.send_message(m)
                status = "sent"
            except Exception as e:  # noqa: BLE001
                status = f"smtp failed ({type(e).__name__}); saved to outbox"
        if status != "sent":
            out = Path("outbox")
            out.mkdir(exist_ok=True)
            fn = out / f'{datetime.now():%Y%m%d-%H%M%S}-{r["supplier"].replace(" ", "_")}.txt'
            fn.write_text(f"To: {to}\nSubject: {r['subject']}\n\n{r['body']}\n")
        results.append({"supplier": r["supplier"], "to": to, "status": status})
    return results
