"""Tests for quote versioning endpoints."""

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

# Add api directory to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Temporarily override DB path to use test database
TEST_DB_DIR = tempfile.mkdtemp()
TEST_DB_PATH = Path(TEST_DB_DIR) / 'test.db'

with patch('app.db.DB_PATH', str(TEST_DB_PATH)):
    from app.main import app
    from app.db import init_db, get_db, now_unix

# Initialize test database
init_db()

client = TestClient(app)

# ============ Fixtures ============

@pytest.fixture(scope='function')
def setup_test_data():
    """Setup test RFQ, supplier, and invite."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Create supplier profile with unique email
        supplier_id = str(uuid.uuid4())
        supplier_email = f'supplier-{supplier_id[:8]}@test.com'
        cursor.execute(
            '''INSERT INTO supplier_profiles 
               (id, email, company, state, business_type, categories, regions, default_lead_days, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (supplier_id, supplier_email, 'Test Supplier', 'MH', 'manufacturer',
             json.dumps(['electronics']), json.dumps(['north']), 5, now_unix())
        )
        
        # Create RFQ
        rfq_id = str(uuid.uuid4())
        buyer_id = 'buyer-123'
        cursor.execute(
            '''INSERT INTO rfqs (id, buyer_id, item, quantity_needed, need_by_days, created_at, decided_quote_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (rfq_id, buyer_id, 'Widget', 100, 10, now_unix(), None)
        )
        
        # Create invite with token
        token = str(uuid.uuid4())
        invite_id = str(uuid.uuid4())
        cursor.execute(
            '''INSERT INTO rfq_invites (id, rfq_id, supplier_id, token, revoked, created_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (invite_id, rfq_id, supplier_id, token, 0, now_unix())
        )
        
        conn.commit()
        
        yield {
            'supplier_id': supplier_id,
            'rfq_id': rfq_id,
            'token': token,
            'buyer_id': buyer_id
        }

# ============ Tests ============

def test_post_quote_creates_v1(setup_test_data):
    """Test: POST first quote creates version=1."""
    data = setup_test_data
    
    response = client.post(
        f'/api/rfq-by-token/{data["token"]}/quotes',
        json={
            'price': 50.0,
            'lead_days': 5,
            'packing_json': '{"pack_size": 10}',
            'notes': 'First quote'
        }
    )
    
    assert response.status_code == 200
    body = response.json()
    
    assert body['version'] == 1
    assert body['price'] == 50.0
    assert body['lead_days'] == 5
    assert body['rfq_id'] == data['rfq_id']
    assert body['supplier_id'] == data['supplier_id']

def test_post_second_quote_creates_v2(setup_test_data):
    """Test: POST second quote for same token/rfq/supplier creates version=2."""
    data = setup_test_data
    
    # Post first quote
    response1 = client.post(
        f'/api/rfq-by-token/{data["token"]}/quotes',
        json={
            'price': 50.0,
            'lead_days': 5,
            'packing_json': None,
            'notes': None
        }
    )
    assert response1.status_code == 200
    assert response1.json()['version'] == 1
    
    # Post second quote
    response2 = client.post(
        f'/api/rfq-by-token/{data["token"]}/quotes',
        json={
            'price': 45.0,
            'lead_days': 4,
            'packing_json': None,
            'notes': 'Revised offer'
        }
    )
    assert response2.status_code == 200
    assert response2.json()['version'] == 2
    assert response2.json()['price'] == 45.0

def test_reject_quote_after_decision(setup_test_data):
    """Test: POST quote after RFQ decided returns 400."""
    data = setup_test_data
    
    # Set decided_quote_id in RFQ
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE rfqs SET decided_quote_id=? WHERE id=?',
            ('some-quote-id', data['rfq_id'])
        )
        conn.commit()
    
    # Try to post quote
    response = client.post(
        f'/api/rfq-by-token/{data["token"]}/quotes',
        json={
            'price': 50.0,
            'lead_days': 5,
            'packing_json': None,
            'notes': None
        }
    )
    
    assert response.status_code == 400
    assert 'already been decided' in response.json()['detail']

def test_get_quotes_mine_returns_all_versions(setup_test_data):
    """Test: GET /mine returns all versions ordered v2 first."""
    data = setup_test_data
    
    # Post v1 and v2
    client.post(
        f'/api/rfq-by-token/{data["token"]}/quotes',
        json={'price': 50.0, 'lead_days': 5, 'packing_json': None, 'notes': 'v1'}
    )
    client.post(
        f'/api/rfq-by-token/{data["token"]}/quotes',
        json={'price': 45.0, 'lead_days': 4, 'packing_json': None, 'notes': 'v2'}
    )
    
    # Get mine
    response = client.get(f'/api/rfq-by-token/{data["token"]}/quotes/mine')
    
    assert response.status_code == 200
    quotes = response.json()
    
    assert len(quotes) == 2
    assert quotes[0]['version'] == 2  # Newest first
    assert quotes[0]['notes'] == 'v2'
    assert quotes[1]['version'] == 1
    assert quotes[1]['notes'] == 'v1'

def test_invalid_token_quote_returns_404(setup_test_data):
    """Test: GET with fake token returns 404."""
    response = client.get('/api/rfq-by-token/fake-token-xyz/quotes/mine')
    assert response.status_code == 404

def test_invalid_token_post_quote_returns_404(setup_test_data):
    """Test: POST with fake token returns 404."""
    response = client.post(
        '/api/rfq-by-token/fake-token-xyz/quotes',
        json={'price': 50.0, 'lead_days': 5, 'packing_json': None, 'notes': None}
    )
    assert response.status_code == 404

# ============ Cleanup ============

@pytest.fixture(scope='session', autouse=True)
def cleanup():
    """Cleanup test database."""
    yield
    if Path(TEST_DB_DIR).exists():
        shutil.rmtree(TEST_DB_DIR)
