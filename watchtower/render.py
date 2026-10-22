"""Text/markdown renderers for ASI:One chat. Kept separate so an Interactive Cards layer can replace them."""
from . import confidence

ICON = {"OK": "🟢", "AT RISK": "🟠", "STOCKOUT": "🔴"}


def status_table(rows: list[dict]) -> str:
    out = ["| SKU | Cover (days) | Restock lead | Gap | Status |", "|---|---|---|---|---|"]
    for r in rows:
        gap = "n/a" if r["gap"] is None else f'{r["gap"]:+.1f}'
        out.append(f'| {r["sku"]} | {r["cover_days"]} | {r["lead_days"]} | {gap} | {ICON[r["status"]]} {r["status"]} |')
    return "\n".join(out)


def confidence_block(sig: dict) -> str:
    c = confidence.score(sig)
    lines = [f'**Confidence: {confidence.badge(c["total"])} ({c["total"]})** — authority {c["authority"]}, '
             f'corroboration {c["corroboration"]}, recency {c["recency"]}, lane/SKU match {c["match"]}']
    if c["notes"]:
        lines.append("⚠️ " + "; ".join(c["notes"]))
    lines.append("**Sources:**")
    lines += [f'- [{s["name"]}]({s["url"]}) ({s["tier"]})' for s in sig["sources"]]
    return "\n".join(lines)


def alert(sig: dict, rows: list[dict], degraded_local: bool = False) -> str:
    hdr = f'### 🚨 Disruption: {sig["title"]}\n{sig["summary"]}\n'
    if not rows:
        return hdr + "\nNone of your SKUs are exposed to this event."
    body = []
    for r in rows:
        line = (f'- **{r["sku"]}** — on-hand covers **{r["cover_days"]} days** (runs out {r["stockout"]}); '
                f'restock would land in **{r["lead_days"]} days** ({r["arrival"]}).')
        if r["gap"] is not None and r["gap"] > 0:
            line += f' **Exposure gap {r["gap"]:+.1f} days** → ~{r["lost_units"]} units / ${r["lost_margin"]:,} margin at risk.'
        if r.get("tariff_pct"):
            line += f' Margin/unit ${r["margin_before"]} → ${r["margin_after"]} (+{r["tariff_pct"]}% duty).'
        body.append(line)
    tail = "\n\n_Risk agent unreachable: computed locally (fallback)._" if degraded_local else ""
    return (hdr + "\n" + "\n".join(body) + "\n\n" + confidence_block(sig) +
            "\n\nReply **`rfq`** for backup suppliers, **`what if delay +10 tariff +15`** to simulate, or **`sources`** for details." + tail)


def whatif(res: dict) -> str:
    out = [f'### 🔮 What-if: delay **+{res["delay"]}d**, tariff **+{res["tariff"]}%**',
           "| SKU | Gap before → after | Stockout | Margin/unit | Margin at risk |", "|---|---|---|---|---|"]
    for b, s in zip(res["base"], res["scenario"]):
        g0 = "n/a" if b["gap"] is None else f'{b["gap"]:+.1f}'
        g1 = "n/a" if s["gap"] is None else f'{s["gap"]:+.1f}'
        out.append(f'| {s["sku"]} | {g0} → {g1} {ICON[s["status"]]} | {s["stockout"]} | '
                   f'${b["margin_before"]} → ${s["margin_after"]} | ${s["lost_margin"]:,} |')
    return "\n".join(out)


def rfq_plan(plan: dict) -> str:
    out = [f'### 🔁 Backup sourcing for **{plan["sku"]}** (target {plan["qty"]} units ≈ 60 days cover)',
           "| Supplier | Country | Landed $/unit | Duty | Lead (days) | MOQ |", "|---|---|---|---|---|---|"]
    for o in plan["options"]:
        out.append(f'| {o["name"]} | {o["country"]} | ${o["landed"]} | {o["duty_pct"]}% | {o["lead_days"]} | {o["moq"] or "-"} |')
    if plan["rfqs"]:
        r = plan["rfqs"][0]
        out += ["", f'**Draft RFQ preview** (to {r["supplier"]}):', f'> **{r["subject"]}**']
        out += ["> " + ln for ln in r["body"].splitlines()]
        out += ["", f'{len(plan["rfqs"])} RFQs ready. Reply **`approve`** to send all, or **`cancel`**.']
    return "\n".join(out)


HELP = """**Supply Chain Watchtower** — turns shipping/tariff events into *your* stockout dates.

- `demo` — load a sample Shopify-style store
- *(paste CSV)* — header: `sku,name,on_hand,sales_7d,sales_14d,sales_30d,lead_time_days,unit_cost,price,supplier,country,hts,lane`
- `status` — days of cover per SKU
- `inject redsea | portclosure | tariff` — fire a realistic disruption (demo injector)
- `fetch live` / `fetch live fail` — pull NWS + GDELT (second form simulates a feed outage)
- `what if delay +10 tariff +15` — deterministic scenario
- `sources` — confidence breakdown + citations for last alert
- `rfq` → `approve` — compare backup suppliers and send RFQs after your approval"""
