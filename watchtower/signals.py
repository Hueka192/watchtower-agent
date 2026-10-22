"""Signal ingestion: dedupe store, event queue, live feeds (NWS + GDELT) with retry/fallback, demo injector."""
import asyncio
import hashlib
from datetime import datetime, timedelta, timezone

import httpx

UA = {"User-Agent": "watchtower-hackathon (contact: you@example.com)"}
WIRES = {"reuters.com", "apnews.com", "bloomberg.com"}

# (keywords, lane, default delay days)
LANE_KEYWORDS = [
    (("suez", "red sea", "bab el-mandeb"), "asia-europe", 14),
    (("los angeles", "long beach"), "transpac-la", 7),
    (("panama canal",), "transpac-usgc", 10),
]


def now_iso(minus_hours: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=minus_hours)).isoformat()


class SignalStore:
    def __init__(self):
        self.signals: dict[str, dict] = {}
        self.queue: asyncio.Queue = asyncio.Queue()

    def ingest(self, sig: dict) -> tuple[dict, bool]:
        """Dedupe by event key; merge corroborating sources. Returns (signal, changed)."""
        key = sig.get("dedupe_key") or f'{sig["kind"]}:{",".join(sorted(sig["lanes"]))}:{sig["title"][:30]}'
        sig["dedupe_key"] = key
        sig["id"] = hashlib.sha1(key.encode()).hexdigest()[:8]
        existing = self.signals.get(sig["id"])
        if not existing:
            self.signals[sig["id"]] = sig
            self.queue.put_nowait(sig["id"])
            return sig, True
        urls = {s["url"] for s in existing["sources"]}
        new = [s for s in sig["sources"] if s["url"] not in urls]
        if new:
            existing["sources"].extend(new)
            self.queue.put_nowait(existing["id"])
            return existing, True
        return existing, False


STORE = SignalStore()


def _src(name, url, tier, hours_ago=1):
    return {"name": name, "url": url, "tier": tier, "published": now_iso(hours_ago)}


def demo_event(key: str) -> dict | None:
    events = {
        "redsea": dict(kind="shipping", title="Red Sea attacks force carriers to reroute via Cape of Good Hope",
                       summary="Major carriers suspend Suez transits; Asia-Europe transit +14 days.",
                       lanes=["asia-europe"], hts_prefixes=[], origin_countries=[], delay_days=14, tariff_pct=0.0,
                       dedupe_key="demo:redsea",
                       sources=[_src("UKMTO Advisory", "https://www.ukmto.org/advisory-demo", "gov", 3),
                                _src("Reuters", "https://www.reuters.com/demo-redsea", "wire", 2),
                                _src("Lloyd's List", "https://lloydslist.com/demo-redsea", "trade", 1)]),
        "portclosure": dict(kind="port", title="LA/Long Beach terminals halt operations after labor action",
                            summary="Terminal closures expected 5-10 days; vessel queues building offshore.",
                            lanes=["transpac-la"], hts_prefixes=[], origin_countries=[], delay_days=10,
                            tariff_pct=0.0, dedupe_key="demo:portclosure",
                            sources=[_src("Port of Los Angeles Notice", "https://www.portoflosangeles.org/demo-notice", "gov", 2),
                                     _src("AP News", "https://apnews.com/demo-port", "wire", 1)]),
        "tariff": dict(kind="tariff", title="USTR announces +15% duty on tents and camp goods from China",
                       summary="Effective in 10 days; applies to HTS 6306 and 7321.",
                       lanes=[], hts_prefixes=["6306", "7321"], origin_countries=["CN"], delay_days=0,
                       tariff_pct=15.0, dedupe_key="demo:tariff",
                       sources=[_src("USTR Federal Register Notice", "https://www.federalregister.gov/demo-ustr", "gov", 4)]),
    }
    return events.get(key)


# ---------- live feeds ----------
async def _get_json(url, params=None, retries=2, timeout=8.0):
    last = None
    for i in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=UA) as c:
                r = await c.get(url, params=params)
                r.raise_for_status()
                return r.json()
        except Exception as e:  # noqa: BLE001
            last = e
            await asyncio.sleep(0.5 * 2 ** i)
    raise RuntimeError(f"{url} failed after retries: {last}")


def _lane_for(text: str):
    t = text.lower()
    for kws, lane, delay in LANE_KEYWORDS:
        if any(k in t for k in kws):
            return lane, delay
    return None, 0


async def fetch_nws() -> list[dict]:
    data = await _get_json("https://api.weather.gov/alerts/active", {"severity": "Extreme,Severe"})
    out = []
    for f in data.get("features", []):
        p = f["properties"]
        lane, _ = _lane_for(f'{p.get("areaDesc", "")} {p.get("headline", "")}')
        if lane:
            out.append(dict(kind="weather", title=p.get("headline") or p.get("event", "Severe weather"),
                            summary=p.get("event", ""), lanes=[lane], hts_prefixes=[], origin_countries=[],
                            delay_days=3, tariff_pct=0.0, dedupe_key=f"nws:{lane}:{p.get('event')}",
                            sources=[{"name": "NWS", "url": f["id"], "tier": "gov",
                                      "published": p.get("effective") or now_iso()}]))
    return out


async def fetch_gdelt() -> list[dict]:
    q = '(suez OR "red sea" OR "port congestion" OR "port strike" OR "panama canal")'
    data = await _get_json("https://api.gdeltproject.org/api/v2/doc/doc",
                           {"query": q, "mode": "ArtList", "format": "json", "maxrecords": 15, "timespan": "24h"})
    by_lane: dict[str, dict] = {}
    for a in data.get("articles", []):
        lane, delay = _lane_for(a.get("title", ""))
        if not lane:
            continue
        tier = "wire" if a.get("domain") in WIRES else "trade"
        try:
            pub = datetime.strptime(a.get("seendate", ""), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pub = now_iso()
        sig = by_lane.setdefault(lane, dict(kind="shipping", title=a["title"], summary="News-detected disruption",
                                            lanes=[lane], hts_prefixes=[], origin_countries=[], delay_days=delay,
                                            tariff_pct=0.0, dedupe_key=f"gdelt:{lane}", sources=[]))
        sig["sources"].append({"name": a.get("domain", "news"), "url": a["url"], "tier": tier, "published": pub})
    return list(by_lane.values())


async def fetch_live(fail_feed: str | None = None) -> tuple[list[dict], list[str]]:
    """Run all feeds; one failing feed degrades confidence but does not break the pipeline."""
    feeds = {"nws": fetch_nws, "gdelt": fetch_gdelt}
    notes, sigs, failed = [], [], False
    for name, fn in feeds.items():
        try:
            if fail_feed == name:
                raise RuntimeError("simulated timeout")
            sigs.extend(await fn())
        except Exception as e:  # noqa: BLE001
            failed = True
            notes.append(f"{name.upper()} feed unavailable ({e}); continuing with remaining sources")
    if failed:
        for s in sigs:
            s["degraded"] = True
    return sigs, notes
