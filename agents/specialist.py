"""Factory for thin specialist agents (Risk, Action) that serve tools over uAgents messages."""
from uagents import Agent, Context

from watchtower.models import ToolRequest, ToolResponse
from watchtower.tools import TOOLS, dispatch


def make_specialist(name: str, seed: str, prefix: str) -> Agent:
    agent = Agent(name=name, seed=seed)

    @agent.on_message(ToolRequest)
    async def handle(ctx: Context, sender: str, msg: ToolRequest):
        if not msg.op.startswith(prefix) or msg.op not in TOOLS:
            await ctx.send(sender, ToolResponse(ok=False, result=f"unknown op {msg.op}"))
            return
        try:
            await ctx.send(sender, ToolResponse(ok=True, result=dispatch(msg.op, msg.payload)))
        except Exception as e:  # noqa: BLE001
            ctx.logger.exception("tool failed")
            await ctx.send(sender, ToolResponse(ok=False, result=str(e)))

    return agent
