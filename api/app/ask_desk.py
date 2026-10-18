"""Ask the desk: a buyer's what-if question becomes engine inputs, the engine recomputes, code writes the answer.

Two readers turn the question into inputs. A rule-based reader works with no AI key. A model can read looser phrasing, but
every value it returns is checked against what the buyer actually wrote and dropped if it is not there. The model never
writes the answer: the sentence is built here from the engine's numbers, so it cannot state a price, date or winner wrongly.
Nothing is saved; the stored request is never changed.
"""
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from .ai import structured_call
from .engine import evaluate
from .intake import numbers_in_text, resolve_need_days
from .models import Need, Quote

MAX_QTY = 1_000_000
MODES = ("cheapest", "fastest", "balanced")

SYSTEM = (
    "A buyer is looking at supplier quotes and asks a what-if question. Turn it into inputs, nothing more. Fill only what "
    "the question explicitly asks to change: qty (units), need_in_days, priority (cheapest, fastest or balanced), and exclude "
    "(sellers who drop out, from the list given). Leave a field null when the question does not mention it. Never invent a "
    "number. Do not answer the question."
)
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["qty", "need_in_days", "priority", "exclude"],
          "properties": {"qty": {"type": ["integer", "null"]}, "need_in_days": {"type": ["integer", "null"]},
                         "priority": {"type": ["string", "null"], "enum": ["cheapest", "fastest", "balanced", None]},
                         "exclude": {"type": "array", "items": {"type": "string"}}}}


@dataclass
class Scenario:
    qty: Optional[int] = None
    need_in_days: Optional[int] = None
    priority: Optional[str] = None
    exclude: List[str] = field(default_factory=list)

    def empty(self) -> bool:
        return self.qty is None and self.need_in_days is None and self.priority is None and not self.exclude

    def dump(self) -> dict:
        return {"qty": self.qty, "need_in_days": self.need_in_days, "priority": self.priority, "exclude": list(self.exclude)}


_IF = re.compile(r"\b(what if|what about|suppose|supposing|if)\b|\?|\b(need|order|want|buy|make it|without|instead)\b", re.I)
_QTY = re.compile(r"(?:need|order|want|buy|get|require|take|for|to)\s+(?:about\s+|around\s+|roughly\s+)?(-?\d[\d,]*)(?!\s*(?:day|week|din|hafte|hour))", re.I)
_QTY_BARE = re.compile(r"(?<![\w/-])(-?\d[\d,]*)\s*(?:units?|pcs?|pieces?|bolts?|nuts?|nos?)\b", re.I)
_HAZAAR = re.compile(r"(\d+)\s*(?:hazaar|hazar|thousand)", re.I)
_DAYS = re.compile(r"(?:in|within|by|inside)\s+(?:about\s+)?(\d+|a|one|two|three|four|five|six|seven)\s*(day|days|week|weeks)", re.I)
_OUT = re.compile(r"\b(out|drop|drops|dropped|without|excluding|exclude|unavailable|backs? out|cancel|cancels|no longer|can't|cannot|unable)\b", re.I)
_ORD = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4, "fifth": 5, "5th": 5}
_ORDINAL = re.compile(r"\b(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th)\s+(?:seller|supplier|one|guy|quote|offer)\b", re.I)
_QTY_WORDS = re.compile(r"((?:(?:one|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|forty|fifty|hundred|thousand)[\s-]*){1,4})\s*(?:units?|pcs?|pieces?|bolts?|nuts?|nos?)?", re.I)
_WORDNUM = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}


def _num(text: str) -> int:
    return int(text.replace(",", ""))


def parse_rules(question: str, aliases: List[str], base_qty: Optional[int] = None, today: Optional[date] = None,
                best_alias: Optional[str] = None) -> Scenario:
    """What the question explicitly changes, read by rules. Anything not clearly there stays None."""
    q = (question or "").strip()
    low = q.lower()
    sc = Scenario()
    if len(low) < 4:
        return sc

    # quantity: "need 300", "order 1,500 units", "2 hazaar", "double", "half"
    m = _HAZAAR.search(low)
    if m:
        sc.qty = int(m.group(1)) * 1000
    else:
        m = _QTY.search(low) or _QTY_BARE.search(low)
        if m:
            sc.qty = _num(m.group(1))
    if sc.qty is None:                                   # "five hundred pieces", "two thousand units"
        mw = _QTY_WORDS.search(low)
        if mw:
            found = [n for n in numbers_in_text(mw.group(1)) if n > 0]
            if len(found) == 1:
                sc.qty = found.pop()
    if sc.qty is None and base_qty:
        if re.search(r"\b(double|twice|2x)\b", low):
            sc.qty = base_qty * 2
        elif re.search(r"\bhalf\b", low):
            sc.qty = max(1, base_qty // 2)
        elif re.search(r"\btriple|3x\b", low):
            sc.qty = base_qty * 3
    if sc.qty is not None and not (0 < sc.qty <= MAX_QTY):
        sc.qty = None

    # deadline: "in 3 days", "within two weeks", "by tomorrow", "by Friday"
    dm = _DAYS.search(low)
    if dm:
        n = _WORDNUM.get(dm.group(1)) or int(dm.group(1))
        sc.need_in_days = n * (7 if dm.group(2).startswith("week") else 1)
    else:
        for phrase in re.findall(r"(?:by|before|till|until)\s+([a-z0-9 ]{3,22})", low):
            d = resolve_need_days(phrase.strip(), today)
            if d:
                sc.need_in_days = d
                break
    if sc.need_in_days is not None and not (0 < sc.need_in_days <= 365):
        sc.need_in_days = None

    # priority
    for mode in MODES:
        if re.search(rf"\b{mode}\b(?!\s+(?:seller|supplier|guy|one|quote|offer)\b)", low):    # "cheapest guy" names a seller
            sc.priority = mode
            break
    if sc.priority is None and re.search(r"\b(quickest|soonest|earliest|asap|urgent)\b", low):
        sc.priority = "fastest"

    # sellers who drop out: only aliases that really exist, and only when the question says they are out
    if _OUT.search(low):
        for a in aliases:
            if re.search(rf"\b{re.escape(a.lower())}\b", low):
                sc.exclude.append(a)
        for m in _ORDINAL.finditer(low):                 # "the second seller", "the 3rd supplier"
            i = _ORD[m.group(1)] - 1
            if 0 <= i < len(aliases) and aliases[i] not in sc.exclude:
                sc.exclude.append(aliases[i])
        if best_alias and best_alias not in sc.exclude and re.search(r"\b(cheapest|best|winner|winning|top|lowest)\b[^.?]{0,20}\b(seller|supplier|guy|one|quote|offer)\b|\bthe (winner|best|cheapest)\b", low):
            sc.exclude.append(best_alias)
    return sc


def _checked(raw: Optional[dict], question: str, aliases: List[str], base_qty: Optional[int]) -> Scenario:
    """A model's reading, kept only where the buyer's own words support it."""
    sc = Scenario()
    if not raw:
        return sc
    low = question.lower()
    spoken = numbers_in_text(question)
    qty, days, pr = raw.get("qty"), raw.get("need_in_days"), raw.get("priority")
    if isinstance(qty, int) and 0 < qty <= MAX_QTY and (qty in spoken or (base_qty and qty in (base_qty * 2, max(1, base_qty // 2), base_qty * 3))):
        sc.qty = qty
    if isinstance(days, int) and 0 < days <= 365 and (days in spoken or days in (7 * n for n in spoken if n < 53)):
        sc.need_in_days = days
    if pr in MODES and re.search(rf"\b{pr}\b", low):
        sc.priority = pr
    for a in raw.get("exclude") or []:
        if a in aliases and a not in sc.exclude and re.search(rf"\b{re.escape(a.lower())}\b", low):
            sc.exclude.append(a)
    return sc


def _baseline_alias(store, rfq, quotes) -> Optional[str]:
    res = evaluate(quotes, Need(item=rfq.item, qty=rfq.qty, need_in_days=rfq.need_in_days), store.exceptions_by_alias(rfq.id), rfq.priority_mode)
    return res.winner.quote_id if res.winner else None


def read_question(question: str, aliases: List[str], base_qty: Optional[int], best_alias: Optional[str] = None) -> Scenario:
    sc = parse_rules(question, aliases, base_qty, best_alias=best_alias)
    if not sc.empty():
        return sc
    # Rules found nothing: let a model try a looser phrasing, then verify it against the words.
    raw = structured_call(SYSTEM, f"Question: {question}\nSellers: {', '.join(aliases)}", "ask_desk", SCHEMA)
    return _checked(raw, question, aliases, base_qty)


def _winner(res) -> Optional[dict]:
    w = res.winner
    return {"winner": w.quote_id, "landed": w.landed, "lead_days": w.lead_days} if w else None


def _inr(n: float) -> str:
    return f"₹{round(n):,}"


def run(store, rfq, question: str) -> Dict[str, Any]:
    quotes: List[Quote] = store.get_latest_quotes_as_engine_input(rfq.id)
    aliases = [q.id for q in quotes]
    sc = read_question(question, aliases, rfq.qty, best_alias=_baseline_alias(store, rfq, quotes))
    if sc.empty() and re.search(r"\d{7,}|\b[1-9]\d{3,}\s*days?\b|\b0\s*days?\b|-\d", question):
        return {"understood": False, "scenario": sc.dump(), "baseline": None, "result": None, "changed": False,
                "sentence": "I can check 1 to 1,000,000 units and 1 to 365 days. Try a smaller number."}
    if sc.empty():
        return {"understood": False, "scenario": sc.dump(), "baseline": None, "result": None, "changed": False,
                "sentence": "I couldn't turn that into a change. Try: “what if I need 300?”, “what if Seller 2 is out?” "
                            "or “what if I need it in 3 days?”."}

    exceptions = store.exceptions_by_alias(rfq.id)
    base_need = Need(item=rfq.item, qty=rfq.qty, need_in_days=rfq.need_in_days)
    base = evaluate(quotes, base_need, exceptions, rfq.priority_mode)
    need = Need(item=rfq.item, qty=sc.qty or rfq.qty, need_in_days=sc.need_in_days or rfq.need_in_days)
    kept = [q for q in quotes if q.id not in sc.exclude]
    res = evaluate(kept, need, exceptions, sc.priority or rfq.priority_mode)

    b, r = _winner(base), _winner(res)
    changed = (b or {}).get("winner") != (r or {}).get("winner")
    asked = []
    if sc.qty:
        asked.append(f"{sc.qty} units")
    if sc.need_in_days:
        asked.append(f"needed in {sc.need_in_days} day{'' if sc.need_in_days == 1 else 's'}")
    if sc.priority:
        asked.append(f"{sc.priority} first")
    if sc.exclude:
        asked.append(f"{' and '.join(sc.exclude)} out")
    lead = f"If {', '.join(asked)}: "
    if r is None:
        sentence = lead + "no seller passes the checks. Approve a late or short seller, or loosen the deadline."
    else:
        now = f"{r['winner']} is best at {_inr(r['landed'])} to your door, arriving in {r['lead_days']} days"
        if not b:
            sentence = lead + now + "."
        elif changed:
            sentence = lead + now + f" (today the best is {b['winner']} at {_inr(b['landed'])} for your current order)."
        else:
            sentence = lead + f"{r['winner']} stays best, at {_inr(r['landed'])}, arriving in {r['lead_days']} days."
    rows = [{"quote_id": x.quote_id, "landed": x.landed, "lead_days": x.lead_days, "status": x.status, "reason": x.reason} for x in res.rows]
    return {"understood": True, "scenario": sc.dump(), "baseline": b, "result": {**(r or {"winner": None, "landed": None, "lead_days": None}), "rows": rows},
            "changed": changed, "sentence": sentence}
