"""Run all four agents in one process (shared signal store). Concierge uses mailbox -> Agentverse -> ASI:One."""
from uagents import Bureau

from agents.action_agent import agent as action
from agents.concierge import agent as concierge
from agents.risk_agent import agent as risk
from agents.signal_agent import agent as signal

if __name__ == "__main__":
    bureau = Bureau(port=8000, endpoint="http://localhost:8000/submit")
    for a in (concierge, signal, risk, action):
        bureau.add(a)
    bureau.run()
