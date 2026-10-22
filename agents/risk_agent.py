from agents.specialist import make_specialist
from watchtower.config import RISK_SEED

agent = make_specialist("watchtower-risk", RISK_SEED, "risk.")

if __name__ == "__main__":
    agent.run()
