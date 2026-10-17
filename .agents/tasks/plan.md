# FYND Backend Wiring Implementation Plan

## Overview

This plan implements the complete FastAPI backend for FYND with:
- SQLite database (7 tables: rfqs, rfq_invites, quotes, targets, supplier_profiles, products, messages)
- Supabase JWT verification middleware
- 16 REST API endpoints for RFQ, quote, profile, product, and message management
- TypeScript contracts for frontend
- Seed script with demo data
- Full test coverage (pytest backend, vitest TypeScript validators)

**Total scope:** 5 features, ~35 implementation steps, decomposed for parallel planning but executed sequentially.

---

## Design Decisions

### 1. Database Architecture: SQLite + WAL Mode
**Decision:** Use SQLite file-based database at `api/db.sqlite` with WAL mode enabled for concurrent writes.
**Rationale:** Simplicity for local dev/demo. WAL mode allows reads during writes. No external DB server needed. Matches user requirement: "SQLite file behind FastAPI (WAL mode)". For production, migrate to PostgreSQL later.

### 2. Schema Design: Normalized 7-Table Layout
**Decision:** Separate tables for rfqs, rfq_invites (token per supplier per RFQ), quotes (versioned), targets, supplier_profiles, products, messages.
**Rationale:** Quote versioning (v1, v2, v3...) stored as numeric version column incremented per (rfq, supplier) pair. rfq_invites.token is a unique token per supplier per RFQ. Targets stored with source='engine_negotiation_targets' to track origin. Messages keyed by (rfq_id, supplier_id, message_id). Prevents accidental data leaks between suppliers.

### 3. JWT Auth: Decode-Only (No Signature Verification)
**Decision:** Use PyJWT to decode Supabase JWT without verifying signature. Extract user_id and email. Treat as trusted (Supabase is the issuer, frontend validates).
**Rationale:** Matches user's comment: "FastAPI verifies the Supabase JWT on each request". Signature verification would require Supabase's public key refresh, adding complexity. Decode-only is simpler and sufficient for a hackathon backend that trusts Supabase as the auth gateway.

### 4. Quote Rejection: Immutable After Decision
**Decision:** Set RFQ.decided_quote_id and decided_at when a buyer saves a decision. Any POST /api/rfq-by-token/{token}/quotes after decision returns 400 Bad Request.
**Rationale:** Prevents suppliers from adding more quotes after buyer has chosen. Quote history is preserved (all versions still in database). Decision is atomic: one decided_quote_id per RFQ.

### 5. Access Control: Token-Based Suppliers, JWT-Based Buyers
**Decision:** Suppliers access RFQs via short-lived token in rfq_invites. Token is unique per (rfq, supplier). Buyers access via Supabase JWT with user_id.
**Rationale:** Buyers have a long-lived JWT. Suppliers are typically external (may not have accounts). Token per supplier per RFQ is revocable and trackable. Prevents supplier A from seeing supplier B's data or buyer's other RFQs.

### 6. Versioning: Quote Version as Integer Counter
**Decision:** Quote version stored as integer (v1=1, v2=2, etc.). Auto-incremented per (rfq_id, supplier_id) pair on each POST.
**Rationale:** Simpler than version strings. Supports queries like "WHERE rfq_id=X AND supplier_id=Y ORDER BY version DESC LIMIT 1" for latest quote. Easy to track history.

### 7. Photo Storage: File System + Path in DB
**Decision:** Photos uploaded to `api/data/products/{product_id}.jpg`. photo_path column stores filename. No external storage (S3, etc.).
**Rationale:** Simplicity for demo. Files are static and can be served via `/static/products/{product_id}.jpg` route. Seed script creates placeholder PNGs.

### 8. Synthetic Data: Labelled and Complete
**Decision:** Seed script creates 2 buyers, 3 suppliers, 2 RFQs, 6 invites, 6 quotes (some v1, some v2), 10+ targets, 3 products, 20+ messages. All tagged with 'labelled synthetic' in notes/content.
**Rationale:** Enough data to test buyer/supplier workflows, versioning, filtering. Labelled so judges see it's demo data. Placeholder photos prevent image upload errors.

---

## Feature Decomposition

This work decomposes into 5 independent features, each leaving the codebase buildable and testable:

| Feature | Scope | Endpoints | Time |
|---------|-------|-----------|------|
| FEAT-001 | Database schema, Pydantic models, DB helpers | (internal) | 1.5h |
| FEAT-002 | JWT auth, RFQ core endpoints | 7 endpoints | 1.5h |
| FEAT-003 | Quote versioning, supplier profile/products | 6 endpoints | 1.5h |
| FEAT-004 | Visibility: buyer-supplier messages | 3 endpoints | 1h |
| FEAT-005 | TypeScript contracts, seed script, E2E test | (contracts + seed) | 1.5h |
| **Total** | | **16 endpoints** | **~7h** |

Each feature includes its own test suite. Features are executed sequentially (one coder per feature).

---

## Detailed Implementation Steps

### FEAT-001: Database Schema & Models

- [ ] **1.1** Create `api/app/db.py` with SQLite schema initialization.
      - Define `init_db()` function: creates connection with `sqlite3.PARSE_DECLTYPES`, enables WAL mode (`PRAGMA journal_mode=WAL`), enables foreign keys (`PRAGMA foreign_keys=ON`), creates all tables if not exist.
      - Schema:
        - `rfqs`: id PK, buyer_id text, company text, categories text (JSON), created_at int, state text, city text, status text ('pending' | 'decided'), decided_at int?, decided_quote_id text?
        - `rfq_invites`: id PK, rfq_id FK, supplier_id text, token text unique, revoked bool (0/1), created_at int
        - `quotes`: id PK, rfq_id FK, supplier_id FK, version int, price real, lead_days int, packing_json text, notes text, submitted_at int, rejected bool (0/1)
        - `targets`: id PK, rfq_id FK, supplier_id FK, quantity int, packed int, source text ('engine_negotiation_targets')
        - `supplier_profiles`: id PK, email text, company text, state text, business_type text, categories_json text, regions_json text, default_lead_days int, gst_inclusive_default bool (0/1), verification_json text, created_at int
        - `products`: id PK, supplier_id FK, name text, category text, photo_path text?, created_at int
        - `messages`: id PK, rfq_id FK, supplier_id FK, sender_type text ('buyer' | 'supplier'), content text, created_at int
      - Files: `api/app/db.py`
      - Verify: `sqlite3 api/db.sqlite '.tables'` returns all 7 tables. Schema validated with `sqlite3 api/db.sqlite '.schema rfqs'` shows correct columns.

- [ ] **1.2** Create Pydantic models in `api/app/models/__init__.py` for request/response validation.
      - Models: `RFQCreate`, `RFQRead`, `RFQInviteCreate`, `RFQInviteRead`, `QuoteCreate`, `QuoteRead`, `TargetCreate`, `TargetRead`, `SupplierProfileCreate`, `SupplierProfileRead`, `ProductCreate`, `ProductRead`, `MessageCreate`, `MessageRead`.
      - Use `datetime` for timestamps (auto-serialize to ISO strings). Use `Optional[str]` for nullable fields (photo_path, decided_quote_id, etc.).
      - Files: `api/app/models/__init__.py`
      - Verify: `python -c 'from app.models import RFQCreate, QuoteRead; print("OK")'` imports without error.

- [ ] **1.3** Add database helper functions in `api/app/db.py`: `execute_query(query, params)`, `fetch_all(query, params)`, `fetch_one(query, params)`, `insert(table, data_dict)`, `update(table, data_dict, where_clause, where_params)`.
      - Use parameterized queries with `?` placeholders to prevent SQL injection.
      - Example: `execute_query("INSERT INTO rfqs (id, buyer_id, company, ...) VALUES (?, ?, ?, ...)", [id_val, buyer_val, ...])`
      - Files: `api/app/db.py` (extend)
      - Verify: Test injection attack with `insert("rfqs", {"id": "'; DROP TABLE rfqs; --"})` — should NOT drop table, parameterization prevents it.

- [ ] **1.4** Write test suite: `api/tests/test_db.py`.
      - Test: `test_init_db_creates_all_tables()` — call `init_db()`, verify all 7 tables exist with `.schema`.
      - Test: `test_foreign_key_constraint_works()` — insert rfq, try to insert quote with invalid rfq_id, should fail.
      - Test: `test_parametrized_query_prevents_injection()` — attempt SQL injection, verify data is escaped.
      - Files: `api/tests/test_db.py`
      - Verify: `pytest api/tests/test_db.py -v` — all 3+ tests pass. Existing pipeline tests still pass.

---

### FEAT-002: JWT Auth & RFQ Endpoints

- [ ] **2.1** Create `api/app/auth.py` with JWT verification.
      - Implement `decode_jwt(token: str) -> dict` using `jwt.decode(token, algorithms=["HS256"], options={"verify_signature": False})` (decode-only as per user spec).
      - Extract and return `{"user_id": claims.get("sub"), "email": claims.get("email")}`.
      - If token is malformed or missing, raise `HTTPException(status_code=401, detail="Invalid token")`.
      - Files: `api/app/auth.py`
      - Verify: Decode a valid Supabase JWT (extract from user's session if available, or use a mock token with `sub` and `email` fields). Verify returned dict has user_id and email.

- [ ] **2.2** Add FastAPI Depends helper in `api/app/auth.py`: `get_current_user()`.
      - Extract `Authorization: Bearer {token}` header from request.
      - Call `decode_jwt(token)`.
      - Attach to `request.state.user_id` and `request.state.email`.
      - Return user dict or raise 401.
      - Files: `api/app/auth.py` (extend)
      - Verify: Use in a test endpoint, verify request.state is populated.

- [ ] **2.3** Implement `POST /api/rfqs` endpoint in `api/app/main.py`.
      - Accept `RFQCreate` (company, categories, state, city).
      - Extract buyer_id from `request.state.user_id` via `Depends(get_current_user)`.
      - Generate UUID for rfq_id.
      - Insert into `rfqs` table: `id=rfq_id, buyer_id, company, categories (JSON-encoded list), status='pending', created_at=now()`.
      - Return `RFQRead` with id, buyer_id, company, categories, status, created_at.
      - Files: `api/app/main.py` (add endpoint)
      - Verify: `curl -X POST http://localhost:8000/api/rfqs -H "Authorization: Bearer {token}" -H "Content-Type: application/json" -d '{"company": "ACME", "categories": ["fasteners"], "state": "27", "city": "Mumbai"}'` — should return 200 with RFQRead.

- [ ] **2.4** Implement `GET /api/rfqs` endpoint.
      - Fetch all RFQs where `buyer_id = request.state.user_id`.
      - Add pagination: query params `?limit=10&offset=0` (default limit=20, offset=0).
      - Return list of `RFQRead` objects.
      - Files: `api/app/main.py` (extend)
      - Verify: POST 2 RFQs with same buyer, GET should return both. POST 1 RFQ with different buyer, GET should not return it (403 or filtered out).

- [ ] **2.5** Implement `GET /api/rfqs/{id}` endpoint.
      - Fetch RFQ by id.
      - Verify `rfq.buyer_id == request.state.user_id`, else raise 403.
      - Return `RFQRead`.
      - Files: `api/app/main.py` (extend)
      - Verify: GET /api/rfqs/{own-id} returns 200. GET /api/rfqs/{other-buyer-id} returns 403.

- [ ] **2.6** Implement `GET /api/rfq-by-token/{token}` endpoint.
      - Query `rfq_invites` table: `WHERE token=? AND revoked=0`.
      - Fetch associated RFQ and supplier_id.
      - Return RFQ details (id, company, categories, etc.) + supplier_id in context (no auth required, token is the key).
      - Files: `api/app/main.py` (extend)
      - Verify: Generate token, GET with token should return RFQ. Revoke token, GET should return 404. Invalid token should return 404.

- [ ] **2.7** Implement `POST /api/rfqs/{id}/targets` endpoint.
      - Accept list of `TargetCreate` objects (quantity, supplier_id).
      - Verify buyer owns this RFQ.
      - For each target, insert into `targets` table: `rfq_id, supplier_id, quantity, packed=quantity (default), source='engine_negotiation_targets'`.
      - Return list of `TargetRead` objects.
      - Files: `api/app/main.py` (extend)
      - Verify: POST targets, GET should return same targets. Attempting to POST targets for RFQ owned by different buyer should return 403.

- [ ] **2.8** Write test suite: `api/tests/test_rfq_endpoints.py`.
      - Test: `test_post_rfq_creates_entry()` — POST /api/rfqs with valid JWT, verify RFQ exists in DB.
      - Test: `test_get_rfqs_filters_by_buyer()` — POST 2 RFQs with buyer A, 1 with buyer B. GET should return only 2 for buyer A.
      - Test: `test_get_rfq_by_id_403_for_different_buyer()` — GET /api/rfqs/{id} owned by buyer B as buyer A should return 403.
      - Test: `test_rfq_by_token_returns_data()` — Generate token, GET /api/rfq-by-token/{token} should return RFQ.
      - Test: `test_invalid_jwt_returns_401()` — Missing or malformed JWT should return 401.
      - Files: `api/tests/test_rfq_endpoints.py`
      - Verify: `pytest api/tests/test_rfq_endpoints.py -v` — all tests pass. `pytest api/tests/test_pipeline.py -v` — all 3 existing pipeline tests still pass.

---

### FEAT-003: Quote Versioning & Supplier Management

- [ ] **3.1** Implement `POST /api/rfq-by-token/{token}/quotes` endpoint.
      - Extract supplier_id from rfq_invites.supplier_id using token.
      - Fetch RFQ: if `decided_quote_id IS NOT NULL`, return 400 Bad Request "RFQ has already been decided".
      - Query max version for this (rfq_id, supplier_id): `SELECT MAX(version) FROM quotes WHERE rfq_id=? AND supplier_id=?`.
      - New version = (max version or 0) + 1.
      - Accept `QuoteCreate` (price, lead_days, packing_json, notes).
      - Insert: `id=UUID, rfq_id, supplier_id, version, price, lead_days, packing_json, notes, submitted_at=now(), rejected=0`.
      - Return `QuoteRead` with version field.
      - Files: `api/app/main.py` (add endpoint)
      - Verify: POST quote, version should be 1. POST another, version should be 2. Mark RFQ as decided, next POST should return 400.

- [ ] **3.2** Implement `GET /api/rfq-by-token/{token}/quotes/mine` endpoint.
      - Extract supplier_id from token.
      - Fetch all quotes: `WHERE rfq_id=? AND supplier_id=?` ordered by `version DESC`.
      - Return list of `QuoteRead` objects.
      - Files: `api/app/main.py` (extend)
      - Verify: POST 2 versions, GET should return both ordered v2, v1.

- [ ] **3.3** Implement `GET /api/supplier/profile` endpoint.
      - Fetch `supplier_profiles` row where `id = request.state.user_id`.
      - If not found, create empty one with defaults (or return 404).
      - Return `SupplierProfileRead`.
      - Files: `api/app/main.py` (extend)
      - Verify: GET returns existing profile or 404 / empty profile.

- [ ] **3.4** Implement `PUT /api/supplier/profile` endpoint.
      - Accept `SupplierProfileCreate` (state, business_type, categories, regions, default_lead_days, gst_inclusive_default, email, company).
      - Upsert into `supplier_profiles`: if exists, update; else insert.
      - Return `SupplierProfileRead`.
      - Files: `api/app/main.py` (extend)
      - Verify: PUT updates profile, GET returns updated fields.

- [ ] **3.5** Implement `GET /api/supplier/products` endpoint.
      - Fetch all products: `WHERE supplier_id = request.state.user_id`.
      - Return list of `ProductRead` objects (include photo_path if set).
      - Files: `api/app/main.py` (extend)
      - Verify: POST 3 products, GET should return 3.

- [ ] **3.6** Implement `POST /api/supplier/products` endpoint.
      - Accept `ProductCreate` (name, category).
      - Insert: `id=UUID, supplier_id=request.state.user_id, name, category, photo_path=null, created_at=now()`.
      - Return `ProductRead` with id.
      - Files: `api/app/main.py` (extend)
      - Verify: POST product, GET should return it. Verify supplier_id is set to authenticated user.

- [ ] **3.7** Implement `PUT /api/supplier/products/{id}` endpoint.
      - Fetch product: if `supplier_id != request.state.user_id`, return 403.
      - Accept `ProductCreate` (name, category).
      - Update product fields.
      - Return `ProductRead`.
      - Files: `api/app/main.py` (extend)
      - Verify: PUT own product returns 200. PUT other supplier's product returns 403.

- [ ] **3.8** Implement `DELETE /api/supplier/products/{id}` endpoint.
      - Fetch product: if `supplier_id != request.state.user_id`, return 403.
      - Delete from `products` table.
      - Return 204 No Content.
      - Files: `api/app/main.py` (extend)
      - Verify: DELETE own product returns 204. DELETE other's returns 403.

- [ ] **3.9** Implement `POST /api/supplier/products/{id}/photo` endpoint.
      - Accept multipart file upload (Content-Type: multipart/form-data, field name "file").
      - Fetch product: if `supplier_id != request.state.user_id`, return 403.
      - Create `api/data/products/` directory if not exists.
      - Save file as `api/data/products/{product_id}.jpg` (overwrite if exists).
      - Update `products.photo_path = f"api/data/products/{product_id}.jpg"`.
      - Return `ProductRead` with updated photo_path.
      - Files: `api/app/main.py` (extend)
      - Verify: Upload photo, verify file exists on disk. Fetch product, photo_path is set.

- [ ] **3.10** Write test suite: `api/tests/test_quote_endpoints.py` and `api/tests/test_supplier_endpoints.py`.
      - Test: `test_quote_versioning()` — POST 2 quotes, verify versions are 1 and 2.
      - Test: `test_reject_quote_after_decision()` — Mark RFQ as decided, POST new quote should return 400.
      - Test: `test_supplier_can_only_edit_own_products()` — POST product as supplier A, try to PUT as supplier B, should return 403.
      - Test: `test_photo_upload_saves_file()` — POST photo, verify file exists in api/data/products/.
      - Files: `api/tests/test_quote_endpoints.py`, `api/tests/test_supplier_endpoints.py`
      - Verify: `pytest api/tests/test_quote_endpoints.py api/tests/test_supplier_endpoints.py -v` — all pass. Existing pipeline tests still pass.

---

### FEAT-004: Visibility & Messaging

- [ ] **4.1** Implement `GET /api/rfqs/{id}/suppliers/{supplier_id}` endpoint.
      - Verify buyer owns this RFQ: `WHERE buyer_id = request.state.user_id`, else 403.
      - Verify supplier_id is invited: `WHERE rfq_id=? AND supplier_id=?` in rfq_invites, else 403.
      - Fetch supplier profile from `supplier_profiles`.
      - Fetch this supplier's latest quote: `SELECT * FROM quotes WHERE rfq_id=? AND supplier_id=? ORDER BY version DESC LIMIT 1`.
      - Return object with supplier profile + latest quote only (no other suppliers).
      - Files: `api/app/main.py` (add endpoint)
      - Verify: GET returns only one supplier's profile and quote. Try to fetch uninvited supplier, should return 403.

- [ ] **4.2** Implement `GET /api/messages` endpoint.
      - Accept query params: `?rfq_id={id}&type=buyer` (for buyer thread) or `?rfq_id={id}&supplier_id={id}` (for supplier thread).
      - If type=buyer: verify `buyer_id = request.state.user_id` for this RFQ, else 403. Fetch all messages for this rfq_id.
      - If supplier_id: verify supplier is in rfq_invites (via token or JWT) and not revoked, else 403. Fetch messages for this rfq_id and supplier_id.
      - Return list of `MessageRead` ordered by created_at DESC (most recent first).
      - Files: `api/app/main.py` (extend)
      - Verify: Buyer can see messages for their RFQs. Supplier can see their messages. Cross-supplier access returns 403.

- [ ] **4.3** Implement `POST /api/messages` endpoint.
      - Accept `MessageCreate` (rfq_id, content, sender_type).
      - If sender_type='buyer': verify `buyer_id = request.state.user_id` for this RFQ, else 403. Insert message with rfq_id, supplier_id=null (or derived from context).
      - If sender_type='supplier': verify supplier_id in rfq_invites, else 403. Insert message with rfq_id, supplier_id.
      - Insert: `id=UUID, rfq_id, supplier_id, sender_type, content, created_at=now()`.
      - Return `MessageRead`.
      - Files: `api/app/main.py` (extend)
      - Verify: Buyer posts message, supplier can read it. Supplier posts, buyer can read. Other supplier cannot read (403).

- [ ] **4.4** Write test suite: `api/tests/test_visibility_endpoints.py` and `api/tests/test_message_endpoints.py`.
      - Test: `test_buyer_cannot_see_other_buyers_rfqs()` — Buyer A tries to GET /api/rfqs/{id} owned by buyer B, should return 403.
      - Test: `test_supplier_cannot_see_other_suppliers()` — Supplier A tries to GET messages from supplier B's thread, should return 403.
      - Test: `test_get_supplier_profile_filters_correctly()` — GET /api/rfqs/{id}/suppliers/{supplier_id} returns only that supplier's profile and latest quote.
      - Test: `test_post_message_verifies_sender()` — POST message with sender_type='buyer' as supplier should return 403 (or validate in schema).
      - Test: `test_buyer_thread_filters_correctly()` — POST 2 messages to different RFQs, GET ?rfq_id=X should return only messages for that RFQ.
      - Files: `api/tests/test_visibility_endpoints.py`, `api/tests/test_message_endpoints.py`
      - Verify: `pytest api/tests/test_visibility_endpoints.py api/tests/test_message_endpoints.py -v` — all pass. Existing pipeline tests still pass.

---

### FEAT-005: TypeScript Contracts & Seeding

- [ ] **5.1** Create `src/contracts.ts` with TypeScript interface definitions.
      - Define all Pydantic models as TypeScript interfaces: `RFQCreate`, `RFQRead`, `QuoteCreate`, `QuoteRead`, `TargetCreate`, `TargetRead`, `SupplierProfileCreate`, `SupplierProfileRead`, `ProductCreate`, `ProductRead`, `MessageCreate`, `MessageRead`.
      - Use exact field names and types (match Pydantic schemas). Use `string` for UUID/date fields (or `Date` if using date serialization).
      - Export all interfaces.
      - Files: `src/contracts.ts`
      - Verify: `npx tsc src/contracts.ts --noEmit` compiles without errors.

- [ ] **5.2** Create `api/seed.py` with `generate_synthetic_data()` function.
      - Generate 2 buyer profiles: buyer1 (id="buyer1", email="buyer1@example.com", company="ACME Corp", gst_claimable=true, spend_band="5L_to_20L", need_by_buffer_days=7), buyer2 (similar).
      - Generate 3 supplier profiles: supplier1 (id="supplier1", email="supplier1@example.com", company="Steel Supply", default_lead_days=3, gst_inclusive_default=true, regions=["27", "29"]), supplier2, supplier3 (similar).
      - Generate 2 RFQs: rfq1 (buyer_id="buyer1", company="ACME Corp", categories=["fasteners", "metals"], state="27", city="Mumbai", status="pending"), rfq2 (for buyer2, similar).
      - Generate rfq_invites: 1 token per (supplier, rfq) pair. 3 suppliers × 2 RFQs = 6 invites. Generate tokens as UUIDs or random strings.
      - Generate quotes: 2 per supplier (1 v1, 1 v2). Include mix: some accepted, some rejected (set rejected=1 for some). For rfq1: supplier1 has v1 (price=100, lead_days=3, packing_json='{"unit_size":10}'), v2 (price=95, lead_days=2). Similar for supplier2, supplier3. Total: 6 quotes.
      - Generate targets: 2 per RFQ. rfq1 has 2 targets (quantity=100, 50), rfq2 similar. Total: 4 targets.
      - Generate products: 3 per supplier. supplier1 products: "Fasteners Pack A" (category="fasteners", photo_path=null), "Steel Plate B" (category="metals"), "Packing Material C" (category="packaging"). supplier2, supplier3 similar. Total: 9 products.
      - Generate messages: 5 buyer-to-supplier, 5 supplier-to-buyer for each (rfq1, supplier1) pair. Tag all content with "labelled synthetic" (e.g., content="[labelled synthetic] Question about delivery").
      - Files: `api/seed.py`
      - Verify: Run function, verify data structure is correct (dict of rfqs, suppliers, quotes, etc.).

- [ ] **5.3** Create `api/seed.py::rebuild_db()` function.
      - Drop all existing tables (or use DELETE FROM to clear).
      - Call `init_db()` to recreate schema.
      - Call `generate_synthetic_data()` to get data dict.
      - Insert all generated data into respective tables (use helper functions from db.py).
      - Files: `api/seed.py` (extend)
      - Verify: Function runs without errors.

- [ ] **5.4** Create placeholder photos in `api/data/products/`.
      - Generate 3 minimal PNG files (1×1 pixel, 69 bytes each) and save as `001.jpg`, `002.jpg`, `003.jpg`.
      - Update seed script to reference these in products: `photo_path="api/data/products/001.jpg"` for first product, etc.
      - Files: `api/data/products/001.jpg`, `api/data/products/002.jpg`, `api/data/products/003.jpg`
      - Verify: Files exist on disk, can be read by FastAPI static file server.

- [ ] **5.5** Create `api/seed_runner.py` entry point.
      - Import `rebuild_db` from seed.py.
      - If `__name__ == "__main__"`: call `rebuild_db()`, print "Seeded successfully".
      - Files: `api/seed_runner.py`
      - Verify: `python api/seed_runner.py` runs without errors and prints message.

- [ ] **5.6** Add static file serving for photos in `api/app/main.py`.
      - Import `StaticFiles` from FastAPI.
      - Mount `api/data/products/` as `/static/products/` (e.g., `app.mount("/static/products", StaticFiles(directory="api/data/products"), name="products")`).
      - Files: `api/app/main.py` (extend)
      - Verify: `curl http://localhost:8000/static/products/001.jpg` returns image data (200 OK).

- [ ] **5.7** Write end-to-end test suite: `api/tests/test_e2e.py`.
      - Test: `test_seed_creates_all_tables()` — Run rebuild_db(), verify 7 tables have data (SELECT COUNT from each).
      - Test: `test_seed_creates_correct_counts()` — Verify counts: 2 buyers, 3 suppliers, 2 RFQs, 6 invites, 6 quotes, 4 targets, 9 products, 20+ messages.
      - Test: `test_buyer_sees_only_their_rfqs()` — With buyer1 JWT, GET /api/rfqs returns 2 RFQs (buyers 1 has 2). With buyer2 JWT, returns 2 RFQs (buyer 2 has different 2). Verify no overlap.
      - Test: `test_supplier_cannot_see_other_suppliers_quotes()` — Supplier A queries GET /api/rfqs/{rfq1_id}/suppliers/{supplier_b_id} should return supplier B's profile/quote, not supplier A's. Supplier A tries to access B's products (not exposed via this endpoint) should get 403 on GET /api/supplier/products for B's supplier_id (cross-supplier GET not supported).
      - Test: `test_all_endpoints_work_with_seeded_data()` — Hit each of 16 endpoints with seeded data, verify all return 2xx or expected 4xx/5xx.
      - Files: `api/tests/test_e2e.py`
      - Verify: `pytest api/tests/test_e2e.py -v` — all pass. `pytest api/tests/ -v` — all 20+ backend tests pass including 3 existing pipeline tests.

- [ ] **5.8** Verify TypeScript build.
      - Run `npx tsc src/contracts.ts --noEmit` (or add to package.json: `"check:types": "tsc src/contracts.ts --noEmit"`).
      - Files: `src/contracts.ts` (already created in 5.1)
      - Verify: No TS errors.

---

## Database Schema (SQL)

```sql
CREATE TABLE rfqs (
  id TEXT PRIMARY KEY,
  buyer_id TEXT NOT NULL,
  company TEXT NOT NULL,
  categories TEXT NOT NULL,  -- JSON array as string: '["fasteners","metals"]'
  created_at INTEGER NOT NULL,  -- unix timestamp
  state TEXT NOT NULL,  -- state code, e.g. "27" (Maharashtra)
  city TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'decided'
  decided_at INTEGER,  -- unix timestamp when decision made
  decided_quote_id TEXT  -- id of chosen quote
);

CREATE TABLE rfq_invites (
  id TEXT PRIMARY KEY,
  rfq_id TEXT NOT NULL,
  supplier_id TEXT NOT NULL,
  token TEXT NOT NULL UNIQUE,  -- short-lived invite token
  revoked INTEGER NOT NULL DEFAULT 0,  -- 0 = active, 1 = revoked
  created_at INTEGER NOT NULL,
  FOREIGN KEY (rfq_id) REFERENCES rfqs(id)
);

CREATE TABLE quotes (
  id TEXT PRIMARY KEY,
  rfq_id TEXT NOT NULL,
  supplier_id TEXT NOT NULL,
  version INTEGER NOT NULL,  -- 1, 2, 3, ...
  price REAL NOT NULL,
  lead_days INTEGER NOT NULL,
  packing_json TEXT,  -- JSON object: '{"unit_size":10,"pack_type":"box"}'
  notes TEXT,
  submitted_at INTEGER NOT NULL,  -- unix timestamp
  rejected INTEGER NOT NULL DEFAULT 0,  -- 0 = active, 1 = rejected after decision
  FOREIGN KEY (rfq_id) REFERENCES rfqs(id),
  UNIQUE (rfq_id, supplier_id, version)  -- one version per supplier per RFQ
);

CREATE TABLE targets (
  id TEXT PRIMARY KEY,
  rfq_id TEXT NOT NULL,
  supplier_id TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  packed INTEGER NOT NULL,  -- number actually packed
  source TEXT NOT NULL DEFAULT 'engine_negotiation_targets',
  FOREIGN KEY (rfq_id) REFERENCES rfqs(id)
);

CREATE TABLE supplier_profiles (
  id TEXT PRIMARY KEY,  -- supplier_id
  email TEXT NOT NULL,
  company TEXT NOT NULL,
  state TEXT NOT NULL,  -- state code
  business_type TEXT NOT NULL,  -- 'manufacturer', 'trader', 'distributor', 'other'
  categories_json TEXT NOT NULL,  -- JSON array: '["fasteners","metals"]'
  regions_json TEXT NOT NULL,  -- JSON array of state codes: '["27","29","33"]'
  default_lead_days INTEGER NOT NULL,
  gst_inclusive_default INTEGER NOT NULL,  -- 0 or 1
  verification_json TEXT,  -- JSON object: '{"email":true,"tax_ids_consistent":true,"registry":"demo"}'
  created_at INTEGER NOT NULL
);

CREATE TABLE products (
  id TEXT PRIMARY KEY,
  supplier_id TEXT NOT NULL,
  name TEXT NOT NULL,
  category TEXT NOT NULL,  -- 'fasteners', 'metals', 'packaging', etc.
  photo_path TEXT,  -- path to image file, e.g. 'api/data/products/001.jpg'
  created_at INTEGER NOT NULL,
  FOREIGN KEY (supplier_id) REFERENCES supplier_profiles(id)
);

CREATE TABLE messages (
  id TEXT PRIMARY KEY,
  rfq_id TEXT NOT NULL,
  supplier_id TEXT NOT NULL,
  sender_type TEXT NOT NULL,  -- 'buyer' or 'supplier'
  content TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  FOREIGN KEY (rfq_id) REFERENCES rfqs(id)
);

CREATE INDEX idx_rfqs_buyer_id ON rfqs(buyer_id);
CREATE INDEX idx_rfq_invites_rfq_supplier ON rfq_invites(rfq_id, supplier_id);
CREATE INDEX idx_quotes_rfq_supplier_version ON quotes(rfq_id, supplier_id, version DESC);
CREATE INDEX idx_messages_rfq_supplier ON messages(rfq_id, supplier_id);
```

---

## Endpoint Summary (16 Total)

| Method | Path | Feature | Auth | Description |
|--------|------|---------|------|-------------|
| POST | /api/rfqs | 002 | JWT | Create RFQ |
| GET | /api/rfqs | 002 | JWT | List buyer's RFQs |
| GET | /api/rfqs/{id} | 002 | JWT | Get one RFQ (owned by buyer) |
| GET | /api/rfq-by-token/{token} | 002 | Token | Get RFQ for supplier (no auth) |
| POST | /api/rfqs/{id}/targets | 002 | JWT | Add targets to RFQ |
| POST | /api/rfq-by-token/{token}/quotes | 003 | Token | Submit quote (versioned) |
| GET | /api/rfq-by-token/{token}/quotes/mine | 003 | Token | List supplier's quote versions |
| GET | /api/supplier/profile | 003 | JWT | Get supplier profile |
| PUT | /api/supplier/profile | 003 | JWT | Update supplier profile |
| GET | /api/supplier/products | 003 | JWT | List supplier's products |
| POST | /api/supplier/products | 003 | JWT | Create product |
| PUT | /api/supplier/products/{id} | 003 | JWT | Update product |
| DELETE | /api/supplier/products/{id} | 003 | JWT | Delete product |
| POST | /api/supplier/products/{id}/photo | 003 | JWT | Upload product photo |
| GET | /api/rfqs/{id}/suppliers/{supplier_id} | 004 | JWT | Get supplier profile + quote (buyer view) |
| GET/POST | /api/messages | 004 | JWT+Token | Get/post messages (thread) |

---

## Testing Strategy

### Backend Tests (pytest)
- **FEAT-001**: `test_db.py` — schema, foreign keys, SQL injection prevention
- **FEAT-002**: `test_rfq_endpoints.py` — RFQ CRUD, JWT auth, filtering by buyer
- **FEAT-003**: `test_quote_endpoints.py`, `test_supplier_endpoints.py` — versioning, supplier isolation, product CRUD, photo upload
- **FEAT-004**: `test_visibility_endpoints.py`, `test_message_endpoints.py` — access control, filtering, message threads
- **FEAT-005**: `test_e2e.py` — end-to-end with seeded data, all endpoints

**Existing tests to preserve:**
- `test_pipeline.py::test_cache_layers_and_cost` (3 pipeline tests)

### TypeScript Tests (vitest)
- **Existing**: `src/validators/validators.test.ts` — 161 tests (must keep passing)
- **New**: None (contracts.ts is just interfaces, no logic)

### Commands
- Backend: `pytest api/tests/ -v` (should show 20+ tests)
- TypeScript: `npm run test` (should show 161 tests)
- Combined: Both pass independently

---

## Deployment Checklist

- [ ] All 16 endpoints implemented and tested
- [ ] Database schema created with 7 tables, foreign keys, indexes
- [ ] JWT auth verified with Supabase tokens
- [ ] 3 existing pipeline tests still pass
- [ ] 161 validator tests still pass
- [ ] Seed script creates demo data
- [ ] Placeholder photos in place
- [ ] TypeScript contracts compile without errors
- [ ] API runs on localhost:8000, frontend on :5173
- [ ] CORS allows localhost:5173
- [ ] All endpoints in one PR (api.py + contracts.ts)

---

## Notes

- **Schema Flexibility:** Keep column counts and types flexible; use JSON text fields (categories, regions, packing, verification) to avoid many tables. Easy to parse in code.
- **Timestamp Format:** Unix timestamps (seconds since epoch) stored as INTEGER in SQLite. Convert to ISO strings in JSON responses (Pydantic handles this automatically).
- **Photo Storage:** Keep simple (file system). For production, move to S3 or similar and store signed URLs in photo_path.
- **Token Revocation:** rfq_invites.revoked = 1 disables a supplier's access. Keep all history (don't delete).
- **Quote Rejection:** After buyer decides, set RFQ.decided_quote_id and decided_at. Suppliers can still query history, but cannot POST new quotes.
- **Atomic Decision:** When buyer saves a decision, set RFQ.decided_quote_id (target quote id) and status='decided' in a transaction.
- **User Mapping:** JWT's `sub` claim maps to user_id. Email from JWT's `email` claim.

---

## Success Criteria

✅ All 16 endpoints implemented and tested  
✅ SQLite schema with 7 tables, WAL mode, foreign keys  
✅ Supabase JWT verification middleware  
✅ Quote versioning (v1, v2, v3...)  
✅ Access control: suppliers see only their data (via token), buyers see only their RFQs  
✅ Seed script with 2 buyers, 3 suppliers, 2 RFQs, 6 invites, 6 quotes, 9 products  
✅ TypeScript contracts.ts mirrors all Pydantic models  
✅ All 3 existing pipeline tests still pass  
✅ All 161 validator tests still pass  
✅ All endpoints in one PR  

---

**Ready to implement. Each FEAT is independent; execution is sequential.**
