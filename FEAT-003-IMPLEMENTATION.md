# FEAT-003: Quote Versioning & Supplier Profile/Products Endpoints

## Implementation Complete ✅

All 9 endpoints and 18 tests successfully implemented and passing.

### Files Created

#### Backend API
- **api/app/db.py** - SQLite database with WAL mode, schema initialization, and connection management
- **api/app/auth.py** - JWT token verification with Supabase secret
- **api/app/main.py** - FastAPI application with 9 endpoints
- **api/app/models/__init__.py** - Pydantic models for all request/response types
- **api/app/__init__.py** - Package marker
- **api/requirements.txt** - Python dependencies

#### Tests
- **api/tests/test_quote_endpoints.py** - 6 tests for quote versioning endpoints
- **api/tests/test_supplier_endpoints.py** - 12 tests for profile and product endpoints
- **api/tests/__init__.py** - Package marker

### Endpoints Implemented

#### Quote Versioning (Token-based)
1. **POST /api/rfq-by-token/{token}/quotes**
   - Submit new quote version
   - Auto-increments version per supplier/RFQ
   - Rejects if RFQ already decided

2. **GET /api/rfq-by-token/{token}/quotes/mine**
   - Fetch all quote versions for supplier
   - Ordered by version DESC (newest first)

#### Supplier Profile (JWT auth)
3. **GET /api/supplier/profile**
   - Fetch authenticated user's profile
   - Returns 404 if missing

4. **PUT /api/supplier/profile**
   - Create or update supplier profile
   - Upserts profile data

#### Supplier Products (JWT auth)
5. **GET /api/supplier/products**
   - List all products for supplier (paginated)
   - Query params: limit (1-100, default 20), offset (default 0)

6. **POST /api/supplier/products**
   - Create new product
   - Auto-generates UUID and timestamp

7. **PUT /api/supplier/products/{product_id}**
   - Update product name and category
   - Returns 403 if not owner

8. **DELETE /api/supplier/products/{product_id}**
   - Delete product and associated photo file
   - Returns 403 if not owner
   - Returns 204 No Content on success

9. **POST /api/supplier/products/{product_id}/photo**
   - Upload product photo
   - Saves to `api/data/products/{product_id}.jpg`
   - Updates photo_path in database
   - Returns 403 if not owner

### Database Schema

```sql
-- RFQs (buyer requests)
rfqs(id, buyer_id, item, quantity_needed, need_by_days, created_at, decided_quote_id)

-- RFQ Invites (tokens per supplier, revocable)
rfq_invites(id, rfq_id, supplier_id, token, revoked, created_at)

-- Quotes (versioned per supplier per RFQ)
quotes(id, rfq_id, supplier_id, version, price, lead_days, packing_json, notes, submitted_at, rejected)

-- Supplier Profiles
supplier_profiles(id, email, company, state, business_type, categories, regions, default_lead_days, gst_inclusive_default, verification_json, created_at)

-- Products
products(id, supplier_id, name, category, photo_path, created_at)

-- Additional tables
targets(id, rfq_id, target_type, target_value, created_at)
messages(id, rfq_id, supplier_id, sender_id, content, created_at)
```

### Pydantic Models

- **QuoteCreate/QuoteRead** - Quote submission and response
- **SupplierProfileCreate/SupplierProfileRead** - Profile management
- **ProductCreate/ProductRead** - Product management
- **RFQCreate/RFQRead** - RFQ data
- **RFQInviteRead/RFQByTokenRead** - Token-based RFQ access
- **TargetCreate/TargetRead** - Negotiation targets
- **MessageCreate/MessageRead** - Threaded messages

### Authentication

- JWT verification via Supabase secret
- Token extracted from `Authorization: Bearer {token}` header
- Validates `sub` claim (user_id)
- Skips audience validation (configurable for testing)

### Test Results

```
18 passed in 2.59s

Quote Endpoints (6 tests):
✅ test_post_quote_creates_v1
✅ test_post_second_quote_creates_v2
✅ test_reject_quote_after_decision
✅ test_get_quotes_mine_returns_all_versions
✅ test_invalid_token_quote_returns_404
✅ test_invalid_token_post_quote_returns_404

Supplier Endpoints (12 tests):
✅ test_get_supplier_profile_404_when_missing
✅ test_put_supplier_profile_upsert
✅ test_put_supplier_profile_updates_existing
✅ test_get_supplier_profile_after_put
✅ test_post_product_creates_with_supplier_id
✅ test_get_supplier_products
✅ test_put_product_own_returns_200
✅ test_put_product_other_supplier_returns_403
✅ test_delete_product_own_returns_204
✅ test_delete_product_other_returns_403
✅ test_photo_upload_saves_file
✅ test_photo_upload_other_supplier_returns_403
```

### Key Implementation Details

1. **Quote Versioning**: Auto-incremented per (rfq_id, supplier_id) pair using `MAX(version) + 1`
2. **Token-based Access**: Suppliers access RFQs via invite tokens, can't see other suppliers' quotes or RFQs
3. **Authorization**: All endpoints validate supplier ownership of resources (403 on mismatch)
4. **JSON Fields**: categories and regions stored as JSON TEXT, auto-serialized on write/read
5. **File Upload**: Product photos saved to `api/data/products/` directory with UUID as filename
6. **Pagination**: Products endpoint supports limit/offset query parameters
7. **Soft Delete**: Quotes have `rejected` flag (not physically deleted)
8. **Timestamps**: Unix timestamps (seconds since epoch) in UTC

### Running Tests

```bash
cd api
pytest tests/ -v
pytest tests/test_quote_endpoints.py -v
pytest tests/test_supplier_endpoints.py -v
```

### Running Server

```bash
cd api
uvicorn app.main:app --port 8000 --reload
```

### Git Commit

```
feat: FEAT-003 quote versioning and supplier profile/products endpoints
```

---

**Status**: ✅ COMPLETE - All 9 endpoints implemented, 18 tests passing, ready for integration with frontend and dashboard.
