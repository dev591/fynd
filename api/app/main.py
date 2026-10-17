"""FastAPI application with quote versioning and supplier endpoints (FEAT-003)."""

import os
import json
import uuid
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db, get_db, dict_from_row, now_unix
from .auth import get_current_user
from .models import (
    QuoteCreate, QuoteRead,
    SupplierProfileCreate, SupplierProfileRead,
    ProductCreate, ProductRead,
    RFQCreate, RFQRead, RFQInviteRead, RFQByTokenRead,
    TargetCreate, TargetRead,
    MessageCreate, MessageRead, RFQSupplierView
)

# Initialize database
init_db()

app = FastAPI(title='FYND API', version='1.0.0')

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

# Create product photos directory
PRODUCT_PHOTOS_DIR = Path(__file__).parent.parent / 'data' / 'products'
PRODUCT_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

# ============ Health Check ============

@app.get('/health')
def health_check():
    """Health check endpoint."""
    return {'ok': True, 'version': '1.0.0'}

# ============ RFQ Endpoints (Buyer) ============

@app.post('/api/rfqs', response_model=RFQRead)
def post_rfq(
    rfq_data: RFQCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    POST /api/rfqs
    Create a new RFQ (JWT auth required).
    Returns the created RFQ with id and timestamps.
    """
    buyer_id = current_user['user_id']
    rfq_id = str(uuid.uuid4())
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO rfqs (id, buyer_id, item, quantity_needed, need_by_days, created_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (rfq_id, buyer_id, rfq_data.item, rfq_data.quantity_needed, 
             rfq_data.need_by_days, now_unix())
        )
        conn.commit()
        
        cursor.execute('SELECT * FROM rfqs WHERE id=?', (rfq_id,))
        rfq = cursor.fetchone()
        
        return RFQRead(
            id=rfq['id'],
            buyer_id=rfq['buyer_id'],
            item=rfq['item'],
            quantity_needed=rfq['quantity_needed'],
            need_by_days=rfq['need_by_days'],
            created_at=rfq['created_at'],
            decided_quote_id=rfq['decided_quote_id']
        )

@app.get('/api/rfqs', response_model=list[RFQRead])
def get_rfqs(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    GET /api/rfqs
    List all RFQs for the current buyer (JWT auth required).
    Paginated with limit/offset.
    """
    buyer_id = current_user['user_id']
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM rfqs WHERE buyer_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?',
            (buyer_id, limit, offset)
        )
        rfqs = cursor.fetchall()
        
        return [
            RFQRead(
                id=r['id'],
                buyer_id=r['buyer_id'],
                item=r['item'],
                quantity_needed=r['quantity_needed'],
                need_by_days=r['need_by_days'],
                created_at=r['created_at'],
                decided_quote_id=r['decided_quote_id']
            )
            for r in rfqs
        ]

@app.get('/api/rfqs/{rfq_id}', response_model=RFQRead)
def get_rfq(
    rfq_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    GET /api/rfqs/{rfq_id}
    Get a specific RFQ (JWT auth required, buyer must own it).
    """
    buyer_id = current_user['user_id']
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM rfqs WHERE id=?',
            (rfq_id,)
        )
        rfq = cursor.fetchone()
        
        if not rfq:
            raise HTTPException(status_code=404, detail='RFQ not found')
        
        if rfq['buyer_id'] != buyer_id:
            raise HTTPException(status_code=403, detail='Not authorized to view this RFQ')
        
        return RFQRead(
            id=rfq['id'],
            buyer_id=rfq['buyer_id'],
            item=rfq['item'],
            quantity_needed=rfq['quantity_needed'],
            need_by_days=rfq['need_by_days'],
            created_at=rfq['created_at'],
            decided_quote_id=rfq['decided_quote_id']
        )

@app.post('/api/rfqs/{rfq_id}/targets', response_model=TargetRead)
def post_rfq_target(
    rfq_id: str,
    target_data: TargetCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    POST /api/rfqs/{rfq_id}/targets
    Add negotiation targets to an RFQ (JWT auth required, buyer must own it).
    target_type can be 'price', 'lead_days', etc.
    """
    buyer_id = current_user['user_id']
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Verify buyer owns this RFQ
        cursor.execute(
            'SELECT buyer_id FROM rfqs WHERE id=?',
            (rfq_id,)
        )
        rfq = cursor.fetchone()
        
        if not rfq:
            raise HTTPException(status_code=404, detail='RFQ not found')
        
        if rfq['buyer_id'] != buyer_id:
            raise HTTPException(status_code=403, detail='Not authorized to update this RFQ')
        
        # Create target
        target_id = str(uuid.uuid4())
        cursor.execute(
            '''INSERT INTO targets (id, rfq_id, target_type, target_value, created_at)
               VALUES (?, ?, ?, ?, ?)''',
            (target_id, rfq_id, target_data.target_type, target_data.target_value, now_unix())
        )
        conn.commit()
        
        # Fetch and return
        cursor.execute('SELECT * FROM targets WHERE id=?', (target_id,))
        target = cursor.fetchone()
        
        return TargetRead(
            id=target['id'],
            rfq_id=target['rfq_id'],
            target_type=target['target_type'],
            target_value=target['target_value'],
            created_at=target['created_at']
        )

# ============ Quote Endpoints (Token-based) ============

@app.post('/api/rfq-by-token/{token}/quotes', response_model=QuoteRead)
def post_quote(token: str, quote_data: QuoteCreate):
    """
    POST /api/rfq-by-token/{token}/quotes
    Submit a new quote version for an RFQ.
    Supplier identified by token, version auto-incremented.
    Returns 400 if RFQ already has decided_quote_id.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Validate token and get rfq_id + supplier_id
        cursor.execute(
            'SELECT rfq_id, supplier_id FROM rfq_invites WHERE token=? AND revoked=0',
            (token,)
        )
        invite = cursor.fetchone()
        
        if not invite:
            raise HTTPException(status_code=404, detail='Invalid or revoked token')
        
        rfq_id, supplier_id = invite['rfq_id'], invite['supplier_id']
        
        # Check if RFQ is already decided
        cursor.execute(
            'SELECT decided_quote_id FROM rfqs WHERE id=?',
            (rfq_id,)
        )
        rfq = cursor.fetchone()
        
        if not rfq:
            raise HTTPException(status_code=404, detail='RFQ not found')
        
        if rfq['decided_quote_id'] is not None:
            raise HTTPException(status_code=400, detail='RFQ has already been decided')
        
        # Get next version
        cursor.execute(
            'SELECT MAX(version) as max_version FROM quotes WHERE rfq_id=? AND supplier_id=?',
            (rfq_id, supplier_id)
        )
        result = cursor.fetchone()
        max_version = result['max_version'] if result['max_version'] is not None else 0
        new_version = max_version + 1
        
        # Create quote
        quote_id = str(uuid.uuid4())
        cursor.execute(
            '''INSERT INTO quotes (id, rfq_id, supplier_id, version, price, lead_days, packing_json, notes, submitted_at, rejected)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (quote_id, rfq_id, supplier_id, new_version, quote_data.price, quote_data.lead_days,
             quote_data.packing_json, quote_data.notes, now_unix(), 0)
        )
        conn.commit()
        
        # Fetch and return
        cursor.execute('SELECT * FROM quotes WHERE id=?', (quote_id,))
        quote = cursor.fetchone()
        
        return QuoteRead(
            id=quote['id'],
            rfq_id=quote['rfq_id'],
            supplier_id=quote['supplier_id'],
            version=quote['version'],
            price=quote['price'],
            lead_days=quote['lead_days'],
            packing_json=quote['packing_json'],
            notes=quote['notes'],
            submitted_at=quote['submitted_at'],
            rejected=bool(quote['rejected'])
        )

@app.get('/api/rfq-by-token/{token}/quotes/mine', response_model=list[QuoteRead])
def get_quotes_mine(token: str):
    """
    GET /api/rfq-by-token/{token}/quotes/mine
    Get all quote versions for this supplier on this RFQ.
    Ordered by version DESC (newest first).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Validate token
        cursor.execute(
            'SELECT rfq_id, supplier_id FROM rfq_invites WHERE token=? AND revoked=0',
            (token,)
        )
        invite = cursor.fetchone()
        
        if not invite:
            raise HTTPException(status_code=404, detail='Invalid or revoked token')
        
        rfq_id, supplier_id = invite['rfq_id'], invite['supplier_id']
        
        # Fetch all quotes ordered by version DESC
        cursor.execute(
            '''SELECT * FROM quotes WHERE rfq_id=? AND supplier_id=? ORDER BY version DESC''',
            (rfq_id, supplier_id)
        )
        quotes = cursor.fetchall()
        
        return [
            QuoteRead(
                id=q['id'],
                rfq_id=q['rfq_id'],
                supplier_id=q['supplier_id'],
                version=q['version'],
                price=q['price'],
                lead_days=q['lead_days'],
                packing_json=q['packing_json'],
                notes=q['notes'],
                submitted_at=q['submitted_at'],
                rejected=bool(q['rejected'])
            )
            for q in quotes
        ]

# ============ Supplier Profile Endpoints ============

@app.get('/api/supplier/profile', response_model=SupplierProfileRead)
def get_supplier_profile(current_user: dict = Depends(get_current_user)):
    """
    GET /api/supplier/profile
    Get current user's supplier profile (JWT auth required).
    Returns 404 if not found.
    """
    user_id = current_user['user_id']
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM supplier_profiles WHERE id=?',
            (user_id,)
        )
        profile = cursor.fetchone()
        
        if not profile:
            raise HTTPException(status_code=404, detail='Supplier profile not found')
        
        return SupplierProfileRead(
            id=profile['id'],
            email=profile['email'],
            company=profile['company'],
            state=profile['state'],
            business_type=profile['business_type'],
            categories=json.loads(profile['categories']),
            regions=json.loads(profile['regions']),
            default_lead_days=profile['default_lead_days'],
            gst_inclusive_default=bool(profile['gst_inclusive_default']),
            verification_json=profile['verification_json'],
            created_at=profile['created_at']
        )

@app.put('/api/supplier/profile', response_model=SupplierProfileRead)
def put_supplier_profile(
    profile_data: SupplierProfileCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    PUT /api/supplier/profile
    Upsert supplier profile (JWT auth required).
    Creates if missing, updates if exists.
    """
    user_id = current_user['user_id']
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if exists
        cursor.execute(
            'SELECT created_at FROM supplier_profiles WHERE id=?',
            (user_id,)
        )
        existing = cursor.fetchone()
        created_at = existing['created_at'] if existing else now_unix()
        
        # Insert or replace
        cursor.execute(
            '''INSERT OR REPLACE INTO supplier_profiles 
               (id, email, company, state, business_type, categories, regions, default_lead_days, gst_inclusive_default, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, profile_data.email, profile_data.company, profile_data.state,
             profile_data.business_type, json.dumps(profile_data.categories),
             json.dumps(profile_data.regions), profile_data.default_lead_days,
             int(profile_data.gst_inclusive_default), created_at)
        )
        conn.commit()
        
        # Fetch and return
        cursor.execute('SELECT * FROM supplier_profiles WHERE id=?', (user_id,))
        profile = cursor.fetchone()
        
        return SupplierProfileRead(
            id=profile['id'],
            email=profile['email'],
            company=profile['company'],
            state=profile['state'],
            business_type=profile['business_type'],
            categories=json.loads(profile['categories']),
            regions=json.loads(profile['regions']),
            default_lead_days=profile['default_lead_days'],
            gst_inclusive_default=bool(profile['gst_inclusive_default']),
            verification_json=profile['verification_json'],
            created_at=profile['created_at']
        )

# ============ Supplier Products Endpoints ============

@app.get('/api/supplier/products', response_model=list[ProductRead])
def get_supplier_products(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    GET /api/supplier/products
    List all products for current supplier (paginated).
    """
    user_id = current_user['user_id']
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM products WHERE supplier_id=? LIMIT ? OFFSET ?',
            (user_id, limit, offset)
        )
        products = cursor.fetchall()
        
        return [
            ProductRead(
                id=p['id'],
                supplier_id=p['supplier_id'],
                name=p['name'],
                category=p['category'],
                photo_path=p['photo_path'],
                created_at=p['created_at']
            )
            for p in products
        ]

@app.post('/api/supplier/products', response_model=ProductRead)
def post_supplier_product(
    product_data: ProductCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    POST /api/supplier/products
    Create a new product for current supplier.
    """
    user_id = current_user['user_id']
    product_id = str(uuid.uuid4())
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO products (id, supplier_id, name, category, photo_path, created_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (product_id, user_id, product_data.name, product_data.category, None, now_unix())
        )
        conn.commit()
        
        cursor.execute('SELECT * FROM products WHERE id=?', (product_id,))
        product = cursor.fetchone()
        
        return ProductRead(
            id=product['id'],
            supplier_id=product['supplier_id'],
            name=product['name'],
            category=product['category'],
            photo_path=product['photo_path'],
            created_at=product['created_at']
        )

@app.put('/api/supplier/products/{product_id}', response_model=ProductRead)
def put_supplier_product(
    product_id: str,
    product_data: ProductCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    PUT /api/supplier/products/{product_id}
    Update product name and category (owner only).
    Returns 403 if not owner.
    """
    user_id = current_user['user_id']
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check ownership
        cursor.execute(
            'SELECT supplier_id FROM products WHERE id=?',
            (product_id,)
        )
        product = cursor.fetchone()
        
        if not product:
            raise HTTPException(status_code=404, detail='Product not found')
        
        if product['supplier_id'] != user_id:
            raise HTTPException(status_code=403, detail='Not authorized to update this product')
        
        # Update
        cursor.execute(
            'UPDATE products SET name=?, category=? WHERE id=?',
            (product_data.name, product_data.category, product_id)
        )
        conn.commit()
        
        # Fetch and return
        cursor.execute('SELECT * FROM products WHERE id=?', (product_id,))
        updated = cursor.fetchone()
        
        return ProductRead(
            id=updated['id'],
            supplier_id=updated['supplier_id'],
            name=updated['name'],
            category=updated['category'],
            photo_path=updated['photo_path'],
            created_at=updated['created_at']
        )

@app.delete('/api/supplier/products/{product_id}', status_code=204)
def delete_supplier_product(
    product_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    DELETE /api/supplier/products/{product_id}
    Delete product (owner only).
    Returns 403 if not owner.
    Returns 204 on success.
    """
    user_id = current_user['user_id']
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check ownership
        cursor.execute(
            'SELECT supplier_id, photo_path FROM products WHERE id=?',
            (product_id,)
        )
        product = cursor.fetchone()
        
        if not product:
            raise HTTPException(status_code=404, detail='Product not found')
        
        if product['supplier_id'] != user_id:
            raise HTTPException(status_code=403, detail='Not authorized to delete this product')
        
        # Delete photo file if exists
        if product['photo_path']:
            photo_file = Path(__file__).parent.parent / product['photo_path']
            if photo_file.exists():
                photo_file.unlink()
        
        # Delete product
        cursor.execute('DELETE FROM products WHERE id=?', (product_id,))
        conn.commit()
        
        return None

@app.post('/api/supplier/products/{product_id}/photo', response_model=ProductRead)
async def post_product_photo(
    product_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    POST /api/supplier/products/{product_id}/photo
    Upload product photo (owner only).
    Saves as {product_id}.jpg in api/data/products/.
    Returns 403 if not owner.
    """
    user_id = current_user['user_id']
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check ownership
        cursor.execute(
            'SELECT supplier_id FROM products WHERE id=?',
            (product_id,)
        )
        product = cursor.fetchone()
        
        if not product:
            raise HTTPException(status_code=404, detail='Product not found')
        
        if product['supplier_id'] != user_id:
            raise HTTPException(status_code=403, detail='Not authorized to upload for this product')
        
        # Save file
        file_path = PRODUCT_PHOTOS_DIR / f'{product_id}.jpg'
        with open(file_path, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        # Update photo_path
        photo_path = f'api/data/products/{product_id}.jpg'
        cursor.execute(
            'UPDATE products SET photo_path=? WHERE id=?',
            (photo_path, product_id)
        )
        conn.commit()
        
        # Fetch and return
        cursor.execute('SELECT * FROM products WHERE id=?', (product_id,))
        updated = cursor.fetchone()
        
        return ProductRead(
            id=updated['id'],
            supplier_id=updated['supplier_id'],
            name=updated['name'],
            category=updated['category'],
            photo_path=updated['photo_path'],
            created_at=updated['created_at']
        )

# ============ Visibility & Messaging Endpoints ============

@app.get('/api/rfqs/{rfq_id}/suppliers/{supplier_id}', response_model=RFQSupplierView)
def get_rfq_supplier_view(
    rfq_id: str,
    supplier_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    GET /api/rfqs/{rfq_id}/suppliers/{supplier_id}
    Buyer views a specific supplier for an RFQ.
    Requires JWT auth and RFQ.buyer_id == current_user['user_id'].
    Verify supplier_id appears in rfq_invites for this rfq (not revoked).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Verify RFQ exists and buyer owns it
        cursor.execute('SELECT buyer_id FROM rfqs WHERE id=?', (rfq_id,))
        rfq = cursor.fetchone()
        
        if not rfq:
            raise HTTPException(status_code=404, detail='RFQ not found')
        
        if rfq['buyer_id'] != current_user['user_id']:
            raise HTTPException(status_code=403, detail='Not authorized to view this RFQ')
        
        # Verify supplier was invited to this RFQ and invite not revoked
        cursor.execute(
            'SELECT revoked FROM rfq_invites WHERE rfq_id=? AND supplier_id=?',
            (rfq_id, supplier_id)
        )
        invite = cursor.fetchone()
        
        if not invite or invite['revoked']:
            raise HTTPException(status_code=403, detail='Supplier not invited or invite revoked')
        
        # Fetch supplier profile
        cursor.execute('SELECT * FROM supplier_profiles WHERE id=?', (supplier_id,))
        profile_row = cursor.fetchone()
        
        supplier_profile = None
        if profile_row:
            supplier_profile = SupplierProfileRead(
                id=profile_row['id'],
                email=profile_row['email'],
                company=profile_row['company'],
                state=profile_row['state'],
                business_type=profile_row['business_type'],
                categories=json.loads(profile_row['categories']),
                regions=json.loads(profile_row['regions']),
                default_lead_days=profile_row['default_lead_days'],
                gst_inclusive_default=bool(profile_row['gst_inclusive_default']),
                verification_json=profile_row['verification_json'],
                created_at=profile_row['created_at']
            )
        
        # Fetch latest quote
        cursor.execute(
            'SELECT * FROM quotes WHERE rfq_id=? AND supplier_id=? ORDER BY version DESC LIMIT 1',
            (rfq_id, supplier_id)
        )
        quote_row = cursor.fetchone()
        
        latest_quote = None
        if quote_row:
            latest_quote = QuoteRead(
                id=quote_row['id'],
                rfq_id=quote_row['rfq_id'],
                supplier_id=quote_row['supplier_id'],
                version=quote_row['version'],
                price=quote_row['price'],
                lead_days=quote_row['lead_days'],
                packing_json=quote_row['packing_json'],
                notes=quote_row['notes'],
                submitted_at=quote_row['submitted_at'],
                rejected=bool(quote_row['rejected'])
            )
        
        return RFQSupplierView(
            supplier=supplier_profile,
            latest_quote=latest_quote
        )

@app.get('/api/messages', response_model=list[MessageRead])
def get_messages(
    rfq_id: str = Query(...),
    supplier_id: str = Query(None),
    token: str = Query(None),
    request: Request = None
):
    """
    GET /api/messages?rfq_id=...&supplier_id=...&token=...
    Get messages for an RFQ/supplier thread.
    - If JWT present (no supplier_id/token): buyer sees full thread for this rfq
    - If token present: supplier sees their messages for this rfq
    - If JWT + supplier_id: buyer sees messages for specific supplier on this rfq
    """
    # Try to get current user from JWT (optional)
    current_user = None
    if request:
        try:
            current_user = get_current_user(request)
        except HTTPException:
            pass
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        if token:
            # Token-based access: supplier viewing their own messages
            cursor.execute(
                'SELECT rfq_id, supplier_id FROM rfq_invites WHERE token=? AND revoked=0',
                (token,)
            )
            invite = cursor.fetchone()
            
            if not invite:
                raise HTTPException(status_code=404, detail='Invalid or revoked token')
            
            invite_rfq_id, invite_supplier_id = invite['rfq_id'], invite['supplier_id']
            
            if invite_rfq_id != rfq_id:
                raise HTTPException(status_code=400, detail='Token does not match rfq_id')
            
            # Fetch messages for this supplier on this RFQ
            cursor.execute(
                'SELECT * FROM messages WHERE rfq_id=? AND supplier_id=? ORDER BY created_at ASC',
                (rfq_id, invite_supplier_id)
            )
        elif supplier_id:
            # JWT + supplier_id: buyer viewing messages for specific supplier
            if not current_user:
                raise HTTPException(status_code=401, detail='JWT required')
            
            cursor.execute('SELECT buyer_id FROM rfqs WHERE id=?', (rfq_id,))
            rfq = cursor.fetchone()
            
            if not rfq:
                raise HTTPException(status_code=404, detail='RFQ not found')
            
            if rfq['buyer_id'] != current_user['user_id']:
                raise HTTPException(status_code=403, detail='Not authorized to view this RFQ')
            
            cursor.execute(
                'SELECT * FROM messages WHERE rfq_id=? AND supplier_id=? ORDER BY created_at ASC',
                (rfq_id, supplier_id)
            )
        else:
            # JWT only: buyer sees all messages for this RFQ
            if not current_user:
                raise HTTPException(status_code=401, detail='JWT required')
            
            cursor.execute('SELECT buyer_id FROM rfqs WHERE id=?', (rfq_id,))
            rfq = cursor.fetchone()
            
            if not rfq:
                raise HTTPException(status_code=404, detail='RFQ not found')
            
            if rfq['buyer_id'] != current_user['user_id']:
                raise HTTPException(status_code=403, detail='Not authorized to view this RFQ')
            
            cursor.execute(
                'SELECT * FROM messages WHERE rfq_id=? ORDER BY created_at ASC',
                (rfq_id,)
            )
        
        messages = cursor.fetchall()
        
        return [
            MessageRead(
                id=m['id'],
                rfq_id=m['rfq_id'],
                supplier_id=m['supplier_id'],
                sender_type=m['sender_type'],
                content=m['content'],
                created_at=m['created_at']
            )
            for m in messages
        ]

@app.post('/api/messages', response_model=MessageRead)
def post_message(
    message_data: MessageCreate,
    request: Request
):
    """
    POST /api/messages
    Create a new message.
    - If sender_type='buyer': require JWT auth and user must own the RFQ
    - If sender_type='supplier': require token and validate via rfq_invites
    """
    # Try to get current user from JWT (optional)
    current_user = None
    try:
        current_user = get_current_user(request)
    except HTTPException:
        pass
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        if message_data.sender_type == 'buyer':
            # Buyer posting: require JWT, verify RFQ ownership
            if not current_user:
                raise HTTPException(status_code=401, detail='JWT required for buyer messages')
            
            cursor.execute('SELECT buyer_id FROM rfqs WHERE id=?', (message_data.rfq_id,))
            rfq = cursor.fetchone()
            
            if not rfq:
                raise HTTPException(status_code=404, detail='RFQ not found')
            
            if rfq['buyer_id'] != current_user['user_id']:
                raise HTTPException(status_code=403, detail='Not authorized to post to this RFQ')
            
            # Buyer posting should not specify supplier_id or token
            # Use the RFQ's buyer_id as a placeholder for supplier_id in the message
            supplier_id = message_data.supplier_id or current_user['user_id']
        
        elif message_data.sender_type == 'supplier':
            # Supplier posting: require token
            if not message_data.token:
                raise HTTPException(status_code=401, detail='Token required for supplier messages')
            
            cursor.execute(
                'SELECT rfq_id, supplier_id FROM rfq_invites WHERE token=? AND revoked=0',
                (message_data.token,)
            )
            invite = cursor.fetchone()
            
            if not invite:
                raise HTTPException(status_code=404, detail='Invalid or revoked token')
            
            if invite['rfq_id'] != message_data.rfq_id:
                raise HTTPException(status_code=400, detail='Token does not match rfq_id')
            
            supplier_id = invite['supplier_id']
        
        else:
            raise HTTPException(status_code=400, detail='Invalid sender_type')
        
        # Create message
        message_id = str(uuid.uuid4())
        cursor.execute(
            '''INSERT INTO messages (id, rfq_id, supplier_id, sender_type, content, created_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (message_id, message_data.rfq_id, supplier_id, message_data.sender_type,
             message_data.content, now_unix())
        )
        conn.commit()
        
        # Fetch and return
        cursor.execute('SELECT * FROM messages WHERE id=?', (message_id,))
        msg = cursor.fetchone()
        
        return MessageRead(
            id=msg['id'],
            rfq_id=msg['rfq_id'],
            supplier_id=msg['supplier_id'],
            sender_type=msg['sender_type'],
            content=msg['content'],
            created_at=msg['created_at']
        )

# Serve product photos as static files
app.mount('/api/data', StaticFiles(directory=Path(__file__).parent.parent / 'data'), name='data')
