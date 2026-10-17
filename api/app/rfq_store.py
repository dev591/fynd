import uuid
from datetime import datetime
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
)
from .engine import order
from .matching import matching_product, verdict_for

# Default supplier labels for demo invites
_DEFAULT_SUPPLIERS = [
    ("A", "Supplier A"),
    ("B", "Supplier B"),
    ("C", "Supplier C"),
]


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

        self._seed_default_data()
        self._seed_supplier_profiles()
        self._seed_marketplace()

    # ─── Seeding ───────────────────────────────────────────────────────

    def _seed_default_data(self):
        rfq = RFQ(
            id="rfq_c27_01",
            token="tok_supplier_a",
            item="M10 bolt",
            qty=100,
            need_in_days=5,
            buyer_company="FanWorks Precision Manufacturing",
            buyer_name="Ramesh Sharma",
            buyer_city="Pune",
            buyer_state="Maharashtra",
            note="Need 100 high-tensile hex bolts for fan motor mountings by Friday.",
            created_at=datetime.now().isoformat(),
            status="Open",
            supplier_tokens={"A": "tok_supplier_a", "B": "tok_supplier_b", "C": "tok_supplier_c"},
        )
        self.rfqs[rfq.id] = rfq
        for sid, tok in rfq.supplier_tokens.items():
            self.token_to_rfq_id[tok] = rfq.id
            self.token_to_supplier_id[tok] = sid
            self.token_to_supplier_name[tok] = dict(_DEFAULT_SUPPLIERS).get(sid, f"Supplier {sid}")

        self.quotes[rfq.id] = {
            "A": [
                QuoteVersion(
                    version=1, supplier_id="A", supplier_name="Supplier A",
                    pack_price=10.0, pack_size=1, freight=200.0, lead_days=3,
                    moq=1, notes="Ex-warehouse Pune.",
                    landed_cost=1200.0, units=100, packs=100,
                    submitted_at="10:00 AM",
                )
            ],
            "B": [
                QuoteVersion(
                    version=1, supplier_id="B", supplier_name="Supplier B",
                    pack_price=11.0, pack_size=1, freight=50.0, lead_days=3,
                    moq=1, notes="Direct local shipping.",
                    landed_cost=1150.0, units=100, packs=100,
                    submitted_at="10:15 AM",
                )
            ],
        }
        self.targets[rfq.id] = {}
        self.chats[rfq.id] = {}

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
                            usual_lead_days=3, unit="pc", stock=80, freight=50,
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

        # The seeded demo request reaches its three invited sellers too.
        seeded = self.rfqs["rfq_c27_01"]
        self._notify(seeded, {sid: m for sid, m in self.match_suppliers(seeded.item).items()
                              if sid in seeded.supplier_tokens})

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

    def _notify(self, rfq: RFQ, matches: Dict[str, SupplierProduct]) -> None:
        for sid, prod in matches.items():
            self.notifications.setdefault(sid, []).append(Notification(
                id="ntf_" + uuid.uuid4().hex[:8], rfq_id=rfq.id, supplier_id=sid,
                product_id=prod.id, token=rfq.supplier_tokens[sid],
                created_at=datetime.now().isoformat(),
            ))

    def _notification_out(self, n: Notification) -> Optional[NotificationOut]:
        rfq = self.rfqs.get(n.rfq_id)
        prod = next((p for p in self.supplier_products.get(n.supplier_id, []) if p.id == n.product_id), None)
        if not rfq or not prod:
            return None
        return NotificationOut(
            id=n.id, rfq_id=rfq.id, supplier_id=n.supplier_id, status=n.status, created_at=n.created_at,
            item=rfq.item, qty=rfq.qty, need_in_days=rfq.need_in_days,
            buyer_company=rfq.buyer_company, buyer_city=rfq.buyer_city, buyer_state=rfq.buyer_state,
            note=rfq.note, priority_mode=rfq.priority_mode, rfq_status=rfq.status,
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
                return self._notification_out(n)
        return None

    def list_suppliers(self) -> List[dict]:
        return [
            {"supplier_id": sid, "business_name": p.business_name, "location_city": p.location_city,
             "categories": p.categories, "synthetic": p.synthetic}
            for sid, p in sorted(self.supplier_profiles.items())
        ]

    # ─── RFQ Lifecycle ─────────────────────────────────────────────────

    def create_rfq(self, payload: RFQCreate) -> RFQ:
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
        rfq = RFQ(
            id=rfq_id, token=primary,
            item=payload.item, qty=payload.qty, need_in_days=payload.need_in_days,
            buyer_company=payload.buyer_company, buyer_name=payload.buyer_name,
            buyer_city=payload.buyer_city, buyer_state=payload.buyer_state,
            note=payload.note, created_at=datetime.now().isoformat(),
            status="Open", supplier_tokens=tokens,
            priority_mode=payload.priority_mode, source=payload.source,
        )
        self.rfqs[rfq_id] = rfq
        self.quotes[rfq_id] = {}
        self.targets[rfq_id] = {}
        self.chats[rfq_id] = {}
        self._notify(rfq, matches)
        return rfq

    def get_rfq(self, rfq_id: str) -> Optional[RFQ]:
        return self.rfqs.get(rfq_id)

    def get_rfq_by_token(self, token: str) -> Optional[dict]:
        """Sealed bids: supplier only sees the buyer's request, nothing about other suppliers."""
        rfq_id = self.token_to_rfq_id.get(token)
        if not rfq_id:
            return None
        rfq = self.rfqs.get(rfq_id)
        if not rfq:
            return None
        return {
            "id": rfq.id,
            "item": rfq.item,
            "qty": rfq.qty,
            "need_in_days": rfq.need_in_days,
            "buyer_company": rfq.buyer_company,
            "buyer_name": rfq.buyer_name,
            "buyer_city": rfq.buyer_city,
            "buyer_state": rfq.buyer_state,
            "note": rfq.note,
            "status": rfq.status,
            "supplier_id": self.token_to_supplier_id.get(token),
            "supplier_name": self.get_supplier_name_for_token(token),
        }

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

        rfq_quotes = self.quotes.setdefault(rfq_id, {})
        supplier_history = rfq_quotes.setdefault(supplier_id, [])

        next_ver = len(supplier_history) + 1
        q_obj = Quote(
            id=supplier_id, supplier=supplier_name, item=rfq.item,
            pack_price=pack_price, pack_size=pack_size, freight=freight,
            lead_days=lead_days, moq=moq, max_qty=max_qty,
        )
        calc = order(q_obj, min(rfq.qty, max_qty) if max_qty else rfq.qty)
        landed = calc.landed if calc else pack_price * pack_size + freight
        units = calc.units if calc else rfq.qty
        packs = calc.packs if calc else 1

        qv = QuoteVersion(
            version=next_ver, supplier_id=supplier_id, supplier_name=supplier_name,
            pack_price=pack_price, pack_size=pack_size, freight=freight,
            lead_days=lead_days, moq=moq, max_qty=max_qty, notes=notes,
            landed_cost=landed, units=units, packs=packs,
            submitted_at=datetime.now().strftime("%I:%M %p"),
        )
        supplier_history.append(qv)

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
            sent_at=datetime.now().strftime("%I:%M %p"), status="pending",
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
            res.append(Quote(
                id=s_id, supplier=latest.supplier_name, item=rfq.item,
                pack_price=latest.pack_price, pack_size=latest.pack_size,
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
            aliases=payload.aliases,
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
                return p
        return None

    def delete_supplier_product(self, supplier_id: str, product_id: str) -> bool:
        prods = self.supplier_products.get(supplier_id, [])
        for i, p in enumerate(prods):
            if p.id == product_id:
                prods.pop(i)
                return True
        return False

    def get_supplier_profile_for_buyer(self, rfq_id: str, supplier_id: str) -> Optional[dict]:
        """Buyer-side: only if that supplier is on the request (invited or quoted)."""
        rfq = self.rfqs.get(rfq_id)
        if not rfq:
            return None
        # Supplier must have a token OR have submitted a quote
        has_token = supplier_id in rfq.supplier_tokens
        has_quote = supplier_id in self.quotes.get(rfq_id, {})
        if not has_token and not has_quote:
            return None
        prof = self.supplier_profiles.get(supplier_id)
        if not prof:
            # Return minimal profile from quote data
            quotes = self.quotes.get(rfq_id, {}).get(supplier_id, [])
            name = quotes[-1].supplier_name if quotes else f"Supplier {supplier_id}"
            return {
                "supplier_id": supplier_id,
                "business_name": name,
                "location_city": "Unknown",
                "location_state": "Unknown",
                "categories": [],
                "description": None,
                "verification_tier": "none",
                "products": [],
            }
        return {
            "supplier_id": prof.supplier_id,
            "business_name": prof.business_name,
            "location_city": prof.location_city,
            "location_state": prof.location_state,
            "categories": prof.categories,
            "description": prof.description,
            "verification_tier": prof.verification_tier,
            "products": [p.model_dump() for p in self.supplier_products.get(supplier_id, [])],
        }

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
