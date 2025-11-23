import json
import time
import urllib.request
from functools import wraps
from flask import request, jsonify, g, current_app
from jose import jwk, jwt
from jose.utils import base64url_decode
from app.models import User, Salon, Staff

def get_token_auth_header():
    """Obtains the Access Token from the Authorization Header"""
    auth = request.headers.get("Authorization", None)
    if not auth:
        return None
    
    parts = auth.split()

    if parts[0].lower() != "bearer":
        return None
    elif len(parts) == 1:
        return None
    elif len(parts) > 2:
        return None

    return parts[1]

_COGNITO_KEYS = None

def verify_cognito_token(token):
    """
    Verifies the Cognito JWT token.
    Returns the claims if valid, raises Exception if invalid.
    """
    global _COGNITO_KEYS
    
    # Get Cognito details from config
    region = current_app.config.get('COGNITO_REGION')
    user_pool_id = current_app.config.get('COGNITO_USER_POOL_ID')
    app_client_id = current_app.config.get('COGNITO_APP_CLIENT_ID')

    if not region or not user_pool_id:
        if current_app.config.get('ENV') == 'development' and not region:
            return {"sub": "dev-user", "email": "dev@example.com"}
        raise Exception("Cognito configuration missing")

    # Fetch keys only if not cached
    if not _COGNITO_KEYS:
        keys_url = f'https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json'
        try:
            with urllib.request.urlopen(keys_url) as response:
                _COGNITO_KEYS = json.loads(response.read())['keys']
        except Exception as e:
            raise Exception(f"Could not fetch JWKS: {str(e)}")
    
    keys = _COGNITO_KEYS

    # Get the kid from the headers
    headers = jwt.get_unverified_headers(token)
    kid = headers['kid']

    # Search for the kid in the downloaded public keys
    key_index = -1
    for i in range(len(keys)):
        if kid == keys[i]['kid']:
            key_index = i
            break
    
    if key_index == -1:
        raise Exception('Public key not found in JWKS')

    # Construct the public key
    public_key = jwk.construct(keys[key_index])

    # Get the message part (ensure signature verification)
    message, encoded_signature = str(token).rsplit('.', 1)
    
    # Decode the signature
    decoded_signature = base64url_decode(encoded_signature.encode('utf-8'))

    # Verify the signature
    if not public_key.verify(message.encode("utf8"), decoded_signature):
        raise Exception('Signature verification failed')

    # Verify the token expiration and claims
    claims = jwt.get_unverified_claims(token)
    
    # Verify expiration
    if time.time() > claims['exp']:
        raise Exception('Token is expired')
    
    # Verify audience (app client id) - optional but recommended
    if app_client_id and claims['aud'] != app_client_id:
         raise Exception('Token was not issued for this audience')
         
    return claims

def login_required(f):
    """Decorator to require valid Cognito token for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_token_auth_header()
        
        if not token:
            return jsonify({'error': 'Authorization token required'}), 401
        
        try:
            # Verify token
            claims = verify_cognito_token(token)
            
            # Store claims in global context
            g.cognito_claims = claims
            g.cognito_sub = claims.get('sub')
            
            # Find or create user in our DB based on sub
            # (In a real app, we might want to do this only on specific endpoints, 
            # but for this MVP, doing it here ensures we always have a user context)
            user = User.query.filter_by(cognito_sub=g.cognito_sub).first()
            
            if not user:
                # If user doesn't exist in our DB but has valid token, 
                # they might be a new user who hasn't hit the /register endpoint yet
                # OR we can auto-create them here? 
                # For now, let's fail and tell them to register if we can't find them,
                # UNLESS it's the registration endpoint itself (handled in routes)
                pass 
            
            if user:
                g.current_user = user
                
                # Load Salon based on Role
                if user.role == 'STAFF':
                    staff_record = Staff.query.filter_by(user_id=user.id).first()
                    # Access the salon relationship from Staff model if it exists
                    salon = staff_record.salon if staff_record else None
                else:
                    salon = Salon.query.filter_by(owner_id=user.id).first()
                    
                g.current_salon = salon
            else:
                g.current_user = None
                g.current_salon = None

        except Exception as e:
            return jsonify({'error': f'Invalid token: {str(e)}'}), 401
            
        return f(*args, **kwargs)
    return decorated_function
