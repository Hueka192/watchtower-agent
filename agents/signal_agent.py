"""Signal Agent: event-driven ingestion (REST webhook) + scheduled live-feed polling.
Normalizes -> dedupes -> pushes AlertNotice to the Concierge the moment something new arrives."""
import json

from uagents import Agent, Context

from watchtower.config import CONCIERGE_ADDR, POLL_MINUTES, SIGNAL_SEED
from watchtower.models import AlertNotice, SignalAck, SignalIn
from watchtower.signals import STORE, fetch_live, now_iso

agent = Agent(name="watchtower-signal", seed=SIGNAL_SEED)


async def _drain(ctx: Context):
    while not STORE.queue.empty():
        sig = STORE.signals[STORE.queue.get_nowait()]
        await ctx.send(CONCIERGE_ADDR, AlertNotice(signal=json.dumps(sig)))


@agent.on_rest_post("/signals", SignalIn, SignalAck)
async def webhook(ctx: Context, req: SignalIn) -> SignalAck:
    """Any external system (MarineTraffic, customs broker, Zapier...) can POST events here."""
    sig = dict(kind=req.kind, title=req.title, summary=req.summary, lanes=req.lanes,
               hts_prefixes=req.hts_prefixes, origin_countries=req.origin_countries,
               delay_days=req.delay_days, tariff_pct=req.tariff_pct,
               sources=[{"name": req.source_name, "url": req.source_url, "tier": req.source_tier,
                         "published": now_iso()}])
    sig, _ = STORE.ingest(sig)
    await _drain(ctx)
    return SignalAck(ok=True, id=sig["id"])


@agent.on_interval(period=POLL_MINUTES * 60)
async def poll(ctx: Context):
    sigs, notes = await fetch_live()
    for n in notes:
        ctx.logger.warning(n)
    for s in sigs:
        STORE.ingest(s)
    await _drain(ctx)


if __name__ == "__main__":
    agent.run()
