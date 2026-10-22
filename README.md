# Supply Chain Watchtower (ASI:One Agent Challenge)

Small importers learn about disruptions after their competitors do. Watchtower turns shipping, port, weather and
tariff events into **your SKU-level stockout dates**, then drafts backup-supplier RFQs that you approve — all inside one ASI:One chat.

## Agents
| Agent | Role |
|---|---|
| **Concierge** (`agents/concierge.py`) | ASI:One-facing, implements Agent Chat Protocol, intent routing, approvals, proactive alerts |
| **Signal** (`agents/signal_agent.py`) | Event-driven ingestion: `POST /signals` webhook + NWS/GDELT polling, dedupe, source merging |
| **Risk** (`agents/risk_agent.py`) | Run-out dates, exposure gap, margin impact, what-if simulation (deterministic math) |
| **Action** (`agents/action_agent.py`) | Landed-cost comparison, RFQ drafting, send-after-approval |

Specialists are called over uAgents messages. If one is unreachable or errors, the Concierge **recovers by running
the same tool in-process** and says so in the reply (visible error recovery).

## Core math (`watchtower/risk.py`)
- velocity = 0.5·(7d/7) + 0.3·(14d/14) + 0.2·(30d/30) · cover = on_hand / velocity
- **exposure gap = (lead time + delay) − cover** · gap > 0 → you stock out before restock lands
- Confidence = 40% source authority + 25% corroboration + 20% recency (48h half-life) + 15% lane/SKU match; shown with citations.

## Run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set unique seeds
python -m pytest -q tests   # unit tests
python run.py               # starts all 4 agents (port 8000)
```
1. The console prints an **Agent inspector link** for `watchtower-concierge`: open it → **Connect → Mailbox**. This registers it on Agentverse.
2. On Agentverse, open the agent → fill in the **README/description** and keywords (e.g. "supply chain, inventory, tariffs, RFQ") so ASI:One can discover it.
3. In ASI:One, select/mention the agent and chat.

If the Bureau + mailbox combo misbehaves on your SDK version, run the Concierge alone: `python -m agents.concierge`.
It works standalone because every tool has the in-process fallback (you lose only the webhook/polling agent).

## Demo script (3 min)
`demo` → `status` → `inject portclosure` (alert w/ gap, margin, confidence, sources) → `sources` →
`what if delay +10 tariff +15` → `rfq` → `approve` → `fetch live fail` (feed outage, graceful degrade).

Webhook test: `curl -X POST localhost:8000/signals -H 'content-type: application/json' -d '{"title":"Suez closure","lanes":["asia-europe"],"delay_days":14,"source_tier":"wire","source_url":"https://reuters.com/x"}'`
(connected users receive a proactive alert).

## Known gaps / roadmap
- **ASI1 Interactive Cards**: output is markdown now; `watchtower/render.py` is the single place to swap in card payloads.
- **Payment Protocol**: not implemented. Plan: free monitoring, per-RFQ-batch fee or Pro tier.
- Shopify adapter reads products only; sales velocity from `/orders.json` and QuickBooks/WooCommerce adapters are TODO. CSV paste works today.
- Duty rates in `data.py` are placeholders; wire in USITC HTS data. Supplier emails are fake (`RFQ_OVERRIDE_TO` routes to you; no SMTP → `./outbox/`).
- Freight pooling is roadmap (needs a user network).
