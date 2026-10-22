from agents.specialist import make_specialist
from watchtower.config import ACTION_SEED

agent = make_specialist("watchtower-action", ACTION_SEED, "action.")

if __name__ == "__main__":
    agent.run()
