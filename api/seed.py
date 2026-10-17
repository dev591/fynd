"""Seed script that rebuilds demo database with synthetic data."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.db import init_db, get_db, now_unix, DB_PATH
import uuid
import json
import shutil
from pathlib import Path

# Minimal valid 1x1 JPEG in bytes
MINI_JPEG = bytes([
    0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
    0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
    0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
    0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
    0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
    0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
    0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
    0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
    0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
    0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
    0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
    0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
    0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
    0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
    0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
    0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
    0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
    0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
    0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
    0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
    0x8A, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3, 0xA4,
    0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7,
    0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xCA,
    0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2, 0xE3,
    0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5,
    0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00,
    0x00, 0x3F, 0x00, 0xFB, 0xD2, 0x8A, 0x28, 0x03, 0xFF, 0xD9
])


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


def rebuild_db():
    """Drop and recreate all tables, insert synthetic data."""
    # Delete existing DB if present
    db_path = Path(DB_PATH)
    if db_path.exists():
        db_path.unlink()
    
    # Also delete WAL and SHM files
    wal_path = Path(str(DB_PATH) + '-wal')
    shm_path = Path(str(DB_PATH) + '-shm')
    if wal_path.exists():
        wal_path.unlink()
    if shm_path.exists():
        shm_path.unlink()
    
    # Recreate schema
    init_db()
    
    # Generate synthetic data
    data = generate_synthetic_data()
    
    # Insert into database
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Insert suppliers
        for supplier_id, supplier in data['suppliers'].items():
            cursor.execute(
                '''INSERT INTO supplier_profiles 
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
                '''INSERT INTO rfqs 
                   (id, buyer_id, item, quantity_needed, need_by_days, created_at, decided_quote_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (rfq['id'], rfq['buyer_id'], rfq['item'], rfq['quantity_needed'],
                 rfq['need_by_days'], rfq['created_at'], rfq['decided_quote_id'])
            )
        
        # Insert RFQ invites
        for invite in data['invites']:
            cursor.execute(
                '''INSERT INTO rfq_invites 
                   (id, rfq_id, supplier_id, token, revoked, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (invite['id'], invite['rfq_id'], invite['supplier_id'], invite['token'],
                 invite['revoked'], invite['created_at'])
            )
        
        # Insert quotes
        for quote in data['quotes']:
            cursor.execute(
                '''INSERT INTO quotes 
                   (id, rfq_id, supplier_id, version, price, lead_days, packing_json, notes, submitted_at, rejected)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (quote['id'], quote['rfq_id'], quote['supplier_id'], quote['version'],
                 quote['price'], quote['lead_days'], quote['packing_json'], quote['notes'],
                 quote['submitted_at'], quote['rejected'])
            )
        
        # Insert products
        for product in data['products']:
            cursor.execute(
                '''INSERT INTO products 
                   (id, supplier_id, name, category, photo_path, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (product['id'], product['supplier_id'], product['name'], product['category'],
                 product['photo_path'], product['created_at'])
            )
        
        # Insert messages
        for message in data['messages']:
            cursor.execute(
                '''INSERT INTO messages 
                   (id, rfq_id, supplier_id, sender_type, content, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (message['id'], message['rfq_id'], message['supplier_id'], message['sender_type'],
                 message['content'], message['created_at'])
            )
        
        # Insert targets
        for target in data['targets']:
            cursor.execute(
                '''INSERT INTO targets 
                   (id, rfq_id, target_type, target_value, created_at)
                   VALUES (?, ?, ?, ?, ?)''',
                (target['id'], target['rfq_id'], target['target_type'], target['target_value'],
                 target['created_at'])
            )
        
        conn.commit()
    
    # Create placeholder photos
    photos_dir = Path(__file__).parent / 'data' / 'products'
    photos_dir.mkdir(parents=True, exist_ok=True)
    
    # Create minimal JPEG files for all product photos
    for i in range(1, 10):
        photo_path = photos_dir / f'{str(i).zfill(3)}.jpg'
        if not photo_path.exists():
            with open(photo_path, 'wb') as f:
                f.write(MINI_JPEG)


if __name__ == '__main__':
    rebuild_db()
    print('Seeded successfully')
