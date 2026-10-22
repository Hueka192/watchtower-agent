"""Message models shared between agents (uAgents Models carry JSON strings for simplicity)."""
from uagents import Model


class ToolRequest(Model):
    op: str          # e.g. "risk.evaluate"
    payload: str     # JSON


class ToolResponse(Model):
    ok: bool
    result: str      # JSON or error text


class AlertNotice(Model):
    signal: str      # JSON of a normalized signal


class SignalIn(Model):
    """Body of POST /signals (webhook for any external feed)."""
    title: str
    kind: str = "shipping"           # shipping | weather | tariff | port
    summary: str = ""
    lanes: list[str] = []
    hts_prefixes: list[str] = []
    origin_countries: list[str] = []
    delay_days: int = 0
    tariff_pct: float = 0.0
    source_name: str = "webhook"
    source_url: str = "https://example.com"
    source_tier: str = "blog"        # gov | wire | trade | blog


class SignalAck(Model):
    ok: bool
    id: str
