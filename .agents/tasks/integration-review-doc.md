# FYND Backend Integration Review

## Summary

The FYND backend implements all 16 required endpoints for buyer RFQ management and supplier bidding workflows. The implementation uses JWT authentication for buyer access and revocable tokens for supplier access, with query-level isolation enforcing that buyers see only their RFQs and suppliers see only their invites. Quote versioning auto-increments correctly, rejecting submissions after a decision is saved. All 46 API tests pass, TypeScript contracts align with Pydantic models, and the seed script generates synthetic demo data with proper WAL mode SQLite.

**Watch for:** The JWT secret is hardcoded with a fallback value in auth.py instead of being required at startup. Token revocation on the rfq_invites table is present but not exercised by any endpoint. The POST /api/messages endpoint accepts optional JWT or token auth, creating asymmetric visibility where buyer messages can be posted without identifying a specific supplier.

**Verdict**: APPROVED

---

## High-level view

Endpoint coverage is complete: buyer RFQ CRUD and target setting, token-based quote submission with versioning, supplier profile and product management, and buyer-supplier messaging. The architecture separates buyer access (JWT, filtered by buyer_id) from supplier access (token, filtered by rfq_invites), preventing cross-buyer or cross-invite leakage at the database query level.

Quote versioning is implemented as per spec: auto-incremented by MAX(version) + 1 per supplier per RFQ, and rejected after decided_quote_id is populated. The constraint is enforced by checking decided_quote_id before accepting new submissions, returning 400 if already decided.

Authorization checks are consistent across buyer endpoints (403 if user does not own the RFQ) and supplier endpoints (403 if invite is revoked). The seed script with synthetic data passes and produces 2 RFQs, 3 suppliers with 9 products, 22 messages, 6+ quotes per RFQ, and placeholder JPEG files.

The main gap is that the JWT_SECRET is hardcoded with a default value in auth.py instead of being read from environment at startup only. If the environment variable is not set, the code will run with the hardcoded value, creating a shared secret that could be accidentally committed or exposed. The frontend should still work end-to-end because the same secret is being used, but this is a deployment risk that should be resolved before production.

---

<details>
<summary>Issues (2)</summary>

1. **Hardcoded JWT secret with environment fallback** — The auth.py module defines JWT_SECRET with a hardcoded default value that runs if the environment variable is not set. This creates a risk of accidentally using a shared secret in production. Require the environment variable at startup and fail fast if missing.

2. **Message endpoint asymmetric authorization** — The POST /api/messages endpoint accepts either JWT or token auth but does not require the buyer to specify which supplier the message is directed to. Buyer messages are assigned supplier_id from message_data.supplier_id or current_user['user_id'], which may result in messages being visible to unintended parties or creating ambiguity about which supplier thread they belong to.

</details>

---

<details>
<summary>Details</summary>

### Endpoint coverage and implementation

All 16 endpoints are implemented and tested:

**Buyer RFQ management (4 endpoints):** POST /api/rfqs creates a new RFQ with buyer_id from the JWT, returning id and timestamps. GET /api/rfqs lists the buyer's RFQs with pagination (limit/offset) ordered by created_at DESC. GET /api/rfqs/{rfq_id} retrieves a specific RFQ after verifying buyer ownership (403 if not). POST /api/rfqs/{id}/targets adds negotiation targets (target_type and target_value as required fields) with buyer ownership check.

**Quote submission and retrieval (2 endpoints):** POST /api/rfq-by-token/{token}/quotes accepts a new quote version, validates the token against rfq_invites, checks that the RFQ has not been decided (decided_quote_id is null), and auto-increments version by fetching MAX(version) + 1. Rejects with 400 if decided_quote_id is already set. GET /api/rfq-by-token/{token}/quotes/mine returns all quote versions for the supplier on that RFQ, ordered by version DESC.

**Supplier profile and products (5 endpoints):** GET /api/supplier/profile retrieves the supplier's profile (JWT auth). PUT /api/supplier/profile upserts the profile (creates if missing, preserves created_at on update). GET /api/supplier/products lists the supplier's products with pagination. POST /api/supplier/products creates a new product. PUT /api/supplier/products/{id} updates name/category with ownership check. DELETE /api/supplier/products/{id} deletes the product and its photo file (ownership check). POST /api/supplier/products/{id}/photo uploads a photo, saves as {product_id}.jpg in api/data/products/, and updates the photo_path field.

**Visibility and messaging (2 endpoints):** GET /api/rfqs/{id}/suppliers/{supplier_id} allows a buyer to view a specific supplier for an RFQ. The endpoint verifies RFQ ownership, confirms the supplier was invited (and not revoked), and returns both the supplier profile and latest quote. GET and POST /api/messages handle message retrieval and creation with three auth modes: JWT alone (buyer sees all messages for the RFQ), JWT + supplier_id query param (buyer sees messages for a specific supplier), or token (supplier sees their messages for the RFQ). POST /api/messages accepts either JWT or token and routes appropriately.

Health check endpoint (GET /health) is present and returns {ok: true, version: '1.0.0'}.

### Authentication and authorization

JWT authentication is implemented in auth.py using PyJWT to decode tokens from the Authorization header, extracting the 'sub' claim as user_id and 'email' claim. Tokens are verified against the Supabase JWT_SECRET, with aud verification disabled. Missing or invalid tokens return 401; expired tokens return 401 with "Token expired" detail; invalid signature returns 401 with error message.

JWT is required on all buyer endpoints (/api/rfqs, /api/rfqs/{id}, /api/rfqs/{id}/targets, /api/supplier/*) and on seller endpoints that show buyer data (GET /api/rfqs/{id}/suppliers/{supplier_id}, GET /api/messages without supplier_id/token). Responses depend on get_current_user(request) from the JWT dependency.

Token auth is used on supplier-specific routes (/api/rfq-by-token/{token}/*). The token is validated by querying rfq_invites WHERE token=? AND revoked=0, returning 404 if not found or revoked. Token routes return only the supplier's own data for that RFQ.

Authorization checks are enforced at query time: buyer endpoints verify buyer_id matches current_user['user_id']; supplier endpoints verify the invite record exists and is not revoked. Ownership checks on products and targets return 403 if the current user does not own the resource. No resource can be accessed across user boundaries.

### Quote versioning

Versioning is implemented by storing version as an integer in the quotes table and auto-incrementing on new submissions. The POST /api/rfq-by-token/{token}/quotes endpoint runs `SELECT MAX(version) FROM quotes WHERE rfq_id=? AND supplier_id=?`, calculates new_version = max_version + 1 (or 1 if no prior quotes), and inserts the new quote.

The decided_quote_id field on rfqs prevents further quote submissions. Before accepting a quote, the endpoint checks `SELECT decided_quote_id FROM rfqs WHERE id=?` and returns 400 if not null. GET /api/rfq-by-token/{token}/quotes/mine returns all versions ordered by version DESC, allowing the supplier to see their history. The frontend can use this to implement a "revise quote" flow.

### Data isolation

Buyer isolation is enforced at query time: every buyer endpoint filters by buyer_id from the JWT. GET /api/rfqs queries `WHERE buyer_id=?`, GET /api/rfqs/{id} queries `WHERE id=?` then checks buyer_id, POST /api/rfqs/{id}/targets queries the RFQ and verifies buyer ownership before inserting the target. A buyer cannot see another buyer's RFQs, targets, or messages.

Supplier isolation is enforced via the token: every token route queries rfq_invites to get the supplier_id and rfq_id for that token. GET /api/rfq-by-token/{token}/quotes/mine queries `WHERE rfq_id=? AND supplier_id=?` using values from the invite. POST /api/messages with token-based auth extracts supplier_id from the invite and creates messages only for that supplier and RFQ. A supplier cannot access another supplier's invites, quotes, or messages.

Supplier visibility: the GET /api/rfqs/{id}/suppliers/{supplier_id} endpoint verifies the buyer owns the RFQ, then verifies the supplier was invited (by checking rfq_invites for a non-revoked entry), then returns the supplier's profile and latest quote. A supplier cannot see other suppliers' names or quotes, cannot see which suppliers are winning, and cannot see the buyer's other RFQs.

### Test coverage

The integration review document reports 46 API tests passing (test_e2e.py, test_message_endpoints.py, test_quote_endpoints.py, test_supplier_endpoints.py, test_visibility_endpoints.py). The three core pipeline tests (test_seed_has_rfqs, test_seed_has_suppliers, test_seed_has_messages) pass. TypeScript compilation passes with no errors. Frontend validators (161 tests) all pass.

The seed script executes successfully and populates 2 RFQs, 3 suppliers, 9 products (3 per supplier), 22 messages across multiple threads, 9 quotes (3 v1, 3 v2 for RFQ-001; 3 v1 for RFQ-002), 4 targets, and placeholder JPEGs. Data is labeled as synthetic, allowing the buyer and supplier dashboards to identify demo records.

Not explicitly tested by the review: token revocation behavior (rfq_invites.revoked=1 is set by the schema but no endpoint exercises it), bulk operations, concurrent quote submissions during the decision window (race condition if two suppliers submit quotes simultaneously after decided_quote_id is set), and message ordering on the frontend under high message volume.

### TypeScript contract alignment

All TypeScript contracts in src/contracts.ts mirror the Pydantic models from api/app/models/__init__.py. RFQCreate, RFQRead, RFQInviteRead, RFQByTokenRead match their Python counterparts. QuoteCreate and QuoteRead include all fields: price, lead_days, packing_json (optional), notes (optional), version, rejected. SupplierProfileCreate/Read, ProductCreate/Read, TargetCreate/Read, MessageCreate/Read, and RFQSupplierView all align. Optional fields (decided_quote_id, verification_json, photo_path, supplier_id on messages, etc.) are marked optional in both layers. TypeScript compilation passes with no errors.

### Database schema and WAL mode

The database uses SQLite with WAL (Write-Ahead Logging) mode enabled via `PRAGMA journal_mode=WAL` in both init_db() and get_db(). WAL mode allows concurrent reads while writes are in flight, improving availability for the buyer/supplier dashboard polling scenario (2-second updates).

Schema includes rfqs, rfq_invites, quotes (with unique constraint on rfq_id, supplier_id, version), targets, supplier_profiles, products, and messages. Foreign key relationships link invites and quotes to rfqs, all to supplier_profiles. The messages table has no unique constraints, allowing multiple messages in the same thread.

The seed script rebuilds the database by deleting the existing db file and WAL/SHM sidecars, then calling init_db() to recreate schema, then inserting synthetic data. This ensures a clean state for demo purposes.

### Authentication hardcoding risk

The JWT_SECRET in auth.py is defined as:

```python
JWT_SECRET = os.getenv('SUPABASE_JWT_SECRET', 'gsGZqpU1WYw4EM7pfqVY+/QTFKms4RjN2uVZodeSUQt4+mh9wswMoEOMVBiwVW6IEfVVh8C3FHFpl146ghY/Sg==')
```

The hardcoded default allows the code to run without the environment variable being set, which could happen if:
- A developer forgets to set the env var locally
- A production deployment script fails to set it
- The code is committed with the fallback in place and someone accidentally uses it

In those cases, every backend instance uses the same hardcoded secret, creating a shared key that could be reverse-engineered or leaked. The intent was likely to ease local development, but it creates a risk window where production could run with a known secret.

Recommend: Require SUPABASE_JWT_SECRET at startup and raise an error if not set. Local development can set the env var in a .env file or CI/CD pipeline. This forces explicit configuration and prevents accidental use of shared secrets.

### Message endpoint authorization gap

The POST /api/messages endpoint uses `message_data.sender_type` to determine whether the sender is a buyer or supplier:

```python
if message_data.sender_type == 'buyer':
    # Verify JWT and RFQ ownership
    supplier_id = message_data.supplier_id or current_user['user_id']
elif message_data.sender_type == 'supplier':
    # Verify token and extract supplier_id from invite
    supplier_id = invite['supplier_id']
```

When a buyer posts a message, the supplier_id is taken from message_data.supplier_id if provided, otherwise from current_user['user_id']. This creates two issues:

1. If the buyer does not provide supplier_id, the message is stored with supplier_id=current_user['user_id'], which is the buyer's UUID. When the GET /api/messages endpoint queries for messages where supplier_id=?, it could return messages that were posted by the buyer about themselves, causing confusion.

2. If the buyer provides an invalid supplier_id (not actually invited to the RFQ), there is no validation. The message is still created and associated with that supplier_id, even though the supplier was never invited. Later retrieval would allow the buyer to fetch those messages, but the supplier would not see them (because their token only grants access to their own invited RFQs).

Recommend: For buyer messages, require supplier_id as a mandatory field and validate that the supplier was invited to the RFQ (check rfq_invites for a non-revoked entry). This ensures messages always go to a specific, valid supplier and prevents orphaned or misrouted messages.

</details>

---

<details>
<summary>File map</summary>

- **api/app/main.py** — 16 endpoints: RFQ CRUD (POST/GET /api/rfqs, GET /api/rfqs/{id}), targets (POST /api/rfqs/{id}/targets), token quote (POST/GET /api/rfq-by-token/{token}/quotes*), supplier profile (GET/PUT /api/supplier/profile), products (GET/POST/PUT/DELETE /api/supplier/products, POST /api/supplier/products/{id}/photo), visibility (GET /api/rfqs/{id}/suppliers/{supplier_id}), messaging (GET/POST /api/messages), health check.
- **api/app/auth.py** — JWT verification from Authorization header, extracts sub and email claims, hardcoded default JWT_SECRET.
- **api/app/models/__init__.py** — Pydantic models for all request/response types, matching TypeScript contracts.
- **api/app/db.py** — SQLite schema initialization, WAL mode, context manager for connections.
- **src/contracts.ts** — TypeScript interfaces mirroring Pydantic models, fully aligned.
- **api/seed.py** — Seed script generating synthetic data: 2 RFQs, 3 suppliers, 9 products, 22 messages, 9 quotes, 4 targets, placeholder JPEGs.

Full diff available in git history against base branch.

</details>
