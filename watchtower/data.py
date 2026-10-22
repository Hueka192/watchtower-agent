"""Demo store, backup suppliers, duty table.
DUTY RATES BELOW ARE ILLUSTRATIVE PLACEHOLDERS - replace with USITC HTS lookups before real use."""

DEMO_STORE = {
    "store_name": "Northwind Outdoor Co.",
    "skus": [
        {"sku": "TENT-2P", "name": "2-Person Trail Tent", "on_hand": 480,
         "sales_7d": 140, "sales_14d": 266, "sales_30d": 540, "lead_time_days": 21,
         "unit_cost": 38.0, "price": 99.0, "supplier": "Shenzhen Outfitters",
         "country": "CN", "hts": "6306.22", "lane": "transpac-la"},
        {"sku": "STOVE-1", "name": "Ultralight Camp Stove", "on_hand": 150,
         "sales_7d": 56, "sales_14d": 100, "sales_30d": 210, "lead_time_days": 25,
         "unit_cost": 14.5, "price": 49.0, "supplier": "Ningbo Metalworks",
         "country": "CN", "hts": "7321.11", "lane": "transpac-la"},
        {"sku": "BAG-30L", "name": "30L Daypack", "on_hand": 900,
         "sales_7d": 70, "sales_14d": 150, "sales_30d": 300, "lead_time_days": 35,
         "unit_cost": 11.0, "price": 59.0, "supplier": "Guangzhou Bagworks",
         "country": "CN", "hts": "4202.92", "lane": "asia-europe"},
    ],
}

# country -> duty % (illustrative)
DUTY = {"CN": 25.0, "VN": 8.0, "PT": 6.0, "MX": 0.0, "IN": 10.0}


def _b(name, country, cost, freight, lead, moq, email):
    return {"name": name, "country": country, "unit_cost": cost,
            "freight_per_unit": freight, "lead_time_days": lead, "moq": moq, "email": email}


BACKUPS = {
    "6306": [_b("Hanoi Gear Works", "VN", 41.0, 1.6, 24, 200, "sales@hanoigear.example"),
             _b("Monterrey Outdoor", "MX", 47.0, 0.7, 12, 150, "rfq@monterreyoutdoor.example"),
             _b("Porto Textiles", "PT", 52.0, 0.9, 14, 100, "export@portotextiles.example")],
    "7321": [_b("Pune Metal Products", "IN", 15.8, 1.1, 27, 300, "sales@punemetal.example"),
             _b("Saigon Stoveworks", "VN", 16.2, 0.9, 23, 250, "rfq@saigonstove.example")],
    "4202": [_b("Ho Chi Minh Bags", "VN", 12.0, 0.6, 30, 400, "sales@hcmbags.example"),
             _b("Chennai Luggage", "IN", 12.4, 0.7, 32, 300, "export@chennailuggage.example")],
}
