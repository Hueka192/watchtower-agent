"""Tool registry. Specialist agents expose these over uAgents messages;
the Concierge falls back to calling them in-process if an agent is unreachable."""
import json

from . import action, risk


def _risk_evaluate(p): return risk.evaluate_signal(p["store"], p["signal"])
def _risk_whatif(p): return risk.whatif(p["store"], p.get("delay", 0), p.get("tariff", 0.0))
def _action_plan(p): return action.plan(p["sku"], p["signal"], p["store_name"])
def _action_send(p): return action.send_all(p["rfqs"])


TOOLS = {"risk.evaluate": _risk_evaluate, "risk.whatif": _risk_whatif,
         "action.plan": _action_plan, "action.send": _action_send}


def dispatch(op: str, payload_json: str) -> str:
    return json.dumps(TOOLS[op](json.loads(payload_json)))
