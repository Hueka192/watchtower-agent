"""Inventory adapters. Shopify is the real adapter; CSV paste is the universal fallback.
QuickBooks / WooCommerce would implement the same `load()` -> store dict interface (roadmap)."""
import csv
import io
import os

import httpx

COLUMNS = ["sku", "name", "on_hand", "sales_7d", "sales_14d", "sales_30d", "lead_time_days",
           "unit_cost", "price", "supplier", "country", "hts", "lane"]
INT = {"on_hand", "sales_7d", "sales_14d", "sales_30d", "lead_time_days"}
FLOAT = {"unit_cost", "price"}


def from_csv(text: str, store_name: str = "My Store") -> dict:
    rows = csv.DictReader(io.StringIO(text.strip()))
    skus = []
    for r in rows:
        s = {}
        for c in COLUMNS:
            v = (r.get(c) or "").strip()
            s[c] = int(v) if c in INT else float(v) if c in FLOAT else v
        skus.append(s)
    if not skus:
        raise ValueError("no rows parsed")
    return {"store_name": store_name, "skus": skus}


def shopify_inventory(shop: str | None = None, token: str | None = None) -> list[dict]:
    """Read inventory levels via Admin REST API (needs read_inventory + read_products scopes).
    Sales velocity should come from /orders.json aggregation - left as TODO; supplier-side fields
    (lead time, cost, HTS, lane) are merged from a mapping the user provides at onboarding."""
    shop, token = shop or os.getenv("SHOPIFY_SHOP"), token or os.getenv("SHOPIFY_TOKEN")
    if not (shop and token):
        raise RuntimeError("SHOPIFY_SHOP / SHOPIFY_TOKEN not set")
    r = httpx.get(f"https://{shop}/admin/api/2024-10/products.json", headers={"X-Shopify-Access-Token": token}, timeout=10)
    r.raise_for_status()
    return r.json().get("products", [])
