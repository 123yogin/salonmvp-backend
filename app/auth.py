from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask import session, jsonify

def hash_password(password):
    """Hash a password for storing."""
    return generate_password_hash(password)

def verify_password(password_hash, password):
    """Verify a stored password against one provided by user."""
    return check_password_hash(password_hash, password)

def login_required(f):
    """Decorator to require login for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function
