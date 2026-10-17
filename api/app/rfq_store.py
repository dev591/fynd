import os
import uuid
from datetime import datetime, timedelta
from typing import Callable
from typing import Dict, List, Optional
from .models import (
    RFQ,
    RFQCreate,
    QuoteVersion,
    NegotiationTarget,
    Profile,
    Quote,
    SupplierProfileOut,
    SupplierProduct,
    SupplierProductIn,
    SupplierProfileIn,
    ChatMessage,
    Notification,
    NotificationOut,
    Verdict,
    DraftQuote,
    Need,
    BuyerNotice,
    ExceptionRecord,
    Activity,
    AutopilotSettings,
)
from .engine import order
from .intake import item_key
from .engine import evaluate
from .tax import normalise_price
from .assistant import template_message
from . import views
from .masking import scrub
from .matching import draft_quote, matching_product, normalise_item, verdict_for

# Default supplier labels for demo invites
_DEFAULT_SUPPLIERS = [
    ("A", "Supplier A"),
    ("B", "Supplier B"),
    ("C", "Supplier C"),
]


DEFAULT_WINDOW = {"fastest": "15m", "balanced": "today", "cheapest": "24h"}
_WINDOWS = {"15m": ("15 minutes", 15), "24h": ("24 hours", 24 * 60), "3d": ("3 days", 3 * 24 * 60)}


def window_end(key: str, now: datetime) -> tuple[datetime, str, bool]:
    """When a request's window closes. Today means the end of today, but never less than 15 minutes from now.
    DEMO_WINDOW_MINUTES shortens every window for a demo and the label says so."""
    try:
        demo = int(os.environ.get("DEMO_WINDOW_MINUTES", "0"))
    except ValueError:
        demo = 0
    if demo > 0:
        return now + timedelta(minutes=demo), f"Demo timing: {demo} minute{'s' if demo != 1 else ''}", True
    if key == "today":
        end = now.replace(hour=23, minute=59, second=59, microsecond=0)
        return max(end, now + timedelta(minutes=15)), "Today", False
    label, minutes = _WINDOWS.get(key, _WINDOWS["24h"])
    return now + timedelta(minutes=minutes), label, False


class RFQStore:
    """In-memory store. All data is real within a single server process."""

    def __init__(self):
        self.rfqs: Dict[str, RFQ] = {}
        self.token_to_rfq_id: Dict[str, str] = {}
        self.token_to_supplier_id: Dict[str, str] = {}
        self.token_to_supplier_name: Dict[str, str] = {}
        self.quotes: Dict[str, Dict[str, List[QuoteVersion]]] = {}
        self.targets: Dict[str, Dict[str, NegotiationTarget]] = {}
        self.profiles: Dict[str, Profile] = {}
        self.decisions: Dict[str, dict] = {}
        self.supplier_profiles: Dict[str, SupplierProfileOut] = {}
        self.supplier_products: Dict[str, List[SupplierProduct]] = {}
        self.chats: Dict[str, Dict[str, List[ChatMessage]]] = {}
        self.notifications: Dict[str, List[Notification]] = {}  # supplier_id -> inbox
        self.aliases: Dict[str, Dict[str, str]] = {}      # rfq_id -> {supplier_id: "Seller N"}, in order of first quote
        self.revealed: Dict[str, Dict[str, dict]] = {}    # rfq_id -> {supplier_id: {buyer_id, at, kind}}
        self.reveal_log: List[dict] = []                  # every first-time reveal: buyer, seller, request, free/paid/repeat
        self.history: List[dict] = []                     # synthetic past orders, labelled as such
        self.media: Dict[str, dict] = {}                          # rfq -> delivery photo/video, kept apart from the record
        self.buyer_notices: Dict[str, List[BuyerNotice]] = {}   # buyer_id -> their bell
        self.clock: Callable[[], datetime] = datetime.now       # injectable, so tests never wait
        self.known_suppliers: Dict[str, Dict[str, str]] = {}      # rfq -> {imp_id: the name the buyer gave}
        self.exceptions: Dict[str, Dict[str, ExceptionRecord]] = {}   # rfq -> supplier -> written exception
        self.plans: Dict[str, str] = {}                   # buyer_id -> "free" | "pro" (mock billing)
        self.supplier_owner: Dict[str, str] = {}  # supplier_id -> owning user id; demo sellers have none
        self.autopilot: Dict[str, AutopilotSettings] = {}  # supplier_id -> settings; absent means off
        self.shares: Dict[str, str] = {}  # unguessable share token -> rfq_id, created only by an explicit click
        self.assists: Dict[str, dict] = {}  # token -> the draft and wording issued, to label quote origin
        self.ai_log: List[dict] = []  # every AI input and output, linked to the request once confirmed

        self._seed_default_data()
        self._seed_supplier_profiles()
        self._seed_marketplace()
        self._seed_contacts()
        self._seed_history()
        self._seed_autopilot()

    # ─── Seeding ───────────────────────────────────────────────────────

    def _seed_default_data(self):
        """No shared demo request: reveals and quotas are per buyer, so every sample request belongs to one buyer."""

    def create_sample_rfq(self, owner_id: str, company: str, name: str, city: str, state: str) -> RFQ:
        """A personal request with quotes already in, for the empty state and the demo. All of it synthetic."""
        rfq = self.create_rfq(RFQCreate(item="M10 bolt", qty=100, need_in_days=5, buyer_company=company, buyer_name=name,
                                        buyer_city=city, buyer_state=state, note="Sample request (synthetic demo data)."),
                              owner_id=owner_id)
        for sid in ("A", "B", "C"):
            token = rfq.supplier_tokens.get(sid)
            if not token or sid in self.quotes.get(rfq.id, {}):
                continue                                           # a demo seller on autopilot already quoted
            d = self.draft_for_token(token)
            if d:
                self.submit_quote(token=token, supplier_name=self._supplier_name(sid), pack_price=d.pack_price,
                                  pack_size=d.pack_size, freight=d.freight, lead_days=d.lead_days, moq=d.moq,
                                  max_qty=d.max_qty, notes="Sample quote (synthetic demo data).",
                                  tax_rate=d.tax_rate, price_includes_tax=d.price_includes_tax)
        return rfq

    def _seed_supplier_profiles(self):
        self.supplier_profiles["A"] = SupplierProfileOut(
            supplier_id="A", business_name="Bolt Express Industrial Supplies",
            location_city="Mumbai", location_state="Maharashtra",
            categories=["fasteners", "tools"], description="Distributor of high-tensile fasteners since 2012.",
            verification_tier="registry",
        )
        self.supplier_profiles["B"] = SupplierProfileOut(
            supplier_id="B", business_name="Pune Hardware Co.",
            location_city="Pune", location_state="Maharashtra",
            categories=["fasteners", "hardware"], description="Local supplier with same-day delivery in Pune metro.",
            verification_tier="tax_ids",
        )
        self.supplier_profiles["C"] = SupplierProfileOut(
            supplier_id="C", business_name="National Bolt Works",
            location_city="Ahmedabad", location_state="Gujarat",
            categories=["fasteners", "industrial"], description="Bulk manufacturer, box packs available.",
            verification_tier="email",
        )

        self.supplier_products["A"] = [
            SupplierProduct(id="prod_a1", name="M10 Hex Bolt (Grade 8.8 High-Tensile)",
                            category="fasteners", pack_price=10, pack_size=1, moq=50,
                            usual_lead_days=3, unit="pc", stock=500, freight=200,
                            aliases=["M10 bolt", "M10 hex bolt"]),
            SupplierProduct(id="prod_a2", name="M10 Zinc-Plated Box Pack (Box of 50)",
                            category="fasteners", pack_price=450, pack_size=50, moq=50,
                            usual_lead_days=2, unit="box", stock=2000, freight=200,
                            aliases=["M10 box pack"]),
        ]
        self.supplier_products["B"] = [
            SupplierProduct(id="prod_b1", name="M10 Hex Bolt (Standard Grade)",
                            category="fasteners", pack_price=11, pack_size=1, moq=1,
                            usual_lead_days=3, unit="pc", stock=150, freight=50,
                            aliases=["M10 bolt"]),
        ]
        self.supplier_products["C"] = [
            SupplierProduct(id="prod_c1", name="M10 Bolt Box of 50",
                            category="fasteners", pack_price=400, pack_size=50, moq=50,
                            usual_lead_days=7, unit="box", stock=5000, freight=0,
                            aliases=["M10 bolt"]),
        ]

    def _seed_marketplace(self):
        """Synthetic sellers across 3 categories so matching has someone to find. All labelled synthetic."""
        def seller(sid, name, city, state, cats, tier, products):
            self.supplier_profiles[sid] = SupplierProfileOut(
                supplier_id=sid, business_name=name, location_city=city, location_state=state,
                categories=cats, description="Synthetic demo seller.", verification_tier=tier,
                synthetic=True,
            )
            self.supplier_products[sid] = products

        def prod(pid, name, cat, price, size, moq, lead, unit, stock, freight, aliases):
            return SupplierProduct(id=pid, name=name, category=cat, pack_price=price, pack_size=size,
                                   moq=moq, usual_lead_days=lead, unit=unit, stock=stock,
                                   freight=freight, aliases=aliases)

        washer = lambda pid, stock, lead: prod(pid, "M8 Flat Washer", "fasteners", 2, 1, 1, lead, "pc", stock, 80, ["M8 washer"])
        seller("D", "Nashik Fastener Mart (synthetic)", "Nashik", "Maharashtra", ["fasteners"], "tax_ids", [
            prod("prod_d1", "M10 Hex Bolt Zinc", "fasteners", 10.5, 1, 1, 2, "pc", 0, 90, ["M10 bolt"]),
            washer("prod_d2", 3000, 2),
        ])
        seller("E", "Thane Industrial Hub (synthetic)", "Thane", "Maharashtra", ["fasteners"], "email", [
            prod("prod_e1", "M10 Hex Bolt Black", "fasteners", 10.8, 1, 1, 4, "pc", 400, 120, ["M10 bolt"]),
            washer("prod_e2", 1000, 3),
        ])
        for sid, name, city, state, price, stock, lead in [
            ("F", "Vapi Pack Solutions (synthetic)", "Vapi", "Gujarat", 38, 900, 3),
            ("G", "Bhiwandi Cartons (synthetic)", "Bhiwandi", "Maharashtra", 41, 150, 2),
            ("H", "Surat Pack Co (synthetic)", "Surat", "Gujarat", 36, 5000, 6),
        ]:
            seller(sid, name, city, state, ["packaging"], "tax_ids", [
                prod(f"prod_{sid.lower()}1", "5 Ply Corrugated Box", "packaging", price, 1, 50, lead, "pc",
                     stock, 300, ["corrugated box", "5-ply box"]),
            ])
        for sid, name, city, state, price, stock, lead in [
            ("I", "Pune Cable House (synthetic)", "Pune", "Maharashtra", 1450, 40, 2),
            ("J", "Chakan Electricals (synthetic)", "Chakan", "Maharashtra", 1380, 200, 4),
        ]:
            seller(sid, name, city, state, ["electricals"], "registry", [
                prod(f"prod_{sid.lower()}1", "1.5 sq mm Copper Wire 90m Coil", "electricals", price, 1, 1, lead,
                     "coil", stock, 150, ["copper wire", "1.5mm copper wire"]),
            ])


    def _seed_contacts(self):
        """Obviously fake contact details for the synthetic sellers. Released only on reveal."""
        for prods in self.supplier_products.values():
            for prod in prods:                    # demo sellers state their GST: 18%, prices exclude it
                prod.tax_rate, prod.price_includes_tax = 18.0, False
        for sid, prof in self.supplier_profiles.items():
            n = ord(sid[0]) - 64
            prof.contact_name = f"Demo contact {sid} (synthetic)"
            prof.phone = f"+91 90000 {n:05d}"
            prof.email = f"seller-{sid.lower()}@synthetic-demo.test"

    def _seed_history(self):
        """A little synthetic order history, so 'last order vs today' has something honest to show. Labelled synthetic."""
        for item, qty, landed, lead, days_ago in [
            ("M10 bolt", 100, 1320, 4, 21),
            ("5 ply corrugated box", 200, 8900, 5, 30),
            ("1.5 sq mm copper wire", 20, 28800, 6, 14),
        ]:
            when = (datetime.now() - timedelta(days=days_ago)).date().isoformat()
            self.history.append({"item_key": item_key(item), "item": item, "qty": qty, "landed": landed,
                                 "lead_days": lead, "date": when, "synthetic": True})

    def _seed_autopilot(self):
        """Demo sellers answer by themselves so quotes land in seconds. A seller can switch it off. Set
        DEMO_AUTOPILOT=off to start with it off. Autopilot only ever opens a first quote on a clean 'yes'."""
        if os.environ.get("DEMO_AUTOPILOT", "on").lower() == "off":
            return
        for sid, prof in self.supplier_profiles.items():
            if prof.synthetic:
                self.autopilot[sid] = AutopilotSettings(enabled=True)

    def last_order(self, buyer_id: str, item: str) -> Optional[dict]:
        """This buyer's most recent decided order for the item, else the synthetic history entry. Numbers only."""
        key = item_key(item)
        mine = [r for r in self.rfqs.values() if r.owner_id == buyer_id and r.decision and item_key(r.item) == key]
        for r in sorted(mine, key=lambda r: r.decision["decided_at"], reverse=True):
            alias = r.decision["winner_id"]
            sid = self.supplier_for_alias(r.id, alias)
            latest = (self.quotes.get(r.id, {}).get(sid) or [None])[-1] if sid else None
            if latest:
                return {"source": "your_last_order", "label": "Your last order", "date": r.decision["decided_at"][:10],
                        "qty": r.qty, "landed": latest.landed_cost, "lead_days": latest.lead_days}
        hist = [h for h in self.history if h["item_key"] == key]
        if hist:
            h = max(hist, key=lambda h: h["date"])
            return {"source": "synthetic_history", "label": "Synthetic demo history", "date": h["date"],
                    "qty": h["qty"], "landed": h["landed"], "lead_days": h["lead_days"]}
        return None

    def todays_best(self, item: str, qty: int, need_in_days: int = 30) -> Optional[dict]:
        """Best landed cost today across sellers who stock the item, from their catalog rows through the engine.
        Returns numbers only: no seller identity."""
        quotes = []
        for sid, prod in self.match_suppliers(item).items():
            probe = RFQ(id="probe", token="t", item=item, qty=qty, need_in_days=need_in_days, buyer_company="", buyer_name="",
                        buyer_city="", buyer_state="", created_at="")
            d = draft_quote(probe, prod)
            quotes.append(Quote(id=sid, supplier=sid, item=item, pack_price=d.pack_price, pack_size=d.pack_size,
                                freight=d.freight, lead_days=d.lead_days, moq=d.moq, max_qty=d.max_qty))
        if not quotes:
            return None
        res = evaluate(quotes, Need(item=item, qty=qty, need_in_days=need_in_days))
        w = res.winner
        return {"landed": w.landed, "lead_days": w.lead_days, "sellers_checked": len(quotes)} if w else None

    # ─── Aliases, reveal, quota ────────────────────────────────────────

    def exceptions_by_alias(self, rfq_id: str) -> Dict[str, ExceptionRecord]:
        return {self.alias_for(rfq_id, sid): rec for sid, rec in self.exceptions.get(rfq_id, {}).items()
                if self.alias_for(rfq_id, sid)}

    def set_exception(self, rfq_id: str, supplier_id: str, reason: str, approver: str) -> None:
        self.exceptions.setdefault(rfq_id, {})[supplier_id] = ExceptionRecord(reason=reason, approver=approver)

    def clear_exception(self, rfq_id: str, supplier_id: str) -> bool:
        return self.exceptions.get(rfq_id, {}).pop(supplier_id, None) is not None

    @staticmethod
    def is_known(supplier_id: str) -> bool:
        """Imported by the buyer from their own file: they named the supplier, so there is nothing to reveal."""
        return supplier_id.startswith("imp_")

    # ─── Quote windows ─────────────────────────────────────────────────

    def _notice(self, rfq: RFQ, kind: str, message: str) -> bool:
        """Add to the buyer's bell once per request and kind."""
        if not rfq.owner_id:
            return False
        bell = self.buyer_notices.setdefault(rfq.owner_id, [])
        if any(n.rfq_id == rfq.id and n.kind == kind for n in bell):
            return False
        bell.append(BuyerNotice(id="nt_" + uuid.uuid4().hex[:8], rfq_id=rfq.id, kind=kind, message=message,
                                created_at=self.clock().isoformat()))
        return True

    def _best_line(self, rfq: RFQ) -> Optional[str]:
        quotes = self.get_latest_quotes_as_engine_input(rfq.id)
        res = evaluate(quotes, Need(item=rfq.item, qty=rfq.qty, need_in_days=rfq.need_in_days),
                       exceptions=self.exceptions_by_alias(rfq.id), mode=rfq.priority_mode) if quotes else None
        w = res.winner if res else None
        return f"{w.supplier} at ₹{w.landed:,.0f} landed, {w.lead_days} days" if w and w.landed is not None else None

    def _quote_notices(self, rfq: RFQ) -> int:
        """First quote, and enough quotes. Aliases only; no seller is ever named here."""
        n = sum(1 for v in self.quotes.get(rfq.id, {}).values() if v)
        sent = 0
        if n >= 1:
            sent += self._notice(rfq, "first_quote", f"First quote is in for {rfq.item}. " + (self._best_line(rfq) or "It does not pass your gates yet.") + ".")
        if n >= rfq.min_quotes:
            best = self._best_line(rfq)
            sent += self._notice(rfq, "enough_quotes", f"{n} quotes are in for {rfq.item}. " +
                                 (f"Best so far: {best}." if best else "None passes your delivery date yet."))
        return sent

    def _remind(self, rfq: RFQ, which: str, text: str) -> int:
        sent = 0
        answered = set(self.quotes.get(rfq.id, {}))
        for notes in self.notifications.values():
            for n in notes:
                if n.rfq_id == rfq.id and n.supplier_id not in answered and n.status != "declined" and which not in n.reminded:
                    n.reminded.append(which)
                    n.reminder = text
                    sent += 1
        return sent

    def tick(self, now: Optional[datetime] = None) -> int:
        """Run by a background loop every 30 seconds (and by tests with a fake clock). Idempotent: returns how many
        things happened, 0 when nothing new was due."""
        now = now or self.clock()
        events = 0
        for rfq in list(self.rfqs.values()):
            if rfq.status != "Open" or not rfq.window_ends_at or rfq.window_closed:
                continue
            start, ends = datetime.fromisoformat(rfq.created_at), datetime.fromisoformat(rfq.window_ends_at)
            events += self._quote_notices(rfq)
            if now >= ends:
                rfq.window_closed = True
                n = sum(1 for v in self.quotes.get(rfq.id, {}).values() if v)
                best = self._best_line(rfq)
                events += 1 + self._notice(rfq, "window_closed",
                    f"The window for {rfq.item} has closed with {n} quote{'s' if n != 1 else ''}. " +
                    (f"Best option: {best}. Confirm?" if best else "No quote passes your gates, so there is nothing to confirm yet.")
                    if n else f"The window for {rfq.item} has closed and no quote came in.")
                continue
            closes = ends.strftime("%a %d %b, %H:%M")
            if now >= start + (ends - start) / 2:
                events += self._remind(rfq, "halfway", f"Halfway: this request closes {closes} and you haven't answered yet.")
            if ends - start > timedelta(minutes=30) and now >= ends - timedelta(minutes=15):
                events += self._remind(rfq, "final", "Closing in 15 minutes: you haven't answered yet.")
        return events

    def record_delivery(self, rfq_id: str, matches_quote: bool, on_time: bool, note: Optional[str], media) -> dict:
        """The buyer's own record of what arrived. Saved on the decision; a photo or video is stored separately."""
        rfq = self.rfqs[rfq_id]
        record = {
            "matches_quote": matches_quote, "on_time": on_time, "note": (note or "").strip() or None,
            "recorded_at": self.clock().isoformat(), "media": None,
            "disclaimer": "This is your own record. Crossover did not inspect the goods.",
        }
        if media:
            import base64
            self.media[rfq_id] = {"name": media.name, "mime": media.mime, "data": media.data}
            record["media"] = {"name": media.name, "mime": media.mime, "bytes": len(base64.b64decode(media.data))}
        else:
            self.media.pop(rfq_id, None)
        for holder in (rfq.decision, self.decisions.get(rfq_id)):          # same dict until a restart splits them
            if holder is not None:
                holder["delivery"] = record
        return record

    def alias_for(self, rfq_id: str, supplier_id: str, create: bool = False) -> Optional[str]:
        table = self.aliases.setdefault(rfq_id, {}) if create else self.aliases.get(rfq_id, {})
        if supplier_id not in table and create:
            prefix = "Imported" if self.is_known(supplier_id) else "Seller"
            table[supplier_id] = f"{prefix} {sum(1 for a in table.values() if a.startswith(prefix + ' ')) + 1}"
        return table.get(supplier_id)

    def import_quote(self, rfq_id: str, row: dict) -> QuoteVersion:
        """Add one validated row from a buyer's CSV/JSON. Same supplier name again = next version of that supplier."""
        rfq = self.rfqs[rfq_id]
        names = self.known_suppliers.setdefault(rfq_id, {})
        name = row["supplier"].strip()
        sid = next((s for s, n in names.items() if n.lower() == name.lower()), None) or "imp_" + uuid.uuid4().hex[:8]
        names.setdefault(sid, name)
        history = self.quotes.setdefault(rfq_id, {}).setdefault(sid, [])
        self.alias_for(rfq_id, sid, create=True)
        price, basis = normalise_price(row["pack_price"], row["tax_rate"], row["price_includes_tax"], rfq.gst_claimable)
        landed = units = packs = None
        if row["pack_size"]:
            qty = min(rfq.qty, row["max_qty"]) if row["max_qty"] else rfq.qty
            calc = order(Quote(id="x", supplier="x", item=rfq.item, pack_price=price, pack_size=row["pack_size"],
                               freight=row["freight"], lead_days=row["lead_days"], moq=row["moq"]), qty)
            landed, units, packs = (calc.landed, calc.units, calc.packs) if calc else (None, 0, 0)
        different = row["item"] and item_key(row["item"]) != item_key(rfq.item)
        qv = QuoteVersion(
            version=len(history) + 1, supplier_id=sid, supplier_name=name, pack_price=row["pack_price"],
            pack_size=row["pack_size"], freight=row["freight"], lead_days=row["lead_days"], moq=row["moq"],
            max_qty=row["max_qty"], notes=row["notes"], origin="manual", tax_rate=row["tax_rate"],
            price_includes_tax=row["price_includes_tax"], compare_price=price, tax_basis=basis,
            landed_cost=landed, units=units or 0, packs=packs or 0, submitted_at=datetime.now().strftime("%I:%M %p"),
            item=row["item"] if different else None, imported=True,
        )
        history.append(qv)
        self._quote_notices(rfq)
        return qv

    def supplier_for_alias(self, rfq_id: str, alias: str) -> Optional[str]:
        return next((sid for sid, a in self.aliases.get(rfq_id, {}).items() if a == alias), None)

    def is_revealed(self, rfq_id: str, supplier_id: str) -> bool:
        return self.is_known(supplier_id) or supplier_id in self.revealed.get(rfq_id, {})

    @staticmethod
    def free_reveal_limit() -> int:
        try:
            return max(0, int(os.environ.get("FREE_REVEALS", "3")))
        except ValueError:
            return 3

    def plan_of(self, buyer_id: str) -> str:
        return self.plans.get(buyer_id, "free")

    def reveals_used(self, buyer_id: str) -> int:
        return sum(1 for e in self.reveal_log if e["buyer_id"] == buyer_id and e["kind"] == "free")

    def reveals_left(self, buyer_id: str) -> Optional[int]:
        if self.plan_of(buyer_id) == "pro":
            return None
        return max(0, self.free_reveal_limit() - self.reveals_used(buyer_id))

    def _revealed_before(self, buyer_id: str, supplier_id: str) -> bool:
        return any(supplier_id in d and self.rfqs[r].owner_id == buyer_id for r, d in self.revealed.items() if r in self.rfqs)

    def reveal(self, rfq_id: str, supplier_id: str, buyer_id: str) -> Optional[str]:
        """Unlock one seller for one request. Idempotent per (request, seller). Returns the kind
        ("free", "paid", "repeat" or "already"), or None when the free allowance is used up."""
        if self.is_revealed(rfq_id, supplier_id):
            return "already"
        if self._revealed_before(buyer_id, supplier_id):
            kind = "repeat"                       # a seller you already unlocked is free and uses no allowance
        elif self.plan_of(buyer_id) == "pro":
            kind = "paid"
        elif self.reveals_used(buyer_id) < self.free_reveal_limit():
            kind = "free"
        else:
            return None
        now = datetime.now().isoformat()
        self.revealed.setdefault(rfq_id, {})[supplier_id] = {"buyer_id": buyer_id, "at": now, "kind": kind}
        self.reveal_log.append({"buyer_id": buyer_id, "supplier_id": supplier_id, "rfq_id": rfq_id,
                                "alias": self.alias_for(rfq_id, supplier_id), "kind": kind, "at": now})
        for n in self.notifications.get(supplier_id, []):     # tell the seller: a buyer unlocked you
            if n.rfq_id == rfq_id:
                n.unlocked_at, n.status = now, "new"
        return kind

    # ─── Matching & notifications ──────────────────────────────────────

    def _supplier_name(self, sid: str) -> str:
        prof = self.supplier_profiles.get(sid)
        return prof.business_name if prof else dict(_DEFAULT_SUPPLIERS).get(sid, f"Supplier {sid}")

    def match_suppliers(self, item: str) -> Dict[str, SupplierProduct]:
        """supplier_id -> matching catalog row. Exact and alias matches only."""
        found: Dict[str, SupplierProduct] = {}
        for sid, prods in self.supplier_products.items():
            hit = matching_product(item, prods)
            if hit:
                found[sid] = hit
        return found

    def catalog_names(self) -> Dict[str, str]:
        """Plural-insensitive key -> the catalog's own spelling, for snapping intake items to real catalog items."""
        names: Dict[str, str] = {}
        for prods in self.supplier_products.values():
            for p in prods:
                for n in [*p.aliases, p.name]:
                    if n.strip():
                        names.setdefault(item_key(n), n.strip())
        return names

    def log_ai(self, kind: str, request_id: str, inp: dict, out: dict) -> None:
        self.ai_log.append({"request_id": request_id, "kind": kind, "at": datetime.now().isoformat(),
                            "input": inp, "output": out, "rfq_id": None})

    def link_ai_log(self, request_id: str, rfq_id: str) -> None:
        for e in self.ai_log:
            if e["request_id"] == request_id:
                e["rfq_id"] = rfq_id

    def ai_log_for(self, rfq_id: str) -> List[dict]:
        return [e for e in self.ai_log if e["rfq_id"] == rfq_id]

    def _notify(self, rfq: RFQ, matches: Dict[str, SupplierProduct]) -> None:
        for sid, prod in matches.items():
            self.notifications.setdefault(sid, []).append(Notification(
                id="ntf_" + uuid.uuid4().hex[:8], rfq_id=rfq.id, supplier_id=sid,
                product_id=prod.id, token=rfq.supplier_tokens[sid],
                created_at=datetime.now().isoformat(),
            ))
            self.maybe_autopilot_quote(rfq, sid)

    def roles_for(self, user_id: str) -> list[str]:
        """The roles this account holds. No profile yet means a plain buyer. Order is stable: buyer, seller."""
        p = self.profiles.get(user_id)
        held = set(p.roles) if p else set()
        if p and not held:
            held.add("seller" if p.role.value == "supplier" else "buyer")
        if self.supplier_owner.get(user_id) == user_id:
            held.add("seller")
        if not held:
            held.add("buyer")
        return [r for r in ("buyer", "seller") if r in held]

    def add_role(self, user_id: str, role: str) -> Optional[list[str]]:
        """Give an existing account a second role. None if there is no profile to build the seller record from."""
        p = self.profiles.get(user_id)
        if not p:
            return None
        roles = set(self.roles_for(user_id)) | {role}
        self.register_profile(user_id, p.model_copy(update={"roles": [r for r in ("buyer", "seller") if r in roles]}))
        return self.roles_for(user_id)

    def register_profile(self, user_id: str, profile: Profile) -> None:
        """Remember a signed-in user's profile. A seller gets their own seller record, owned by them."""
        held = set(profile.roles) or {"seller" if profile.role.value == "supplier" else "buyer"}
        profile = profile.model_copy(update={"roles": [r for r in ("buyer", "seller") if r in held]})
        self.profiles[user_id] = profile
        if "seller" not in held:
            return
        self.supplier_owner[user_id] = user_id
        tier = "registry" if profile.verification.registry != "none" else \
               "tax_ids" if profile.verification.tax_ids_consistent else \
               "email" if profile.verification.email else "none"
        existing = self.supplier_profiles.get(user_id)
        self.supplier_profiles[user_id] = SupplierProfileOut(
            supplier_id=user_id, business_name=profile.company, location_city=profile.city,
            location_state=profile.state, categories=profile.categories,
            description=existing.description if existing else None,
            verification_tier=tier, synthetic=False,
            contact_name=profile.full_name, phone=profile.phone, email=profile.email,
        )
        self.supplier_products.setdefault(user_id, [])

    # Pincodes for the synthetic sellers, by city. Real accounts give theirs once at sign-up.
    _DEMO_CITY_PINS = {"mumbai": "400001", "pune": "411001", "ahmedabad": "380001", "delhi": "110001", "bengaluru": "560001",
                       "bangalore": "560001", "chennai": "600001", "hyderabad": "500001", "kolkata": "700001",
                       "surat": "395003", "jaipur": "302001", "ludhiana": "141001", "nashik": "422001", "thane": "400601"}

    def shipping_pins(self, token: str) -> Optional[tuple[str, str]]:
        """(seller pincode, buyer pincode) for the request behind this quote link. Used only to price shipping on the
        server; neither pincode is ever returned to the other side."""
        rfq = self.rfqs.get(self.token_to_rfq_id.get(token, ""))
        sid = self.token_to_supplier_id.get(token)
        if not rfq or not sid:
            return None
        owner = self.profiles.get(sid) if self.supplier_owner.get(sid) == sid else None
        seller_pin = owner.pincode if owner else self._DEMO_CITY_PINS.get(
            (self.supplier_profiles[sid].location_city if sid in self.supplier_profiles else "").strip().lower(), "")
        buyer = self.profiles.get(rfq.owner_id or "")
        buyer_pin = buyer.pincode if buyer else ""
        return (seller_pin, buyer_pin) if seller_pin and buyer_pin else None

    def supplier_id_for_user(self, user_id: str) -> Optional[str]:
        return user_id if self.supplier_owner.get(user_id) == user_id else None

    def get_autopilot(self, supplier_id: str) -> AutopilotSettings:
        return self.autopilot.get(supplier_id, AutopilotSettings())

    def set_autopilot(self, supplier_id: str, enabled: bool) -> AutopilotSettings:
        self.autopilot[supplier_id] = AutopilotSettings(enabled=enabled)
        return self.autopilot[supplier_id]

    def maybe_autopilot_quote(self, rfq: RFQ, supplier_id: str) -> Optional[QuoteVersion]:
        """Send a first quote from the catalog row, with no review, only when every rule holds:
        autopilot is on, the request is open, the seller has not quoted, no target is waiting,
        and the rules verdict is a clean yes (stock covers it, lead time fits, minimum order fits).
        Anything else stays in the inbox for a person. It never revises and never answers a target."""
        if not self.get_autopilot(supplier_id).enabled or rfq.status != "Open":
            return None
        token = rfq.supplier_tokens.get(supplier_id)
        if not token or supplier_id in self.quotes.get(rfq.id, {}) or self.has_pending_target(token):
            return None
        draft = self.draft_for_token(token)
        if not draft or draft.verdict.can_fulfil != "yes":
            return None
        qv = self.submit_quote(
            token=token, supplier_name=self._supplier_name(supplier_id), pack_price=draft.pack_price,
            pack_size=draft.pack_size, freight=draft.freight, lead_days=draft.lead_days, moq=draft.moq,
            max_qty=draft.max_qty, notes=template_message(rfq, draft), origin="auto",
            tax_rate=draft.tax_rate, price_includes_tax=draft.price_includes_tax,
        )
        qv.origin = "auto"
        return qv

    def _notification_out(self, n: Notification) -> Optional[NotificationOut]:
        rfq = self.rfqs.get(n.rfq_id)
        prod = next((p for p in self.supplier_products.get(n.supplier_id, []) if p.id == n.product_id), None)
        if not rfq or not prod:
            return None
        unlocked = self.is_revealed(rfq.id, n.supplier_id)
        return NotificationOut(
            id=n.id, rfq_id=rfq.id, supplier_id=n.supplier_id, status=n.status, created_at=n.created_at,
            item=rfq.item, qty=rfq.qty, need_in_days=rfq.need_in_days,
            buyer_descriptor=views.buyer_descriptor(self, rfq),
            note=rfq.note if unlocked else scrub(rfq.note), priority_mode=rfq.priority_mode, rfq_status=rfq.status,
            unlocked=unlocked, buyer_contact=views.buyer_contact(self, rfq) if unlocked else None,
            reminder=n.reminder, closes_at=rfq.window_ends_at, window_closed=rfq.window_closed,
            token=n.token, quote_url=f"/supplier/quote?token={n.token}",
            product=prod, verdict=verdict_for(rfq, prod),
            has_quoted=n.supplier_id in self.quotes.get(rfq.id, {}),
        )

    def list_notifications(self, supplier_id: str) -> List[NotificationOut]:
        outs = (self._notification_out(n) for n in self.notifications.get(supplier_id, []))
        return sorted((o for o in outs if o), key=lambda o: o.created_at, reverse=True)

    def mark_notification_viewed(self, supplier_id: str, notification_id: str) -> Optional[NotificationOut]:
        for n in self.notifications.get(supplier_id, []):
            if n.id == notification_id:
                n.status = "viewed"
                n.reminder = None
                return self._notification_out(n)
        return None

    def _notification_for_token(self, token: str) -> Optional[Notification]:
        sid = self.token_to_supplier_id.get(token)
        return next((n for n in self.notifications.get(sid, []) if n.token == token), None) if sid else None

    def touch_token(self, token: str, state: str) -> None:
        """Record that a seller opened ('viewed') or started editing ('quoting'). Never moves backwards."""
        n = self._notification_for_token(token)
        if n:
            n.reminder = None                      # they have seen the request, so the nudge has done its job
        if n and n.status == "new" or (n and state == "quoting" and n.status in ("viewed", "declined")):
            n.status = state

    def decline(self, token: str) -> bool:
        """'Can't supply' counts as a response. The seller may still change their mind and quote."""
        n = self._notification_for_token(token)
        if not n:
            return False
        n.status = "declined"
        return True

    def draft_for_token(self, token: str) -> Optional[DraftQuote]:
        n = self._notification_for_token(token)
        rfq = self.rfqs.get(self.token_to_rfq_id.get(token, ""))
        if not n or not rfq:
            return None
        prod = next((p for p in self.supplier_products.get(n.supplier_id, []) if p.id == n.product_id), None)
        return draft_quote(rfq, prod) if prod else None

    def create_share(self, rfq_id: str) -> str:
        for tok, rid in self.shares.items():
            if rid == rfq_id:
                return tok
        tok = "shr_" + uuid.uuid4().hex
        self.shares[tok] = rfq_id
        return tok

    def has_pending_target(self, token: str) -> bool:
        """True while a buyer's target awaits a human answer. Autopilot must not quote while this holds."""
        rfq_id, sid = self.token_to_rfq_id.get(token), self.token_to_supplier_id.get(token)
        t = self.targets.get(rfq_id, {}).get(sid) if rfq_id and sid else None
        return bool(t and t.status == "pending")

    def product_for_token(self, token: str) -> Optional[SupplierProduct]:
        n = self._notification_for_token(token)
        return next((p for p in self.supplier_products.get(n.supplier_id, []) if p.id == n.product_id), None) if n else None

    def activity(self, rfq_id: str) -> Activity:
        notes = [n for ns in self.notifications.values() for n in ns if n.rfq_id == rfq_id]
        quoted = set(self.quotes.get(rfq_id, {}))
        quoted_n = sum(1 for n in notes if n.supplier_id in quoted)
        quoting_n = sum(1 for n in notes if n.status == "quoting" or n.supplier_id in quoted)
        viewed_n = sum(1 for n in notes if n.status != "new" or n.supplier_id in quoted)
        declined_n = sum(1 for n in notes if n.status == "declined" and n.supplier_id not in quoted)
        return Activity(notified=len(notes), viewed=viewed_n, quoting=quoting_n, quoted=quoted_n, declined=declined_n)

    def list_suppliers(self) -> List[dict]:
        return [
            {"supplier_id": sid, "business_name": p.business_name, "location_city": p.location_city,
             "categories": p.categories, "synthetic": p.synthetic}
            for sid, p in sorted(self.supplier_profiles.items())
        ]

    # ─── RFQ Lifecycle ─────────────────────────────────────────────────

    def create_rfq(self, payload: RFQCreate, owner_id: Optional[str] = None) -> RFQ:
        """Create the request, find every seller whose catalog has the item, notify each once."""
        rfq_id = "rfq_" + uuid.uuid4().hex[:8]
        matches = self.match_suppliers(payload.item)
        tokens: dict[str, str] = {}
        for sid in matches:
            tok = "tok_" + uuid.uuid4().hex[:12]
            tokens[sid] = tok
            self.token_to_rfq_id[tok] = rfq_id
            self.token_to_supplier_id[tok] = sid
            self.token_to_supplier_name[tok] = self._supplier_name(sid)

        primary = list(tokens.values())[0] if tokens else "tok_" + uuid.uuid4().hex[:12]
        now = self.clock()
        key = payload.window or DEFAULT_WINDOW.get(payload.priority_mode, "24h")
        ends, label, demo = window_end(key, now)
        rfq = RFQ(
            id=rfq_id, token=primary,
            item=payload.item, qty=payload.qty, need_in_days=payload.need_in_days,
            buyer_company=payload.buyer_company, buyer_name=payload.buyer_name,
            buyer_city=payload.buyer_city, buyer_state=payload.buyer_state,
            note=payload.note, created_at=now.isoformat(),
            window_key=key, window_label=label, window_ends_at=ends.isoformat(), demo_timing=demo,
            status="Open", supplier_tokens=tokens,
            priority_mode=payload.priority_mode, source=payload.source, owner_id=owner_id,
            gst_claimable=True if payload.gst_claimable is None else payload.gst_claimable,
        )
        self.rfqs[rfq_id] = rfq
        self.quotes[rfq_id] = {}
        self.targets[rfq_id] = {}
        self.chats[rfq_id] = {}
        self._notify(rfq, matches)
        return rfq

    def get_rfq(self, rfq_id: str) -> Optional[RFQ]:
        return self.rfqs.get(rfq_id)

    def submit_quote(
        self,
        token: str,
        supplier_name: str,
        pack_price: float,
        pack_size: int,
        freight: float,
        lead_days: int,
        moq: Optional[int] = None,
        notes: Optional[str] = None,
        max_qty: Optional[int] = None,
        origin: str = "manual",
        tax_rate: Optional[float] = None,
        price_includes_tax: Optional[bool] = None,
        shipping: Optional[str] = None,
        shipping_basis: Optional[str] = None,
    ) -> QuoteVersion:
        rfq_id = self.token_to_rfq_id.get(token)
        if not rfq_id or rfq_id not in self.rfqs:
            raise ValueError("Invalid or expired quote token.")

        rfq = self.rfqs[rfq_id]
        if rfq.status != "Open":
            raise ValueError("RFQ is already closed or decided.")

        supplier_id = self.token_to_supplier_id.get(token)
        if not supplier_id:
            raise ValueError("Invalid or expired quote token.")

        if rfq.window_closed and not self.quotes.get(rfq_id, {}).get(supplier_id):
            raise ValueError("The quote window for this request has closed.")
        rfq_quotes = self.quotes.setdefault(rfq_id, {})
        supplier_history = rfq_quotes.setdefault(supplier_id, [])
        self.alias_for(rfq_id, supplier_id, create=True)     # "Seller N", in order of first quote, stable afterwards

        next_ver = len(supplier_history) + 1
        compare_price, tax_basis = normalise_price(pack_price, tax_rate, price_includes_tax, rfq.gst_claimable)
        q_obj = Quote(
            id=supplier_id, supplier=supplier_name, item=rfq.item,
            pack_price=compare_price, pack_size=pack_size, freight=freight,
            lead_days=lead_days, moq=moq, max_qty=max_qty,
        )
        calc = order(q_obj, min(rfq.qty, max_qty) if max_qty else rfq.qty)
        landed = calc.landed if calc else compare_price * pack_size + freight
        units = calc.units if calc else rfq.qty
        packs = calc.packs if calc else 1

        qv = QuoteVersion(
            version=next_ver, supplier_id=supplier_id, supplier_name=supplier_name,
            pack_price=pack_price, pack_size=pack_size, freight=freight,
            lead_days=lead_days, moq=moq, max_qty=max_qty, notes=notes, origin=origin,
            tax_rate=tax_rate, price_includes_tax=price_includes_tax, compare_price=compare_price, tax_basis=tax_basis,
            landed_cost=landed, units=units, packs=packs,
            shipping=shipping, shipping_basis=shipping_basis if shipping == "delhivery" else None,
            submitted_at=datetime.now().strftime("%I:%M %p"),
        )
        issued = self.assists.get(token)
        if origin == "auto":
            qv.origin = "auto"          # only maybe_autopilot_quote passes this; the HTTP layer never does
        elif issued and issued["source"] == "ai":
            d = issued["draft"]
            same = (pack_price, pack_size, freight, lead_days, moq, max_qty) == (
                d.pack_price, d.pack_size, d.freight, d.lead_days, d.moq, d.max_qty) and (notes or "") == issued["text"]
            qv.origin = "ai_draft_sent" if same else "ai_draft_edited"
        else:
            qv.origin = "manual"
        supplier_history.append(qv)
        self._quote_notices(rfq)

        # Mark pending target as accepted on revision
        if rfq_id in self.targets and supplier_id in self.targets[rfq_id]:
            self.targets[rfq_id][supplier_id].status = "accepted"

        return qv

    def get_supplier_quotes_and_target(self, token: str) -> dict:
        rfq_id = self.token_to_rfq_id.get(token)
        if not rfq_id:
            return {"quotes": [], "target": None}
        supplier_id = self.token_to_supplier_id.get(token)
        if not supplier_id:
            return {"quotes": [], "target": None}
        quotes = self.quotes.get(rfq_id, {}).get(supplier_id, [])
        target = self.targets.get(rfq_id, {}).get(supplier_id)
        return {"quotes": quotes, "target": target}

    def send_target(
        self,
        rfq_id: str,
        supplier_id: str,
        cut_needed: float,
        target_freight: Optional[float] = None,
        target_per_unit: Optional[float] = None,
        concession_type: str = "freight",
        message: Optional[str] = None,
        sent_by: str = "",
    ) -> NegotiationTarget:
        if rfq_id not in self.rfqs:
            raise ValueError(f"RFQ {rfq_id} not found.")

        msg = message or (
            f"Cut freight to ₹{target_freight} to win this order."
            if concession_type == "freight"
            else f"Cut unit price by ₹{target_per_unit} to win this order."
        )

        target = NegotiationTarget(
            id="tgt_" + uuid.uuid4().hex[:8],
            supplier_id=supplier_id, message=msg, cut_needed=cut_needed,
            target_freight=target_freight, target_per_unit=target_per_unit,
            concession_type=concession_type,
            sent_at=datetime.now().strftime("%I:%M %p"), sent_by=sent_by, status="pending",
        )
        self.targets.setdefault(rfq_id, {})[supplier_id] = target

        # Also drop a structured chat message so the thread shows the target card
        chat = self.chats.setdefault(rfq_id, {}).setdefault(supplier_id, [])
        chat.append(ChatMessage(
            id="msg_" + uuid.uuid4().hex[:8],
            sender="buyer", sender_name=self.rfqs[rfq_id].buyer_name,
            text=msg, timestamp=target.sent_at, target=target,
        ))

        return target

    def save_decision(self, rfq_id: str, winner_id: str, reason: str, approver: str) -> dict:
        rfq = self.rfqs.get(rfq_id)
        if not rfq:
            raise ValueError(f"RFQ {rfq_id} not found.")
        rfq.status = "Decided"
        decision = {
            "rfq_id": rfq_id, "winner_id": winner_id,
            "reason": reason, "approver": approver,
            "decided_at": datetime.now().isoformat(),
            # Every AI call that touched this request, so the record shows what a model did and did not do.
            "ai_calls": [{"request_id": e["request_id"], "kind": e["kind"], "at": e["at"]}
                         for e in self.ai_log_for(rfq_id)],
            "mode": rfq.priority_mode,
            "source": rfq.source,
            "payment_note": "Cash on delivery. Crossover never holds money.",
            # Every gate a person chose to break on this request, with their written reason.
            "exceptions": {a: r.model_dump() for a, r in self.exceptions_by_alias(rfq_id).items()},
        }
        rfq.decision = decision
        self.decisions[rfq_id] = decision
        return decision

    def get_latest_quotes_as_engine_input(self, rfq_id: str) -> List[Quote]:
        rfq = self.rfqs.get(rfq_id)
        if not rfq:
            return []
        rfq_quotes = self.quotes.get(rfq_id, {})
        res = []
        for s_id, versions in rfq_quotes.items():
            if not versions:
                continue
            latest = versions[-1]
            alias = self.alias_for(rfq_id, s_id, create=True)   # the engine only ever sees the alias
            res.append(Quote(
                id=alias, supplier=alias, item=latest.item or rfq.item,
                pack_price=latest.compare_price if latest.compare_price is not None else latest.pack_price,
                pack_size=latest.pack_size,
                freight=latest.freight, lead_days=latest.lead_days,
                moq=latest.moq, max_qty=latest.max_qty, raw=f"v{latest.version}: ₹{latest.pack_price} + ₹{latest.freight}",
            ))
        return res

    def get_supplier_id_for_token(self, token: str) -> Optional[str]:
        return self.token_to_supplier_id.get(token)

    def get_supplier_name_for_token(self, token: str) -> str:
        return self.token_to_supplier_name.get(token, "Supplier")

    # ─── Supplier Profile & Products ───────────────────────────────────

    def get_supplier_profile(self, supplier_id: str) -> Optional[SupplierProfileOut]:
        p = self.supplier_profiles.get(supplier_id)
        if p:
            p.products = self.supplier_products.get(supplier_id, [])
        return p

    def upsert_supplier_profile(self, supplier_id: str, payload: SupplierProfileIn) -> SupplierProfileOut:
        existing = self.supplier_profiles.get(supplier_id)
        tier = existing.verification_tier if existing else "none"
        prof = SupplierProfileOut(
            supplier_id=supplier_id,
            business_name=payload.business_name,
            location_city=payload.location_city,
            location_state=payload.location_state,
            categories=payload.categories,
            description=payload.description,
            verification_tier=tier,
            # Editing a profile must not wipe what the seller registered with, or flip a real seller to "synthetic".
            synthetic=existing.synthetic if existing else False,
            contact_name=existing.contact_name if existing else None,
            phone=existing.phone if existing else None,
            email=existing.email if existing else None,
            products=self.supplier_products.get(supplier_id, []),
        )
        self.supplier_profiles[supplier_id] = prof
        return prof

    def get_supplier_products(self, supplier_id: str) -> List[SupplierProduct]:
        return self.supplier_products.get(supplier_id, [])

    def add_supplier_product(self, supplier_id: str, payload: SupplierProductIn) -> SupplierProduct:
        prod = SupplierProduct(
            id="prod_" + uuid.uuid4().hex[:8],
            name=payload.name, category=payload.category,
            pack_price=payload.pack_price, pack_size=payload.pack_size,
            moq=payload.moq, usual_lead_days=payload.usual_lead_days,
            capacity_cap=payload.capacity_cap, unit=payload.unit,
            stock=payload.stock, freight=payload.freight, price_breaks=payload.price_breaks,
            aliases=payload.aliases, tax_rate=payload.tax_rate, price_includes_tax=payload.price_includes_tax,
        )
        self.supplier_products.setdefault(supplier_id, []).append(prod)
        return prod

    def update_supplier_product(self, supplier_id: str, product_id: str, payload: SupplierProductIn) -> Optional[SupplierProduct]:
        prods = self.supplier_products.get(supplier_id, [])
        for p in prods:
            if p.id == product_id:
                p.name = payload.name
                p.category = payload.category
                p.pack_price = payload.pack_price
                p.pack_size = payload.pack_size
                p.moq = payload.moq
                p.usual_lead_days = payload.usual_lead_days
                p.capacity_cap = payload.capacity_cap
                p.unit = payload.unit
                p.stock = payload.stock
                p.freight = payload.freight
                p.price_breaks = payload.price_breaks
                p.aliases = payload.aliases
                p.tax_rate = payload.tax_rate
                p.price_includes_tax = payload.price_includes_tax
                return p
        return None

    def delete_supplier_product(self, supplier_id: str, product_id: str) -> bool:
        prods = self.supplier_products.get(supplier_id, [])
        for i, p in enumerate(prods):
            if p.id == product_id:
                prods.pop(i)
                return True
        return False

    # ─── Chat ──────────────────────────────────────────────────────────

    def get_chat_messages(self, rfq_id: str, supplier_id: str) -> List[ChatMessage]:
        return self.chats.get(rfq_id, {}).get(supplier_id, [])

    def add_chat_message(self, rfq_id: str, supplier_id: str,
                         sender: str, sender_name: str, text: str) -> ChatMessage:
        msg = ChatMessage(
            id="msg_" + uuid.uuid4().hex[:8],
            sender=sender, sender_name=sender_name, text=text,
            timestamp=datetime.now().strftime("%I:%M %p"),
        )
        self.chats.setdefault(rfq_id, {}).setdefault(supplier_id, []).append(msg)
        return msg

    def get_chat_by_token(self, token: str) -> List[ChatMessage]:
        rfq_id = self.token_to_rfq_id.get(token)
        if not rfq_id:
            return []
        supplier_id = self.token_to_supplier_id.get(token)
        if not supplier_id:
            return []
        return self.get_chat_messages(rfq_id, supplier_id)

    def add_chat_by_token(self, token: str, sender: str, sender_name: str, text: str) -> Optional[ChatMessage]:
        rfq_id = self.token_to_rfq_id.get(token)
        if not rfq_id:
            return None
        supplier_id = self.token_to_supplier_id.get(token)
        if not supplier_id:
            return None
        return self.add_chat_message(rfq_id, supplier_id, sender, sender_name, text)


store = RFQStore()
