"""Concierge Agent: the ASI:One-facing agent. Implements the Agent Chat Protocol (ACP),
routes intents, orchestrates Risk/Action agents (with local fallback), and pushes proactive alerts."""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement, ChatMessage, StartSessionContent, TextContent, chat_protocol_spec,
)

from watchtower import render, signals, store_loader
from watchtower.config import ACTION_ADDR, CONCIERGE_SEED, RISK_ADDR
from watchtower.data import DEMO_STORE
from watchtower.models import AlertNotice, ToolRequest, ToolResponse
from watchtower.tools import TOOLS

agent = Agent(name="watchtower-concierge", seed=CONCIERGE_SEED, port=8000, mailbox=True,
              publish_agent_details=True)
chat = Protocol(spec=chat_protocol_spec)


@dataclass
class Session:
    store: dict | None = None
    last_signal: dict | None = None
    pending_plan: dict | None = None
    history: list = field(default_factory=list)


SESSIONS: dict[str, Session] = {}


def _msg(text: str) -> ChatMessage:
    return ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(),
                       content=[TextContent(type="text", text=text)])


async def call_tool(ctx: Context, dest: str, op: str, payload: dict):
    """Ask a specialist agent; on timeout/error recover by running the same tool in-process."""
    try:
        reply, _ = await ctx.send_and_receive(dest, ToolRequest(op=op, payload=json.dumps(payload)),
                                              response_type=ToolResponse, timeout=8)
        if isinstance(reply, ToolResponse) and reply.ok:
            return json.loads(reply.result), False
        ctx.logger.warning(f"{op}: specialist returned {reply!r}; using local fallback")
    except Exception as e:  # noqa: BLE001
        ctx.logger.warning(f"{op}: specialist unreachable ({e}); using local fallback")
    return TOOLS[op](payload), True


async def push_alert(ctx: Context, to: str, sess: Session, sig: dict):
    rows, fallback = await call_tool(ctx, RISK_ADDR, "risk.evaluate", {"store": sess.store, "signal": sig})
    sess.last_signal = sig
    sess.pending_plan = None
    await ctx.send(to, _msg(render.alert(sig, rows, fallback)))


def _num(pattern: str, text: str, default=0.0):
    m = re.search(pattern, text)
    return float(m.group(1)) if m else default


async def route(ctx: Context, sender: str, text: str) -> str | None:
    sess = SESSIONS.setdefault(sender, Session())
    t = text.lower().strip()

    if t.startswith("sku,") or "\nsku," in t:                         # pasted CSV
        try:
            sess.store = store_loader.from_csv(text)
            return f'✅ Loaded {len(sess.store["skus"])} SKUs. Type `status`.'
        except Exception as e:  # noqa: BLE001
            return f"Couldn't parse that CSV ({e}). Check the header row; type `help` for the format."
    if t in {"demo", "load demo", "onboard"}:
        sess.store = DEMO_STORE
        return f'✅ Connected demo store **{DEMO_STORE["store_name"]}** ({len(DEMO_STORE["skus"])} SKUs). Monitoring is ON; I will message you proactively. Try `status`, then `inject portclosure`.'
    if t in {"help", "hi", "hello", ""}:
        return render.HELP
    if not sess.store:
        return "I need inventory first. Type `demo` for a sample store, or paste CSV (see `help`)."

    if t in {"status", "inventory", "stock"}:
        from watchtower.risk import assess
        return "### 📦 Inventory cover\n" + render.status_table([assess(s) for s in sess.store["skus"]])

    if t.startswith("inject"):
        sig = signals.demo_event(t.replace("inject", "").strip())
        if not sig:
            return "Options: `inject redsea`, `inject portclosure`, `inject tariff`."
        sig, _ = signals.STORE.ingest(sig)
        while not signals.STORE.queue.empty():
            signals.STORE.queue.get_nowait()                          # handled inline below
        await push_alert(ctx, sender, sess, sig)
        return None

    if t.startswith("fetch live"):
        sigs, notes = await signals.fetch_live("nws" if "fail" in t else None)
        for s in sigs:
            sig, _ = signals.STORE.ingest(s)
            await push_alert(ctx, sender, sess, sig)
        while not signals.STORE.queue.empty():
            signals.STORE.queue.get_nowait()
        msg = "### 📡 Live feed check\n" + ("\n".join(f"- ⚠️ {n}" for n in notes) or "- All feeds healthy")
        return msg + f"\n- {len(sigs)} relevant event(s) found" + ("" if sigs else " for monitored lanes right now. Use `inject` for a demo event.")

    if re.search(r"what[\s-]?if", t):
        res, _ = await call_tool(ctx, RISK_ADDR, "risk.whatif", {
            "store": sess.store, "delay": int(_num(r"delay\s*\+?(-?\d+)", t, 0)),
            "tariff": _num(r"tariff\s*\+?(-?\d+(?:\.\d+)?)", t, 0.0)})
        return render.whatif(res)

    if t in {"sources", "why", "confidence"}:
        return render.confidence_block(sess.last_signal) if sess.last_signal else "No alert yet. Try `inject portclosure`."

    if t == "rfq":
        if not sess.last_signal:
            return "No active disruption. Run `inject portclosure` first."
        rows, _ = await call_tool(ctx, RISK_ADDR, "risk.evaluate", {"store": sess.store, "signal": sess.last_signal})
        if not rows:
            return "None of your SKUs are exposed, so no RFQs are needed."
        worst = next(s for s in sess.store["skus"] if s["sku"] == rows[0]["sku"])
        plan, fallback = await call_tool(ctx, ACTION_ADDR, "action.plan", {
            "sku": worst, "signal": sess.last_signal, "store_name": sess.store["store_name"]})
        sess.pending_plan = plan
        return render.rfq_plan(plan) + ("\n\n_Action agent unreachable: computed locally._" if fallback else "")

    if t == "approve":
        if not sess.pending_plan or not sess.pending_plan["rfqs"]:
            return "Nothing pending approval. Type `rfq` first."
        res, _ = await call_tool(ctx, ACTION_ADDR, "action.send", {"rfqs": sess.pending_plan["rfqs"]})
        sess.pending_plan = None
        lines = "\n".join(f'- {r["supplier"]} → {r["to"]}: **{r["status"]}**' for r in res)
        return f"### ✅ RFQs processed\n{lines}\n\nI'll flag replies and landed-cost changes as they come in."
    if t == "cancel":
        sess.pending_plan = None
        return "Cancelled. Nothing was sent."

    return "I didn't catch that.\n\n" + render.HELP


@chat.on_message(ChatMessage)
async def on_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.now(timezone.utc), acknowledged_msg_id=msg.msg_id))
    text = ""
    for c in msg.content:
        if isinstance(c, StartSessionContent):
            text = text or "help"
        elif isinstance(c, TextContent):
            text += c.text
    try:
        reply = await route(ctx, sender, text)
    except Exception:  # noqa: BLE001
        ctx.logger.exception("route failed")
        reply = "Something went wrong on my side. Your data is safe; please retry."
    if reply:
        await ctx.send(sender, _msg(reply))


@chat.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


@agent.on_message(AlertNotice)
async def on_alert(ctx: Context, sender: str, msg: AlertNotice):
    """Event-driven path: Signal Agent -> proactive alert to every monitored user."""
    sig = json.loads(msg.signal)
    for user, sess in SESSIONS.items():
        if sess.store:
            await push_alert(ctx, user, sess, sig)


agent.include(chat, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
