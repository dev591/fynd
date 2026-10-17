"""Tests for message endpoints (GET/POST /api/messages)."""

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

# ============ Helpers ============

def create_jwt_token(user_id, email='test@buyer.com'):
    """Create a valid JWT token for testing."""
    payload = {
        'sub': user_id,
        'email': email,
        'aud': 'authenticated'
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

# ============ Fixtures ============

@pytest.fixture(scope='function')
def setup_rfq_with_supplier():
    """Setup RFQ with supplier and token."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Create buyer
        buyer_id = 'buyer-' + str(uuid.uuid4())[:8]
        
        # Create supplier profile
        supplier_id = str(uuid.uuid4())
        supplier_email = f'supplier-{supplier_id[:8]}@test.com'
        cursor.execute(
            '''INSERT INTO supplier_profiles 
               (id, email, company, state, business_type, categories, regions, default_lead_days, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (supplier_id, supplier_email, 'Test Supplier', 'MH', 'manufacturer',
             json.dumps(['electronics']), json.dumps(['north']), 5, now_unix())
        )
        
        # Create RFQ owned by buyer
        rfq_id = str(uuid.uuid4())
        cursor.execute(
            '''INSERT INTO rfqs (id, buyer_id, item, quantity_needed, need_by_days, created_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (rfq_id, buyer_id, 'Widget', 100, 10, now_unix())
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
            'buyer_id': buyer_id,
            'supplier_id': supplier_id,
            'rfq_id': rfq_id,
            'token': token
        }

@pytest.fixture(scope='function')
def setup_rfq_with_messages(setup_rfq_with_supplier):
    """Setup RFQ with existing messages."""
    data = setup_rfq_with_supplier
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Post some messages
        msg1_id = str(uuid.uuid4())
        cursor.execute(
            '''INSERT INTO messages (id, rfq_id, supplier_id, sender_type, content, created_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (msg1_id, data['rfq_id'], data['supplier_id'], 'buyer', 'Hello supplier!', now_unix())
        )
        
        msg2_id = str(uuid.uuid4())
        cursor.execute(
            '''INSERT INTO messages (id, rfq_id, supplier_id, sender_type, content, created_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (msg2_id, data['rfq_id'], data['supplier_id'], 'supplier', 'Hi buyer!', now_unix() + 1)
        )
        
        conn.commit()
        
        data['msg1_id'] = msg1_id
        data['msg2_id'] = msg2_id
        return data

# ============ Tests: GET /api/messages ============

def test_buyer_can_get_messages_for_own_rfq(setup_rfq_with_messages):
    """Test: Buyer can GET messages for own RFQ."""
    data = setup_rfq_with_messages
    token = create_jwt_token(data['buyer_id'])
    
    headers = {'Authorization': f'Bearer {token}'}
    response = client.get(
        f'/api/messages?rfq_id={data["rfq_id"]}',
        headers=headers
    )
    
    assert response.status_code == 200
    messages = response.json()
    
    assert len(messages) == 2
    assert messages[0]['id'] == data['msg1_id']
    assert messages[0]['sender_type'] == 'buyer'
    assert messages[0]['content'] == 'Hello supplier!'
    assert messages[1]['id'] == data['msg2_id']
    assert messages[1]['sender_type'] == 'supplier'

def test_buyer_cannot_get_messages_for_other_buyers_rfq(setup_rfq_with_supplier):
    """Test: Different buyer cannot GET messages for RFQ."""
    data = setup_rfq_with_supplier
    
    # Different buyer
    different_buyer_id = 'buyer-different-' + str(uuid.uuid4())[:8]
    token = create_jwt_token(different_buyer_id)
    
    headers = {'Authorization': f'Bearer {token}'}
    response = client.get(
        f'/api/messages?rfq_id={data["rfq_id"]}',
        headers=headers
    )
    
    assert response.status_code == 403

def test_supplier_can_get_own_messages_by_token(setup_rfq_with_messages):
    """Test: Supplier can GET own messages using token."""
    data = setup_rfq_with_messages
    
    response = client.get(
        f'/api/messages?rfq_id={data["rfq_id"]}&token={data["token"]}'
    )
    
    assert response.status_code == 200
    messages = response.json()
    
    assert len(messages) == 2
    # Messages should be ordered by created_at ASC
    assert messages[0]['sender_type'] == 'buyer'
    assert messages[1]['sender_type'] == 'supplier'

def test_buyer_can_get_messages_for_specific_supplier(setup_rfq_with_messages):
    """Test: Buyer can GET messages with supplier_id param."""
    data = setup_rfq_with_messages
    token = create_jwt_token(data['buyer_id'])
    
    headers = {'Authorization': f'Bearer {token}'}
    response = client.get(
        f'/api/messages?rfq_id={data["rfq_id"]}&supplier_id={data["supplier_id"]}',
        headers=headers
    )
    
    assert response.status_code == 200
    messages = response.json()
    
    assert len(messages) == 2
    # All messages should be for this supplier
    for msg in messages:
        assert msg['supplier_id'] == data['supplier_id']

def test_token_mismatch_rfq_returns_400(setup_rfq_with_supplier):
    """Test: Token with mismatched rfq_id returns 400."""
    data = setup_rfq_with_supplier
    
    # Create different RFQ
    with get_db() as conn:
        cursor = conn.cursor()
        other_rfq_id = str(uuid.uuid4())
        cursor.execute(
            '''INSERT INTO rfqs (id, buyer_id, item, quantity_needed, need_by_days, created_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (other_rfq_id, data['buyer_id'], 'Other Item', 50, 5, now_unix())
        )
        conn.commit()
    
    response = client.get(
        f'/api/messages?rfq_id={other_rfq_id}&token={data["token"]}'
    )
    
    assert response.status_code == 400

# ============ Tests: POST /api/messages ============

def test_post_message_as_buyer(setup_rfq_with_supplier):
    """Test: Buyer can POST message with sender_type=buyer."""
    data = setup_rfq_with_supplier
    token = create_jwt_token(data['buyer_id'])
    
    headers = {'Authorization': f'Bearer {token}'}
    response = client.post(
        '/api/messages',
        json={
            'rfq_id': data['rfq_id'],
            'content': 'What is your quote?',
            'sender_type': 'buyer'
        },
        headers=headers
    )
    
    assert response.status_code == 200
    msg = response.json()
    
    assert msg['rfq_id'] == data['rfq_id']
    assert msg['content'] == 'What is your quote?'
    assert msg['sender_type'] == 'buyer'
    assert msg['id'] is not None

def test_post_message_as_supplier(setup_rfq_with_supplier):
    """Test: Supplier can POST message with sender_type=supplier and token."""
    data = setup_rfq_with_supplier
    
    response = client.post(
        '/api/messages',
        json={
            'rfq_id': data['rfq_id'],
            'content': 'We can provide at $50',
            'sender_type': 'supplier',
            'token': data['token']
        }
    )
    
    assert response.status_code == 200
    msg = response.json()
    
    assert msg['rfq_id'] == data['rfq_id']
    assert msg['content'] == 'We can provide at $50'
    assert msg['sender_type'] == 'supplier'
    assert msg['supplier_id'] == data['supplier_id']

def test_post_buyer_message_rejected_without_jwt(setup_rfq_with_supplier):
    """Test: POST buyer message without JWT returns 401."""
    data = setup_rfq_with_supplier
    
    response = client.post(
        '/api/messages',
        json={
            'rfq_id': data['rfq_id'],
            'content': 'Message without auth',
            'sender_type': 'buyer'
        }
    )
    
    assert response.status_code == 401

def test_post_supplier_message_rejected_without_token(setup_rfq_with_supplier):
    """Test: POST supplier message without token returns 401."""
    data = setup_rfq_with_supplier
    
    response = client.post(
        '/api/messages',
        json={
            'rfq_id': data['rfq_id'],
            'content': 'Message without token',
            'sender_type': 'supplier'
        }
    )
    
    assert response.status_code == 401

def test_post_message_invalid_sender_type(setup_rfq_with_supplier):
    """Test: POST with invalid sender_type returns 400."""
    data = setup_rfq_with_supplier
    token = create_jwt_token(data['buyer_id'])
    
    headers = {'Authorization': f'Bearer {token}'}
    response = client.post(
        '/api/messages',
        json={
            'rfq_id': data['rfq_id'],
            'content': 'Test',
            'sender_type': 'invalid'
        },
        headers=headers
    )
    
    assert response.status_code == 422  # Pydantic validation error

def test_post_buyer_message_wrong_rfq_owner(setup_rfq_with_supplier):
    """Test: Different buyer cannot POST to RFQ."""
    data = setup_rfq_with_supplier
    
    different_buyer_id = 'buyer-different-' + str(uuid.uuid4())[:8]
    token = create_jwt_token(different_buyer_id)
    
    headers = {'Authorization': f'Bearer {token}'}
    response = client.post(
        '/api/messages',
        json={
            'rfq_id': data['rfq_id'],
            'content': 'Unauthorized',
            'sender_type': 'buyer'
        },
        headers=headers
    )
    
    assert response.status_code == 403

def test_post_supplier_message_with_invalid_token(setup_rfq_with_supplier):
    """Test: POST supplier message with invalid token returns 404."""
    data = setup_rfq_with_supplier
    
    response = client.post(
        '/api/messages',
        json={
            'rfq_id': data['rfq_id'],
            'content': 'Test',
            'sender_type': 'supplier',
            'token': 'invalid-token-xyz'
        }
    )
    
    assert response.status_code == 404

def test_post_supplier_message_token_mismatch_rfq(setup_rfq_with_supplier):
    """Test: POST supplier message with token for different RFQ returns 400."""
    data = setup_rfq_with_supplier
    
    # Create different RFQ
    with get_db() as conn:
        cursor = conn.cursor()
        other_rfq_id = str(uuid.uuid4())
        cursor.execute(
            '''INSERT INTO rfqs (id, buyer_id, item, quantity_needed, need_by_days, created_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (other_rfq_id, data['buyer_id'], 'Other Item', 50, 5, now_unix())
        )
        conn.commit()
    
    response = client.post(
        '/api/messages',
        json={
            'rfq_id': other_rfq_id,
            'content': 'Wrong RFQ',
            'sender_type': 'supplier',
            'token': data['token']
        }
    )
    
    assert response.status_code == 400

# ============ Cleanup ============

@pytest.fixture(scope='session', autouse=True)
def cleanup():
    """Cleanup test database."""
    yield
    if Path(TEST_DB_DIR).exists():
        shutil.rmtree(TEST_DB_DIR)
