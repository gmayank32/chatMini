from flask import Flask, render_template, request, Response, redirect, session, url_for, jsonify, make_response, flash
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from functools import wraps
import uuid
import json
import redis
import os
import datetime
import bcrypt

# --- Setup App ---
app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- Redis Sessions ---
session_redis = redis.StrictRedis(host='localhost', port=6379, db=1)
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = session_redis
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_PERMANENT'] = True

# --- SQLite DB with SQLAlchemy ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
Session(app)
db = SQLAlchemy(app)

# --- JWT Configuration ---
JWT_SECRET = app.secret_key
JWT_ALGO = "HS256"
JWT_COOKIE_NAME = "token"

# --- Available Models ---
AVAILABLE_MODELS = ['qwen3:8b', 'qwen3:30b-a3b', 'qwen3:14b','deepseek-r1', 'mistral', 'gemma', 'nous-hermes2']

@app.before_request
def make_Session_permanent():
    session.permanent = True
    app.permanent_session_lifetime = datetime.timedelta(days=90)

# --- User Model ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

with app.app_context():
    db.create_all()

# --- JWT Decorator ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get(JWT_COOKIE_NAME)
        if not token:
            return redirect(url_for('login'))
        try:
            data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
            user = User.query.get(data['user_id'])
            if not user:
                return redirect(url_for('login'))
        except:
            return redirect(url_for('login'))
        return f(user, *args, **kwargs)
    return decorated

# --- Auth Routes ---
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            return "User already exists", 400
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        new_user = User(username=username, password_hash=password_hash)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if not user or not bcrypt.checkpw(password.encode(), user.password_hash):
            return "Invalid credentials", 401
        token = jwt.encode({'user_id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)}, JWT_SECRET, algorithm=JWT_ALGO)
        resp = make_response(redirect(url_for('home')))
        resp.set_cookie(JWT_COOKIE_NAME, token, httponly=True, samesite='Lax')
        return resp
    return render_template('login.html')

@app.route('/logout')
def logout():
    resp = make_response(redirect(url_for('login')))
    resp.delete_cookie(JWT_COOKIE_NAME)
    return resp

# --- Chat Helper Functions ---
def get_chat_key(chat_id, model=None):
    """Generate Redis key for chat data"""
    if model:
        return f"chat:data:{chat_id}:{model}"
    return f"chat:data:{chat_id}"

def get_chat_title(chat_id):
    """Get chat title from Redis"""
    title = session_redis.get(f"chat:title:{chat_id}")
    return title.decode() if title else "Untitled Chat"

def get_chat_model(chat_id):
    """Get chat model from Redis"""
    model = session_redis.get(f"chat:model:{chat_id}")
    return model.decode() if model else AVAILABLE_MODELS[0]  # Default to first model if not set

def save_chat(chat_id, model, chat_history):
    """Save chat history to Redis"""
    key = get_chat_key(chat_id, model)
    session_redis.set(key, json.dumps(chat_history))

def get_chat_history(chat_id, model=None):
    """Get chat history from Redis"""
    if model:
        key = get_chat_key(chat_id, model)
        history_raw = session_redis.get(key)
    else:
        # Try to get the default history
        history_raw = session_redis.get(get_chat_key(chat_id))
    return json.loads(history_raw) if history_raw else []

def get_chat_list(user_id):
    """Get list of chats for a user"""
    chat_ids = session_redis.smembers(f"user:{user_id}:chats")
    chats = []
    for cid in chat_ids:
        cid_str = cid.decode()
        chats.append({
            "id": cid_str,
            "title": get_chat_title(cid_str),
            "model": get_chat_model(cid_str)  # Add model info to chat list
        })
    return chats

# --- Chat Routes ---
@app.route('/')
@token_required
def home(current_user):
    # Always pass models to home page
    chat_list = get_chat_list(current_user.id)
    return render_template('index.html', models=AVAILABLE_MODELS, chat_list=chat_list)

@app.route('/new')
@token_required
def new_chat(current_user):
    # Generate a new UUID for the chat
    chat_id = str(uuid.uuid4())
    
    # Get default model (first model)
    default_model = AVAILABLE_MODELS[0]
    
    # Associate this chat with the current user
    session_redis.sadd(f"user:{current_user.id}:chats", chat_id)
    
    # Set the initial title, model and user association
    session_redis.set(f"chat:title:{chat_id}", "New Chat")
    session_redis.set(f"chat:user:{chat_id}", str(current_user.id))
    session_redis.set(f"chat:model:{chat_id}", default_model)
    
    # Initialize an empty chat history for the default model
    save_chat(chat_id, default_model, [])
    
    return redirect(url_for('chat', chat_id=chat_id))

@app.route('/new_chat', methods=['POST'])
@token_required
def create_new_chat(current_user):
    # Generate a new UUID for the chat
    chat_id = str(uuid.uuid4())
    
    # Get selected model from form or use default
    model = request.form.get('model', AVAILABLE_MODELS[0])
    
    # Validate model selection
    if model not in AVAILABLE_MODELS:
        model = AVAILABLE_MODELS[0]
    
    # Associate this chat with the current user
    session_redis.sadd(f"user:{current_user.id}:chats", chat_id)
    
    # Set the initial title, model and user association
    session_redis.set(f"chat:title:{chat_id}", "New Chat")
    session_redis.set(f"chat:user:{chat_id}", str(current_user.id))
    session_redis.set(f"chat:model:{chat_id}", model)
    
    # Initialize an empty chat history for the selected model
    save_chat(chat_id, model, [])
    
    return redirect(url_for('chat', chat_id=chat_id, model=model))

@app.route('/chat/<chat_id>')
@token_required
def chat(current_user, chat_id):
    # Verify the chat belongs to the current user
    owner_id_bytes = session_redis.get(f"chat:user:{chat_id}")
    if not owner_id_bytes or int(owner_id_bytes.decode()) != current_user.id:
        return "Unauthorized", 403

    # Get the selected model for this chat
    selected_model = get_chat_model(chat_id)
    
    # Get chat history for this chat and model
    chat_history = get_chat_history(chat_id, selected_model)
    
    # Get the list of all chats for this user
    chat_list = get_chat_list(current_user.id)
    
    return render_template(
        'index.html',
        chat_history=chat_history,
        models=AVAILABLE_MODELS,
        selected_model=selected_model,
        chat_id=chat_id,
        chat_list=chat_list
    )

@app.route('/stream/<chat_id>', methods=['POST'])
@token_required
def stream_response(current_user, chat_id):
    from ollama import chat as ollama_chat
    
    # Get data from request
    data = request.get_json()
    prompt = data['prompt']
    model = data['model']
    
    # Update the chat model if it changed
    current_model = get_chat_model(chat_id)
    if model != current_model:
        session_redis.set(f"chat:model:{chat_id}", model)
    
    # Get chat history
    chat_history = get_chat_history(chat_id, model)
    
    # Check if this is the first message (for title generation)
    is_first_message = len(chat_history) == 0
    
    # Add the user's message to history
    chat_history.append({"role": "user", "content": prompt})
    
    # Save updated history
    save_chat(chat_id, model, chat_history)
    
    # Track the full response to save later
    full_response = []
    
    def generate():
        title_updated = False
        try:
            # Stream the response from the model
            stream = ollama_chat(model=model, messages=chat_history, stream=True)
            for chunk in stream:
                content = chunk['message']['content']
                full_response.append(content)
                yield content
        except Exception as e:
            yield f"Error: {e}"
        finally:
            # Save the complete response to history
            response_text = ''.join(full_response)
            chat_history.append({"role": "assistant", "content": response_text})
            save_chat(chat_id, model, chat_history)
            
            # Always update the chat title for the first message, regardless of current title
            if is_first_message:
                title_key = f"chat:title:{chat_id}"
                # Generate a title based on the prompt
                title_prompt = f"Create a very short, descriptive title (maximum 5 words) for a conversation that starts with this message: {prompt.strip()}"
                try:
                    title_response = ollama_chat(
                        model='mistral',
                        messages=[{"role": "user", "content": title_prompt}],
                        stream=False
                    )
                    new_title = title_response['message']['content'].strip()
                    # Remove quotes if present
                    new_title = new_title.strip('"\'')
                    # Limit title length and save
                    session_redis.set(title_key, new_title[:50])
                except Exception as e:
                    print(f"Error generating title: {e}")
    
    return Response(generate(), mimetype='text/plain')

@app.route('/chat/<chat_id>/rename', methods=['POST'])
@token_required
def rename_chat(current_user, chat_id):
    # Verify ownership
    owner_id_bytes = session_redis.get(f"chat:user:{chat_id}")
    if not owner_id_bytes or int(owner_id_bytes.decode()) != current_user.id:
        return jsonify(success=False, error="Unauthorized"), 403
    
    data = request.get_json()
    new_title = data.get('title', '').strip()
    if not new_title:
        return jsonify(success=False, error="Title cannot be empty"), 400
    
    # Update the title
    session_redis.set(f"chat:title:{chat_id}", new_title[:100])
    return jsonify(success=True)

@app.route('/chat/<chat_id>/delete', methods=['DELETE'])
@token_required
def delete_chat(current_user, chat_id):
    # Verify ownership
    owner_id_bytes = session_redis.get(f"chat:user:{chat_id}")
    if not owner_id_bytes or int(owner_id_bytes.decode()) != current_user.id:
        return jsonify(success=False, error="Unauthorized"), 403
    
    # Get the model for this chat
    model = get_chat_model(chat_id)
    
    # Delete all associated keys
    session_redis.delete(get_chat_key(chat_id, model))
    session_redis.delete(f"chat:title:{chat_id}")
    session_redis.delete(f"chat:user:{chat_id}")
    session_redis.delete(f"chat:model:{chat_id}")
    session_redis.srem(f"user:{current_user.id}:chats", chat_id)
    
    return jsonify(success=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True, threaded=True)