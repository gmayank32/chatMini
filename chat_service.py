import json
import uuid
from redis_client import session_redis
from config import Config

class ChatService:
    """Service class for chat-related operations"""
    
    @staticmethod
    def get_chat_key(chat_id, model=None):
        """Generate Redis key for chat data"""
        if model:
            return f"chat:data:{chat_id}:{model}"
        return f"chat:data:{chat_id}"
    
    @staticmethod
    def get_chat_title(chat_id):
        """Get chat title from Redis"""
        title = session_redis.get(f"chat:title:{chat_id}")
        return title.decode() if title else "Untitled Chat"
    
    @staticmethod
    def get_chat_model(chat_id):
        """Get chat model from Redis"""
        model = session_redis.get(f"chat:model:{chat_id}")
        return model.decode() if model else Config.AVAILABLE_MODELS[0]
    
    @staticmethod
    def save_chat(chat_id, model, chat_history):
        """Save chat history to Redis"""
        key = ChatService.get_chat_key(chat_id, model)
        session_redis.set(key, json.dumps(chat_history))
    
    @staticmethod
    def get_chat_history(chat_id, model=None):
        """Get chat history from Redis"""
        if model:
            key = ChatService.get_chat_key(chat_id, model)
            history_raw = session_redis.get(key)
        else:
            history_raw = session_redis.get(ChatService.get_chat_key(chat_id))
        
        return json.loads(history_raw) if history_raw else []
    
    @staticmethod
    def get_chat_list(user_id):
        """Get list of chats for a user"""
        chat_ids = session_redis.smembers(f"user:{user_id}:chats")
        chats = []
        
        for cid in chat_ids:
            cid_str = cid.decode()
            chats.append({
                "id": cid_str,
                "title": ChatService.get_chat_title(cid_str),
                "model": ChatService.get_chat_model(cid_str)
            })
        
        return chats
    
    @staticmethod
    def create_new_chat(user_id, model=None):
        """Create a new chat for a user"""
        chat_id = str(uuid.uuid4())
        selected_model = model if model in Config.AVAILABLE_MODELS else Config.AVAILABLE_MODELS[0]
        
        # Associate chat with user
        session_redis.sadd(f"user:{user_id}:chats", chat_id)
        
        # Set initial chat properties
        session_redis.set(f"chat:title:{chat_id}", "New Chat")
        session_redis.set(f"chat:user:{chat_id}", str(user_id))
        session_redis.set(f"chat:model:{chat_id}", selected_model)
        
        # Initialize empty chat history
        ChatService.save_chat(chat_id, selected_model, [])
        
        return chat_id
    
    @staticmethod
    def verify_chat_ownership(chat_id, user_id):
        """Verify that a chat belongs to a specific user"""
        owner_id_bytes = session_redis.get(f"chat:user:{chat_id}")
        return owner_id_bytes and int(owner_id_bytes.decode()) == user_id
    
    @staticmethod
    def update_chat_title(chat_id, new_title):
        """Update chat title"""
        session_redis.set(f"chat:title:{chat_id}", new_title[:100])
    
    @staticmethod
    def update_chat_model(chat_id, model):
        """Update chat model"""
        if model in Config.AVAILABLE_MODELS:
            session_redis.set(f"chat:model:{chat_id}", model)
    
    @staticmethod
    def delete_chat(chat_id, user_id):
        """Delete a chat and all associated data"""
        if not ChatService.verify_chat_ownership(chat_id, user_id):
            return False
        
        model = ChatService.get_chat_model(chat_id)
        
        # Delete all associated keys
        session_redis.delete(ChatService.get_chat_key(chat_id, model))
        session_redis.delete(f"chat:title:{chat_id}")
        session_redis.delete(f"chat:user:{chat_id}")
        session_redis.delete(f"chat:model:{chat_id}")
        session_redis.srem(f"user:{user_id}:chats", chat_id)
        
        return True