from flask import Flask, session
from flask_session import Session
import datetime
from config import Config
from models import db
from redis_client import session_redis

def create_app():
    """Application factory function"""
    app = Flask(__name__)
    
    # Configure app
    app.secret_key = Config.SECRET_KEY
    
    # Session configuration
    app.config['SESSION_TYPE'] = Config.SESSION_TYPE
    app.config['SESSION_REDIS'] = session_redis
    app.config['SESSION_USE_SIGNER'] = Config.SESSION_USE_SIGNER
    app.config['SESSION_PERMANENT'] = Config.SESSION_PERMANENT
    
    # Database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = Config.SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = Config.SQLALCHEMY_TRACK_MODIFICATIONS
    
    # Initialize extensions
    db.init_app(app)
    Session(app)
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    # Register blueprints
    from routes.auth_routes import auth_bp
    from routes.chat_routes import chat_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp, name='main')  # Register chat_bp as 'main' for URL compatibility
    
    # Session configuration
    @app.before_request
    def make_session_permanent():
        session.permanent = True
        app.permanent_session_lifetime = Config.PERMANENT_SESSION_LIFETIME
    
    return app