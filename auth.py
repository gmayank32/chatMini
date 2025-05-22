import jwt
import bcrypt
import datetime
from functools import wraps
from flask import request, redirect, url_for
from models import User
from config import Config

def token_required(f):
    """Decorator to require JWT authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get(Config.JWT_COOKIE_NAME)
        if not token:
            return redirect(url_for('auth.login'))
        
        try:
            data = jwt.decode(token, Config.SECRET_KEY, algorithms=[Config.JWT_ALGO])
            user = User.query.get(data['user_id'])
            if not user:
                return redirect(url_for('auth.login'))
        except:
            return redirect(url_for('auth.login'))
        
        return f(user, *args, **kwargs)
    return decorated

def generate_token(user_id):
    """Generate JWT token for user"""
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=Config.JWT_EXPIRATION_DAYS)
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm=Config.JWT_ALGO)

def hash_password(password):
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def check_password(password, password_hash):
    """Check password against hash"""
    return bcrypt.checkpw(password.encode(), password_hash)