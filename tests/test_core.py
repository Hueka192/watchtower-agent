import os, sys
from datetime import date, datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("RFQ_OVERRIDE_TO", "me@example.com")

from watchtower import risk, confidence, action, signals, store_loader
from watchtower.data import DEMO_STORE

TODAY = date(2026, 1, 1)
S = {"sku": "X", "name": "x", "on_hand": 300, "sales_7d": 70, "sales_14d": 140, "sales_30d": 300,
     "lead_time_days": 20, "unit_cost": 10.0, "price": 30.0, "supplier": "s", "country": "CN",
     "hts": "6306.22", "lane": "transpac-la"}


def test_velocity_and_cover():
    assert abs(risk.velocity(S) - 10.0) < 1e-9
    assert risk.cover_days(S) == 30.0


def test_gap_and_status():
    ok = risk.assess(S, 0, 0, TODAY)
    assert ok["gap"] == -10.0 and ok["status"] == "OK"
    hit = risk.assess(S, 14, 0, TODAY)
    assert hit["gap"] == 4.0 and hit["status"] == "AT RISK"
    assert hit["stockout"] == "2026-01-31" and hit["lost_units"] == 40


def test_tariff_margin():
    r = risk.assess(S, 0, 15, TODAY)
    assert r["margin_before"] == 20.0 and r["margin_after"] == 18.5


def test_zero_velocity_is_safe():
    z = dict(S, sales_7d=0, sales_14d=0, sales_30d=0)
    assert risk.assess(z, 30, 0, TODAY)["cover_days"] is None


def test_signal_matching():
    sig = signals.demo_event("portclosure")
    rows = risk.evaluate_signal(DEMO_STORE, sig, TODAY)
    assert {r["sku"] for r in rows} == {"TENT-2P", "STOVE-1"}
    tar = risk.evaluate_signal(DEMO_STORE, signals.demo_event("tariff"), TODAY)
    assert {r["sku"] for r in tar} == {"TENT-2P", "STOVE-1"} and tar[0]["tariff_pct"] == 15.0


def test_dedupe_merges_sources():
    st = signals.SignalStore()
    a = signals.demo_event("redsea")
    st.ingest(a)
    b = signals.demo_event("redsea"); b["sources"] = [{"name": "New", "url": "https://x.com/n", "tier": "wire",
                                                       "published": signals.now_iso()}]
    sig, changed = st.ingest(b)
    assert changed and len(sig["sources"]) == 4 and len(st.signals) == 1


def test_confidence_orders_sensibly():
    strong = confidence.score(signals.demo_event("redsea"))["total"]
    weak_sig = {"sources": [{"name": "b", "url": "https://blog.x/a", "tier": "blog",
                             "published": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()}]}
    weak = confidence.score(weak_sig)
    assert strong > weak["total"] and "single source" in weak["notes"]
    deg = confidence.score(dict(signals.demo_event("redsea"), degraded=True))["total"]
    assert deg < strong


def test_plan_and_outbox_fallback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path); monkeypatch.delenv("SMTP_HOST", raising=False)
    sku = DEMO_STORE["skus"][0]
    plan = action.plan(sku, signals.demo_event("tariff"), "Northwind")
    assert len(plan["rfqs"]) == 3 and plan["options"][0]["landed"] <= plan["options"][-1]["landed"]
    cur = next(o for o in plan["options"] if o["current"])
    assert cur["duty_pct"] == 40.0  # 25 base + 15 tariff shock
    res = action.send_all(plan["rfqs"])
    assert all(r["status"] == "queued-to-outbox" for r in res) and len(list((tmp_path / "outbox").iterdir())) == 3


def test_csv_loader():
    csv_text = "sku,name,on_hand,sales_7d,sales_14d,sales_30d,lead_time_days,unit_cost,price,supplier,country,hts,lane\nA,Thing,10,7,14,30,20,1.5,5,Acme,CN,6306.22,transpac-la"
    s = store_loader.from_csv(csv_text)
    assert s["skus"][0]["on_hand"] == 10 and s["skus"][0]["unit_cost"] == 1.5
