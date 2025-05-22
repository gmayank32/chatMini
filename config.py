import os
import datetime

class Config:
    """Application configuration settings"""
    
    # Flask settings
    SECRET_KEY = os.urandom(24)
    
    # Redis settings
    REDIS_HOST = 'localhost'
    REDIS_PORT = 6379
    REDIS_DB = 1
    
    # Session settings
    SESSION_TYPE = 'redis'
    SESSION_USE_SIGNER = True
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = datetime.timedelta(days=90)
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = 'sqlite:///users.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT settings
    JWT_ALGO = "HS256"
    JWT_COOKIE_NAME = "token"
    JWT_EXPIRATION_DAYS = 1
    
    # Available AI models
    AVAILABLE_MODELS = ['qwen3:8b', 'qwen3:30b-a3b', 'qwen3:14b', 'mistral', 'gemma', 'nous-hermes2']
    
    # Server settings
    HOST = '0.0.0.0'
    PORT = 8000
    DEBUG = True
    THREADED = True