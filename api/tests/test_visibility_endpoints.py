"""Tests for visibility endpoints (GET /api/rfqs/{rfq_id}/suppliers/{supplier_id})."""

import pytest
import json
import uuid
import tempfile
import shutil
import sys
import os
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch
import jwt

# Add api directory to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Temporarily override DB path to use test database
TEST_DB_DIR = tempfile.mkdtemp()
TEST_DB_PATH = Path(TEST_DB_DIR) / 'test.db'

with patch('app.db.DB_PATH', str(TEST_DB_PATH)):
    from app.main import app
    from app.db import init_db, get_db, now_unix
    from app.auth import JWT_SECRET, JWT_ALGORITHM

# Initialize test database
init_db()

client = TestClient(app)

# ============ Fixtures ============

def create_jwt_token(user_id, email='test@buyer.com'):
    """Create a valid JWT token for testing."""
    payload = {
        'sub': user_id,
        'email': email,
        'aud': 'authenticated'
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

@pytest.fixture(scope='function')
def setup_buyer_rfq_suppliers():
    """Setup RFQ with 2 suppliers, quotes, and invites."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Create buyer
        buyer_id = 'buyer-' + str(uuid.uuid4())[:8]
        
        # Create 2 suppliers with profiles
        supplier1_id = str(uuid.uuid4())
        supplier1_email = f'supplier1-{supplier1_id[:8]}@test.com'
        cursor.execute(
            '''INSERT INTO supplier_profiles 
               (id, email, company, state, business_type, categories, regions, default_lead_days, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (supplier1_id, supplier1_email, 'Supplier One', 'MH', 'manufacturer',
             json.dumps(['electronics']), json.dumps(['north']), 5, now_unix())
        )
        
        supplier2_id = str(uuid.uuid4())
        supplier2_email = f'supplier2-{supplier2_id[:8]}@test.com'
        cursor.execute(
            '''INSERT INTO supplier_profiles 
               (id, email, company, state, business_type, categories, regions, default_lead_days, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (supplier2_id, supplier2_email, 'Supplier Two', 'KA', 'distributor',
             json.dumps(['electronics']), json.dumps(['south']), 7, now_unix())
        )
        
        # Create RFQ owned by buyer
        rfq_id = str(uuid.uuid4())
        cursor.execute(
            '''INSERT INTO rfqs (id, buyer_id, item, quantity_needed, need_by_days, created_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (rfq_id, buyer_id, 'Widget', 100, 10, now_unix())
        )
        
        # Create invites for both suppliers
        token1 = str(uuid.uuid4())
        invite_id1 = str(uuid.uuid4())
        cursor.execute(
            '''INSERT INTO rfq_invites (id, rfq_id, supplier_id, token, revoked, created_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (invite_id1, rfq_id, supplier1_id, token1, 0, now_unix())
        )
        
        token2 = str(uuid.uuid4())
        invite_id2 = str(uuid.uuid4())
        cursor.execute(
            '''INSERT INTO rfq_invites (id, rfq_id, supplier_id, token, revoked, created_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (invite_id2, rfq_id, supplier2_id, token2, 0, now_unix())
        )
        
        # Create quotes for both suppliers
        quote1_id = str(uuid.uuid4())
        cursor.execute(
            '''INSERT INTO quotes (id, rfq_id, supplier_id, version, price, lead_days, submitted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (quote1_id, rfq_id, supplier1_id, 1, 50.0, 5, now_unix())
        )
        
        quote2_id = str(uuid.uuid4())
        cursor.execute(
            '''INSERT INTO quotes (id, rfq_id, supplier_id, version, price, lead_days, submitted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (quote2_id, rfq_id, supplier2_id, 1, 60.0, 7, now_unix())
        )
        
        conn.commit()
        
        yield {
            'buyer_id': buyer_id,
            'rfq_id': rfq_id,
            'supplier1_id': supplier1_id,
            'supplier2_id': supplier2_id,
            'quote1_id': quote1_id,
            'quote2_id': quote2_id,
            'token1': token1,
            'token2': token2
        }

# ============ Tests ============

def test_buyer_sees_supplier_view(setup_buyer_rfq_suppliers):
    """Test: GET /api/rfqs/{id}/suppliers/{sid} returns supplier profile + quote."""
    data = setup_buyer_rfq_suppliers
    token = create_jwt_token(data['buyer_id'])
    
    headers = {'Authorization': f'Bearer {token}'}
    response = client.get(
        f'/api/rfqs/{data["rfq_id"]}/suppliers/{data["supplier1_id"]}',
        headers=headers
    )
    
    assert response.status_code == 200
    body = response.json()
    
    assert body['supplier'] is not None
    assert body['supplier']['id'] == data['supplier1_id']
    assert body['supplier']['company'] == 'Supplier One'
    
    assert body['latest_quote'] is not None
    assert body['latest_quote']['id'] == data['quote1_id']
    assert body['latest_quote']['price'] == 50.0

def test_buyer_cannot_see_uninvited_supplier(setup_buyer_rfq_suppliers):
    """Test: GET for uninvited supplier returns 403."""
    data = setup_buyer_rfq_suppliers
    token = create_jwt_token(data['buyer_id'])
    
    # Create another supplier not invited to this RFQ
    with get_db() as conn:
        cursor = conn.cursor()
        uninvited_id = str(uuid.uuid4())
        cursor.execute(
            '''INSERT INTO supplier_profiles 
               (id, email, company, state, business_type, categories, regions, default_lead_days, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (uninvited_id, f'uninvited-{uninvited_id[:8]}@test.com', 'Uninvited', 'TN', 'manufacturer',
             json.dumps(['electronics']), json.dumps(['south']), 5, now_unix())
        )
        conn.commit()
    
    headers = {'Authorization': f'Bearer {token}'}
    response = client.get(
        f'/api/rfqs/{data["rfq_id"]}/suppliers/{uninvited_id}',
        headers=headers
    )
    
    assert response.status_code == 403

def test_wrong_buyer_gets_403(setup_buyer_rfq_suppliers):
    """Test: Different buyer cannot view supplier for RFQ."""
    data = setup_buyer_rfq_suppliers
    
    # Create token for different buyer
    different_buyer_id = 'buyer-different-' + str(uuid.uuid4())[:8]
    token = create_jwt_token(different_buyer_id)
    
    headers = {'Authorization': f'Bearer {token}'}
    response = client.get(
        f'/api/rfqs/{data["rfq_id"]}/suppliers/{data["supplier1_id"]}',
        headers=headers
    )
    
    assert response.status_code == 403

def test_supplier_view_returns_only_that_suppliers_data(setup_buyer_rfq_suppliers):
    """Test: GET for supplier1 does not include supplier2 data."""
    data = setup_buyer_rfq_suppliers
    token = create_jwt_token(data['buyer_id'])
    
    # Get supplier1 view
    headers = {'Authorization': f'Bearer {token}'}
    response = client.get(
        f'/api/rfqs/{data["rfq_id"]}/suppliers/{data["supplier1_id"]}',
        headers=headers
    )
    
    assert response.status_code == 200
    body = response.json()
    
    # Should only have supplier1 data
    assert body['supplier']['id'] == data['supplier1_id']
    assert body['latest_quote']['supplier_id'] == data['supplier1_id']
    
    # Should NOT match supplier2 data
    assert body['supplier']['id'] != data['supplier2_id']

def test_revoked_invite_returns_403(setup_buyer_rfq_suppliers):
    """Test: GET for revoked invite returns 403."""
    data = setup_buyer_rfq_suppliers
    token = create_jwt_token(data['buyer_id'])
    
    # Revoke supplier1's invite
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE rfq_invites SET revoked=1 WHERE rfq_id=? AND supplier_id=?',
            (data['rfq_id'], data['supplier1_id'])
        )
        conn.commit()
    
    headers = {'Authorization': f'Bearer {token}'}
    response = client.get(
        f'/api/rfqs/{data["rfq_id"]}/suppliers/{data["supplier1_id"]}',
        headers=headers
    )
    
    assert response.status_code == 403

def test_nonexistent_rfq_returns_404(setup_buyer_rfq_suppliers):
    """Test: GET for nonexistent RFQ returns 404."""
    data = setup_buyer_rfq_suppliers
    token = create_jwt_token(data['buyer_id'])
    
    headers = {'Authorization': f'Bearer {token}'}
    response = client.get(
        f'/api/rfqs/nonexistent-rfq-id/suppliers/{data["supplier1_id"]}',
        headers=headers
    )
    
    assert response.status_code == 404

# ============ Cleanup ============

@pytest.fixture(scope='session', autouse=True)
def cleanup():
    """Cleanup test database."""
    yield
    if Path(TEST_DB_DIR).exists():
        shutil.rmtree(TEST_DB_DIR)
