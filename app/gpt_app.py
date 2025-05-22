from flask import Flask, render_template, request, Response, redirect, url_for, session, jsonify
from flask_session import Session
import ollama
import os
import redis
import uuid
import json
from datetime import timedelta
import openai
from openai import OpenAI

app = Flask(__name__)
app.secret_key = os.urandom(24)

KEY = "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"

# Redis Configuration
redis_store = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

# Flask Session Config
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_REDIS'] = redis_store
app.config['SESSION_USE_SIGNER'] = True
Session(app)

AVAILABLE_MODELS = ['gpt-3.5-turbo', 'gpt-4o']

@app.before_request
def make_session_permanent():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(days=90)

def get_chat_key(chat_id, model):
    return f"chat:{chat_id}:{model}"

def get_chat_title(chat_id):
    return redis_store.get(f"chat:title:{chat_id}") or "Untitled Chat"

def save_chat(chat_id, model, chat_history):
    redis_store.set(get_chat_key(chat_id, model), json.dumps(chat_history))

def get_chat_list():
    chat_ids = redis_store.smembers("chat:ids")
    return [{"id": cid, "title": get_chat_title(cid)} for cid in chat_ids]

def delete_chat(chat_id):
    # Delete title
    redis_store.delete(f"chat:title:{chat_id}")
    # Delete all chat history for available models
    for model in AVAILABLE_MODELS:
        redis_store.delete(get_chat_key(chat_id, model))
    # Remove from chat set
    redis_store.srem("chat:ids", chat_id)

@app.route('/')
def home():
    return redirect(url_for('new_chat'))

@app.route('/new')
def new_chat():
    new_chat_id = str(uuid.uuid4())
    redis_store.sadd("chat:ids", new_chat_id)
    redis_store.set(f"chat:title:{new_chat_id}", "New Chat")
    return redirect(url_for('chat', chat_id=new_chat_id))

@app.route('/new_chat', methods=['POST'])
def create_new_chat():
    return redirect(url_for('new_chat'))

@app.route('/chat/<chat_id>', methods=['GET'])
def chat(chat_id):
    selected_model = request.args.get('model', 'gpt-3.5-turbo')
    key = get_chat_key(chat_id, selected_model)
    history_raw = redis_store.get(key)
    chat_history = json.loads(history_raw) if history_raw else []

    chat_list = get_chat_list()
    return render_template('index.html',
                           chat_history=chat_history,
                           models=AVAILABLE_MODELS,
                           selected_model=selected_model,
                           chat_id=chat_id,
                           chat_list=chat_list)

@app.route('/stream/<chat_id>', methods=['POST'])
def stream_response(chat_id):
    data = request.get_json()
    prompt = data['prompt']
    model = data['model']  # e.g., "gpt-4" or "gpt-3.5-turbo"

    key = get_chat_key(chat_id, model)
    history_raw = redis_store.get(key)
    history = json.loads(history_raw) if history_raw else []

    history.append({"role": "user", "content": prompt})
    redis_store.set(key, json.dumps(history))

    full_response = []

    def generate():
        try:
            # Convert history into OpenAI-compatible format
            openai_history = [{"role": h["role"], "content": h["content"]} for h in history]

            client = OpenAI(api_key=KEY)
            response = client.chat.completions.create(
                model=model,
                messages=openai_history,
                stream=True
            )

            for chunk in response:
                if 'choices' in chunk and len(chunk['choices']) > 0:
                    delta = chunk['choices'][0]['delta'].get('content', '')
                    full_response.append(delta)
                    yield delta

        except Exception as e:
            yield f"Error: {e}"

        finally:
            response_text = ''.join(full_response)
            history.append({"role": "assistant", "content": response_text})
            redis_store.set(key, json.dumps(history))

            title_key = f"chat:title:{chat_id}"
            if redis_store.get(title_key) == "New Chat" and prompt:
                redis_store.set(title_key, prompt[:40])

    return Response(generate(), mimetype='text/plain')


# ✅ Rename chat title
@app.route('/chat/<chat_id>/rename', methods=['POST'])
def rename_chat(chat_id):
    data = request.get_json()
    new_title = data.get("title", "").strip()
    if new_title:
        redis_store.set(f"chat:title:{chat_id}", new_title[:100])
        return jsonify(success=True), 200
    return jsonify(success=False, error="Invalid title"), 400

# ✅ Delete chat
@app.route('/chat/<chat_id>/delete', methods=['DELETE'])
def delete_chat_route(chat_id):
    delete_chat(chat_id)
    return jsonify(success=True), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True, threaded=True)
