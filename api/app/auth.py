"""JWT authentication with Supabase verification."""

import os
import jwt
from fastapi import Depends, HTTPException, status, Request

# Supabase JWT Secret (configure via environment)
JWT_SECRET = os.getenv('SUPABASE_JWT_SECRET', 'gsGZqpU1WYw4EM7pfqVY+/QTFKms4RjN2uVZodeSUQt4+mh9wswMoEOMVBiwVW6IEfVVh8C3FHFpl146ghY/Sg==')
JWT_ALGORITHM = 'HS256'

def get_current_user(request: Request) -> dict:
    """
    Verify JWT token from Authorization header.
    Returns decoded token with user_id, email, etc.
    """
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Missing or invalid Authorization header',
            headers={'WWW-Authenticate': 'Bearer'}
        )
    
    token = auth_header.split('Bearer ')[1]
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_aud": False})
        user_id = payload.get('sub')
        email = payload.get('email')
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Invalid token: missing sub claim',
                headers={'WWW-Authenticate': 'Bearer'}
            )
        
        return {
            'user_id': user_id,
            'email': email,
            'token_data': payload
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Token expired',
            headers={'WWW-Authenticate': 'Bearer'}
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f'Invalid token: {str(e)}',
            headers={'WWW-Authenticate': 'Bearer'}
        )
