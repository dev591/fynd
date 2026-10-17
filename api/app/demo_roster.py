"""Ten demo seller accounts with overlapping catalogs, for testing a live buyer/seller demo.

The seed script (scripts/seed_demo_sellers.py) creates them in Supabase and fills their profile and catalog through the
normal API. The sign-in page lists them as one-click logins only when DEMO_LOGINS=on. These are fictional businesses
made up for the demo."""
import os

DOMAIN = "crossover-demo.test"


def _p(name, price, size, moq, lead, freight, stock, unit="pc", aliases=()):
    return {"name": name, "category": "fasteners", "pack_price": price, "pack_size": size, "moq": moq,
            "usual_lead_days": lead, "freight": freight, "stock": stock, "unit": unit,
            "aliases": list(aliases), "tax_rate": 18, "price_includes_tax": False}


M10 = ["M10 bolt", "M10 hex bolt"]
ROSTER = [
    {"n": "01", "company": "Bolt Express Industrial", "city": "Mumbai", "state": "Maharashtra", "pincode": "400069",
     "products": [_p("M10 Hex Bolt (Grade 8.8)", 10, 1, 1, 3, 200, 5000, aliases=M10), _p("M8 Hex Nut", 2, 1, 1, 3, 150, 9000, aliases=["M8 nut"])]},
    {"n": "02", "company": "Pune Hardware Co.", "city": "Pune", "state": "Maharashtra", "pincode": "411001",
     "products": [_p("M10 Hex Bolt (Standard)", 11, 1, 1, 4, 50, 3000, aliases=M10), _p("M8 Hex Nut", 2.2, 1, 1, 3, 60, 4000, aliases=["M8 nut"])]},
    {"n": "03", "company": "National Bolt Works", "city": "Ahmedabad", "state": "Gujarat", "pincode": "380001",
     "products": [_p("M10 Bolt Box of 50", 400, 50, 50, 7, 0, 8000, unit="box", aliases=M10)]},
    {"n": "04", "company": "Delhi Fasteners", "city": "Delhi", "state": "Delhi", "pincode": "110001",
     "products": [_p("M10 Hex Bolt", 10.5, 1, 1, 3, 120, 6000, aliases=M10), _p("M8 Hex Nut", 1.9, 1, 1, 4, 100, 12000, aliases=["M8 nut"])]},
    {"n": "05", "company": "Chennai Metal Mart", "city": "Chennai", "state": "Tamil Nadu", "pincode": "600001",
     "products": [_p("M10 Bolt Pack of 100", 950, 100, 100, 5, 150, 4000, unit="pack", aliases=M10)]},
    {"n": "06", "company": "Bengaluru Industrial Supply", "city": "Bengaluru", "state": "Karnataka", "pincode": "560001",
     "products": [_p("M10 Hex Bolt", 9.8, 1, 1, 4, 260, 80, aliases=M10)]},            # cheap but only 80 in stock
    {"n": "07", "company": "Jaipur Hardware House", "city": "Jaipur", "state": "Rajasthan", "pincode": "302001",
     "products": [_p("M10 Hex Bolt", 12, 1, 1, 2, 0, 2500, aliases=M10), _p("M8 Hex Nut", 2.5, 1, 1, 2, 0, 3000, aliases=["M8 nut"])]},
    {"n": "08", "company": "Ludhiana Fasteners", "city": "Ludhiana", "state": "Punjab", "pincode": "141001",
     "products": [_p("M10 Bolt Box of 25", 250, 25, 25, 3, 90, 5000, unit="box", aliases=M10), _p("M8 Hex Nut", 2, 1, 1, 3, 90, 7000, aliases=["M8 nut"])]},
    {"n": "09", "company": "Hyderabad Nuts & Bolts", "city": "Hyderabad", "state": "Telangana", "pincode": "500001",
     "products": [_p("M10 Hex Bolt", 10.2, 1, 1, 3, 180, 4500, aliases=M10), _p("M8 Hex Nut", 2.1, 1, 1, 3, 120, 6000, aliases=["M8 nut"])]},
    {"n": "10", "company": "Kolkata Steel Traders", "city": "Kolkata", "state": "West Bengal", "pincode": "700001",
     "products": [_p("M10 Bolt Box of 50", 430, 50, 50, 6, 60, 6000, unit="box", aliases=M10)]},
]


def email_of(s: dict) -> str:
    return f"seller{s['n']}@{DOMAIN}"


def logins_enabled() -> bool:
    return os.environ.get("DEMO_LOGINS", "").lower() in ("on", "true", "1") and bool(os.environ.get("DEMO_SELLER_PASSWORD"))


def profile_payload(s: dict) -> dict:
    """What the sign-up wizard would send for this seller."""
    return {"id": "x", "role": "supplier", "full_name": f"{s['company']} (demo)", "email": email_of(s),
            "phone": f"98200000{s['n']}", "company": s["company"], "business_type": "distributor",
            "state": s["state"], "city": s["city"], "pincode": s["pincode"], "categories": ["fasteners"],
            "verification": {"email": True, "tax_ids_consistent": False, "registry": "none"},
            "supplier": {"default_lead_days": 3, "gst_inclusive_default": False, "regions": [s["state"]]}}


def public_listing() -> list[dict]:
    return [{"email": email_of(s), "company": s["company"], "city": s["city"],
             "items": [f"{p['name']} · ₹{p['pack_price']:g}/{p['unit']}" for p in s["products"]]} for s in ROSTER]
