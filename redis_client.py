import redis
from config import Config

# Redis client for session management
session_redis = redis.StrictRedis(
    host=Config.REDIS_HOST, 
    port=Config.REDIS_PORT, 
    db=Config.REDIS_DB
)