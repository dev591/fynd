"""Run the 15 golden buyer sentences against the live model and report accuracy and invented values.

Usage (from api/):  OPENAI_API_KEY=... MODEL_INTAKE=... python3 -m tests.golden.run_live
Target: invented values = 0. Field accuracy is reported per field.
"""
import json
import sys
from datetime import date
from pathlib import Path

from app.ai import ai_enabled
from app.intake import draft_from_text, numbers_in_text
from app.main import store

gold = json.loads((Path(__file__).parent / "intake_cases.json").read_text())
today = date.fromisoformat(gold["today"])

if not ai_enabled():
    sys.exit("Set OPENAI_API_KEY and MODEL_INTAKE first.")

fields = ["item", "qty", "need_in_days", "priority_mode"]
right = {f: 0 for f in fields}
invented = 0
fallbacks = 0
for c in gold["cases"]:
    out = draft_from_text(c["text"], store.catalog_names(), today)
    d = out["draft"]
    fallbacks += out["fallback"]
    for f in fields:
        right[f] += d[f] == c["expect"][f]
    # An invented value is one the buyer's words cannot support. The guard drops them; count survivors.
    if d["qty"] is not None and d["qty"] not in numbers_in_text(c["text"]):
        invented += 1
    if d["item"] and not any(w in c["text"].lower() for w in d["item"].lower().split()[:1]):
        invented += 1
    print(f"{c['tag']:<18} {d}  warnings={out['warnings']}")

n = len(gold["cases"])
print(f"\nfallbacks: {fallbacks}/{n}")
for f in fields:
    print(f"{f:<14} {right[f]}/{n}")
print(f"invented values surviving the guard: {invented} (target 0)")
