"""End-to-end tests using seeded data."""

import pytest
import sys
import os
import json
import uuid
from pathlib import Path

# Add api directory to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.main import app
from app.db import get_db, now_unix

from fastapi.testclient import TestClient

client = TestClient(app)


def generate_synthetic_data():
    """Generate and return all synthetic records."""
    now = now_unix()
    
    # Supplier profiles
    suppliers = {
        'supplier-001': {
            'id': 'supplier-001',
            'email': 'supplier1@vendor.com',
            'company': 'Steel Supply Co',
            'state': '27',
            'business_type': 'manufacturer',
            'categories': ['fasteners', 'metals'],
            'regions': ['27', '29'],
            'default_lead_days': 3,
            'gst_inclusive_default': 1,
            'created_at': now - 86400 * 30,
        },
        'supplier-002': {
            'id': 'supplier-002',
            'email': 'supplier2@vendor.com',
            'company': 'Packaging Solutions Ltd',
            'state': '29',
            'business_type': 'trader',
            'categories': ['packaging', 'chemicals'],
            'regions': ['29', '33'],
            'default_lead_days': 5,
            'gst_inclusive_default': 0,
            'created_at': now - 86400 * 25,
        },
        'supplier-003': {
            'id': 'supplier-003',
            'email': 'supplier3@vendor.com',
            'company': 'Industrial Chemicals Inc',
            'state': '27',
            'business_type': 'distributor',
            'categories': ['chemicals', 'metals'],
            'regions': ['27', '33', '36'],
            'default_lead_days': 7,
            'gst_inclusive_default': 1,
            'created_at': now - 86400 * 20,
        },
    }
    
    # RFQs
    rfqs = {
        'rfq-001': {
            'id': 'rfq-001',
            'buyer_id': 'buyer-001',
            'item': 'Fasteners assortment',
            'quantity_needed': 1000,
            'need_by_days': 14,
            'created_at': now - 86400 * 7,
            'decided_quote_id': None,
        },
        'rfq-002': {
            'id': 'rfq-002',
            'buyer_id': 'buyer-002',
            'item': 'Packaging materials',
            'quantity_needed': 5000,
            'need_by_days': 21,
            'created_at': now - 86400 * 5,
            'decided_quote_id': None,
        },
    }
    
    # RFQ Invites (one per supplier per RFQ)
    invites = []
    for rfq_id in rfqs:
        for supplier_id in suppliers:
            invites.append({
                'id': str(uuid.uuid4()),
                'rfq_id': rfq_id,
                'supplier_id': supplier_id,
                'token': str(uuid.uuid4()),
                'revoked': 0,
                'created_at': rfqs[rfq_id]['created_at'] + 3600,
            })
    
    # Quotes (6+ total: rfq1 gets 6 quotes (2 per supplier v1+v2), rfq2 gets 3 quotes (1 per supplier v1))
    quotes = []
    # RFQ-001: 2 versions per supplier
    for supplier_id in ['supplier-001', 'supplier-002', 'supplier-003']:
        for version in [1, 2]:
            quotes.append({
                'id': str(uuid.uuid4()),
                'rfq_id': 'rfq-001',
                'supplier_id': supplier_id,
                'version': version,
                'price': 100.0 + (version * 10) if supplier_id == 'supplier-001' else 110.0 + (version * 15),
                'lead_days': 3 + version,
                'packing_json': None,
                'notes': '[labelled synthetic] demo quote',
                'submitted_at': rfqs['rfq-001']['created_at'] + 7200 + (version * 1800),
                'rejected': 0,
            })
    # RFQ-002: 1 version per supplier
    for supplier_id in ['supplier-001', 'supplier-002', 'supplier-003']:
        quotes.append({
            'id': str(uuid.uuid4()),
            'rfq_id': 'rfq-002',
            'supplier_id': supplier_id,
            'version': 1,
            'price': 200.0,
            'lead_days': 5,
            'packing_json': None,
            'notes': '[labelled synthetic] demo quote',
            'submitted_at': rfqs['rfq-002']['created_at'] + 3600,
            'rejected': 0,
        })
    
    # Products (9 total: 3 per supplier)
    products = []
    supplier_products = {
        'supplier-001': [
            {
                'name': 'Bolt Pack A',
                'category': 'fasteners',
                'photo_path': 'api/data/products/001.jpg',
            },
            {
                'name': 'Steel Rod 6mm',
                'category': 'metals',
                'photo_path': 'api/data/products/002.jpg',
            },
            {
                'name': 'Hex Nut M8',
                'category': 'fasteners',
                'photo_path': 'api/data/products/003.jpg',
            },
        ],
        'supplier-002': [
            {
                'name': 'Bubble Wrap Roll',
                'category': 'packaging',
                'photo_path': 'api/data/products/004.jpg',
            },
            {
                'name': 'Corrugated Box',
                'category': 'packaging',
                'photo_path': 'api/data/products/005.jpg',
            },
            {
                'name': 'Foam Sheets',
                'category': 'packaging',
                'photo_path': 'api/data/products/006.jpg',
            },
        ],
        'supplier-003': [
            {
                'name': 'Sodium Chloride 25kg',
                'category': 'chemicals',
                'photo_path': 'api/data/products/007.jpg',
            },
            {
                'name': 'Aluminum Ingot',
                'category': 'metals',
                'photo_path': 'api/data/products/008.jpg',
            },
            {
                'name': 'Industrial Thinner',
                'category': 'chemicals',
                'photo_path': 'api/data/products/009.jpg',
            },
        ],
    }
    
    for supplier_id, prod_list in supplier_products.items():
        for prod in prod_list:
            products.append({
                'id': str(uuid.uuid4()),
                'supplier_id': supplier_id,
                'name': prod['name'],
                'category': prod['category'],
                'photo_path': prod['photo_path'],
                'created_at': suppliers[supplier_id]['created_at'] + 86400,
            })
    
    # Messages (20+ total: 5+5 for rfq1-supplier1, 3+3 for rfq1-supplier2, 2+2 for rfq1-supplier3, 1+1 for rfq2-supplier1)
    messages = []
    
    # RFQ-001, Supplier-001: 10 messages (5 buyer + 5 supplier)
    for i in range(5):
        messages.append({
            'id': str(uuid.uuid4()),
            'rfq_id': 'rfq-001',
            'supplier_id': 'supplier-001',
            'sender_type': 'buyer',
            'content': f'[labelled synthetic] buyer message {i+1}',
            'created_at': rfqs['rfq-001']['created_at'] + 86400 + (i * 3600),
        })
        messages.append({
            'id': str(uuid.uuid4()),
            'rfq_id': 'rfq-001',
            'supplier_id': 'supplier-001',
            'sender_type': 'supplier',
            'content': f'[labelled synthetic] supplier response {i+1}',
            'created_at': rfqs['rfq-001']['created_at'] + 86400 + (i * 3600) + 1800,
        })
    
    # RFQ-001, Supplier-002: 6 messages (3 buyer + 3 supplier)
    for i in range(3):
        messages.append({
            'id': str(uuid.uuid4()),
            'rfq_id': 'rfq-001',
            'supplier_id': 'supplier-002',
            'sender_type': 'buyer',
            'content': f'[labelled synthetic] buyer query {i+1}',
            'created_at': rfqs['rfq-001']['created_at'] + 172800 + (i * 3600),
        })
        messages.append({
            'id': str(uuid.uuid4()),
            'rfq_id': 'rfq-001',
            'supplier_id': 'supplier-002',
            'sender_type': 'supplier',
            'content': f'[labelled synthetic] supplier answer {i+1}',
            'created_at': rfqs['rfq-001']['created_at'] + 172800 + (i * 3600) + 1800,
        })
    
    # RFQ-001, Supplier-003: 4 messages (2 buyer + 2 supplier)
    for i in range(2):
        messages.append({
            'id': str(uuid.uuid4()),
            'rfq_id': 'rfq-001',
            'supplier_id': 'supplier-003',
            'sender_type': 'buyer',
            'content': f'[labelled synthetic] buyer note {i+1}',
            'created_at': rfqs['rfq-001']['created_at'] + 259200 + (i * 3600),
        })
        messages.append({
            'id': str(uuid.uuid4()),
            'rfq_id': 'rfq-001',
            'supplier_id': 'supplier-003',
            'sender_type': 'supplier',
            'content': f'[labelled synthetic] supplier feedback {i+1}',
            'created_at': rfqs['rfq-001']['created_at'] + 259200 + (i * 3600) + 1800,
        })
    
    # RFQ-002, Supplier-001: 2 messages (1 buyer + 1 supplier)
    messages.append({
        'id': str(uuid.uuid4()),
        'rfq_id': 'rfq-002',
        'supplier_id': 'supplier-001',
        'sender_type': 'buyer',
        'content': '[labelled synthetic] buyer initial message',
        'created_at': rfqs['rfq-002']['created_at'] + 86400,
    })
    messages.append({
        'id': str(uuid.uuid4()),
        'rfq_id': 'rfq-002',
        'supplier_id': 'supplier-001',
        'sender_type': 'supplier',
        'content': '[labelled synthetic] supplier acknowledgement',
        'created_at': rfqs['rfq-002']['created_at'] + 86400 + 1800,
    })
    
    # Targets (4+ total: 2 per RFQ)
    targets = []
    targets.append({
        'id': str(uuid.uuid4()),
        'rfq_id': 'rfq-001',
        'target_type': 'min_price',
        'target_value': 95.0,
        'created_at': rfqs['rfq-001']['created_at'] + 7200,
    })
    targets.append({
        'id': str(uuid.uuid4()),
        'rfq_id': 'rfq-001',
        'target_type': 'max_lead_days',
        'target_value': 5,
        'created_at': rfqs['rfq-001']['created_at'] + 7200,
    })
    targets.append({
        'id': str(uuid.uuid4()),
        'rfq_id': 'rfq-002',
        'target_type': 'min_price',
        'target_value': 190.0,
        'created_at': rfqs['rfq-002']['created_at'] + 3600,
    })
    targets.append({
        'id': str(uuid.uuid4()),
        'rfq_id': 'rfq-002',
        'target_type': 'max_lead_days',
        'target_value': 7,
        'created_at': rfqs['rfq-002']['created_at'] + 3600,
    })
    
    return {
        'suppliers': suppliers,
        'rfqs': rfqs,
        'invites': invites,
        'quotes': quotes,
        'products': products,
        'messages': messages,
        'targets': targets,
    }


@pytest.fixture(scope='function', autouse=True)
def seeded_db():
    """Populate database with synthetic data for each test."""
    # Clean up any existing test data first
    with get_db() as conn:
        cursor = conn.cursor()
        # Delete test data only (RFQ created by tests will have buyer-001 or buyer-002)
        cursor.execute('DELETE FROM rfqs WHERE buyer_id IN (?, ?)', ('buyer-001', 'buyer-002'))
        conn.commit()
    
    data = generate_synthetic_data()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Insert suppliers
        for supplier_id, supplier in data['suppliers'].items():
            cursor.execute(
                '''INSERT OR REPLACE INTO supplier_profiles 
                   (id, email, company, state, business_type, categories, regions, 
                    default_lead_days, gst_inclusive_default, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (supplier['id'], supplier['email'], supplier['company'], supplier['state'],
                 supplier['business_type'], json.dumps(supplier['categories']),
                 json.dumps(supplier['regions']), supplier['default_lead_days'],
                 supplier['gst_inclusive_default'], supplier['created_at'])
            )
        
        # Insert RFQs
        for rfq_id, rfq in data['rfqs'].items():
            cursor.execute(
                '''INSERT OR REPLACE INTO rfqs 
                   (id, buyer_id, item, quantity_needed, need_by_days, created_at, decided_quote_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (rfq['id'], rfq['buyer_id'], rfq['item'], rfq['quantity_needed'],
                 rfq['need_by_days'], rfq['created_at'], rfq['decided_quote_id'])
            )
        
        # Insert RFQ invites
        for invite in data['invites']:
            cursor.execute(
                '''INSERT OR REPLACE INTO rfq_invites 
                   (id, rfq_id, supplier_id, token, revoked, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (invite['id'], invite['rfq_id'], invite['supplier_id'], invite['token'],
                 invite['revoked'], invite['created_at'])
            )
        
        # Insert quotes
        for quote in data['quotes']:
            cursor.execute(
                '''INSERT OR REPLACE INTO quotes 
                   (id, rfq_id, supplier_id, version, price, lead_days, packing_json, notes, submitted_at, rejected)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (quote['id'], quote['rfq_id'], quote['supplier_id'], quote['version'],
                 quote['price'], quote['lead_days'], quote['packing_json'], quote['notes'],
                 quote['submitted_at'], quote['rejected'])
            )
        
        # Insert products
        for product in data['products']:
            cursor.execute(
                '''INSERT OR REPLACE INTO products 
                   (id, supplier_id, name, category, photo_path, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (product['id'], product['supplier_id'], product['name'], product['category'],
                 product['photo_path'], product['created_at'])
            )
        
        # Insert messages
        for message in data['messages']:
            cursor.execute(
                '''INSERT OR REPLACE INTO messages 
                   (id, rfq_id, supplier_id, sender_type, content, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (message['id'], message['rfq_id'], message['supplier_id'], message['sender_type'],
                 message['content'], message['created_at'])
            )
        
        # Insert targets
        for target in data['targets']:
            cursor.execute(
                '''INSERT OR REPLACE INTO targets 
                   (id, rfq_id, target_type, target_value, created_at)
                   VALUES (?, ?, ?, ?, ?)''',
                (target['id'], target['rfq_id'], target['target_type'], target['target_value'],
                 target['created_at'])
            )
        
        conn.commit()
    
    yield


# ============ Tests ============

def test_seed_has_rfqs(seeded_db):
    """Test that seeded data includes RFQs."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as cnt FROM rfqs')
        rfq_count = cursor.fetchone()['cnt']
        assert rfq_count >= 2, f'Expected at least 2 RFQs, got {rfq_count}'


def test_seed_has_suppliers(seeded_db):
    """Test that seeded data includes suppliers."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as cnt FROM supplier_profiles')
        supplier_count = cursor.fetchone()['cnt']
        assert supplier_count >= 3, f'Expected at least 3 suppliers, got {supplier_count}'


def test_seed_has_messages(seeded_db):
    """Test that seeded data includes messages."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as cnt FROM messages')
        message_count = cursor.fetchone()['cnt']
        assert message_count >= 20, f'Expected at least 20 messages, got {message_count}'


def test_supplier_quote_versioning_via_seed(seeded_db):
    """Test quote versioning using seeded data and token endpoint."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get a token for supplier-001 on rfq-001
        cursor.execute(
            'SELECT token FROM rfq_invites WHERE rfq_id=? AND supplier_id=?',
            ('rfq-001', 'supplier-001')
        )
        token_row = cursor.fetchone()
        assert token_row is not None, 'No token found for supplier-001 on rfq-001'
        token = token_row['token']
    
    # Use token endpoint to get quotes
    response = client.get(f'/api/rfq-by-token/{token}/quotes/mine')
    assert response.status_code == 200
    quotes = response.json()
    
    # Should have at least 2 quotes (v1, v2) from seeded data
    assert len(quotes) >= 2, f'Expected at least 2 quotes, got {len(quotes)}'
    
    # Verify versions (should be in DESC order, at least v1 and v2 present)
    versions = [q['version'] for q in quotes]
    assert 1 in versions and 2 in versions, f'Expected versions 1 and 2, got {versions}'
    # Newest should be first
    assert quotes[0]['version'] == max(versions)


def test_full_workflow_e2e(seeded_db):
    """Test complete workflow: RFQ, quote versions, messages."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get supplier token for rfq-001
        cursor.execute(
            'SELECT token FROM rfq_invites WHERE rfq_id=? AND supplier_id=?',
            ('rfq-001', 'supplier-001')
        )
        supplier_token = cursor.fetchone()['token']
    
    # Step 1: Supplier posts a quote
    quote_payload = {
        'price': 105.0,
        'lead_days': 4,
        'notes': 'Updated quote via e2e test',
    }
    response = client.post(f'/api/rfq-by-token/{supplier_token}/quotes', json=quote_payload)
    assert response.status_code == 200
    new_quote = response.json()
    # Version should be higher than existing v1 and v2
    assert new_quote['version'] >= 3, f'Expected v3 or higher, got v{new_quote["version"]}'
    
    # Step 2: Get supplier's quotes
    response = client.get(f'/api/rfq-by-token/{supplier_token}/quotes/mine')
    assert response.status_code == 200
    quotes = response.json()
    assert len(quotes) >= 3
    assert quotes[0]['version'] == new_quote['version'], 'Newest quote should be first'
    
    # Step 3: Supplier sends a message
    message_payload = {
        'rfq_id': 'rfq-001',
        'content': '[labelled synthetic test] Supplier message via e2e',
        'sender_type': 'supplier',
        'token': supplier_token,
    }
    response = client.post('/api/messages', json=message_payload)
    assert response.status_code == 200
    message = response.json()
    assert message['content'] == '[labelled synthetic test] Supplier message via e2e'


def test_supplier_quote_submission(seeded_db):
    """Test that supplier can submit quotes via token."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT token FROM rfq_invites WHERE rfq_id=? AND supplier_id=?',
            ('rfq-002', 'supplier-002')
        )
        token = cursor.fetchone()['token']
    
    # Submit a quote
    quote_payload = {
        'price': 250.0,
        'lead_days': 6,
        'notes': 'Test quote',
    }
    response = client.post(f'/api/rfq-by-token/{token}/quotes', json=quote_payload)
    assert response.status_code == 200
    quote = response.json()
    # Should be v2 (v1 exists from seed)
    assert quote['version'] >= 2, f'Expected version >= 2, got {quote["version"]}'
    assert quote['price'] == 250.0


def test_seeded_supplier_profiles_exist(seeded_db):
    """Test that seeded supplier profiles exist with correct data."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Fetch supplier-001
        cursor.execute('SELECT * FROM supplier_profiles WHERE id=?', ('supplier-001',))
        supplier = cursor.fetchone()
        
        assert supplier is not None
        assert supplier['email'] == 'supplier1@vendor.com'
        assert supplier['company'] == 'Steel Supply Co'


def test_seeded_products_exist(seeded_db):
    """Test that seeded products exist with photo paths."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check that products exist for supplier-001
        cursor.execute('SELECT * FROM products WHERE supplier_id=?', ('supplier-001',))
        products = cursor.fetchall()
        
        assert len(products) >= 3


def test_seeded_rfqs_have_correct_structure(seeded_db):
    """Test that seeded RFQs have expected structure."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Fetch rfq-001
        cursor.execute('SELECT * FROM rfqs WHERE id=?', ('rfq-001',))
        rfq = cursor.fetchone()
        
        assert rfq is not None
        assert rfq['buyer_id'] == 'buyer-001'
        assert rfq['item'] == 'Fasteners assortment'
        assert rfq['quantity_needed'] == 1000
