from flask import Blueprint, render_template, request, redirect, url_for, jsonify, Response
from auth import token_required
from chat_service import ChatService
from ollama_service import OllamaService
from config import Config

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/')
@token_required
def home(current_user):
    """Home page with chat list"""
    chat_list = ChatService.get_chat_list(current_user.id)
    return render_template('index.html', models=Config.AVAILABLE_MODELS, chat_list=chat_list)

@chat_bp.route('/new')
@token_required
def new_chat(current_user):
    """Create new chat with default model"""
    chat_id = ChatService.create_new_chat(current_user.id)
    return redirect(url_for('main.chat', chat_id=chat_id))

@chat_bp.route('/new_chat', methods=['POST'])
@token_required
def create_new_chat(current_user):
    """Create new chat with selected model"""
    model = request.form.get('model', Config.AVAILABLE_MODELS[0])
    chat_id = ChatService.create_new_chat(current_user.id, model)
    return redirect(url_for('main.chat', chat_id=chat_id, model=model))

@chat_bp.route('/chat/<chat_id>')
@token_required
def chat(current_user, chat_id):
    """View specific chat"""
    if not ChatService.verify_chat_ownership(chat_id, current_user.id):
        return "Unauthorized", 403
    
    selected_model = ChatService.get_chat_model(chat_id)
    chat_history = ChatService.get_chat_history(chat_id, selected_model)
    chat_list = ChatService.get_chat_list(current_user.id)
    
    return render_template(
        'index.html',
        chat_history=chat_history,
        models=Config.AVAILABLE_MODELS,
        selected_model=selected_model,
        chat_id=chat_id,
        chat_list=chat_list
    )

@chat_bp.route('/stream/<chat_id>', methods=['POST'])
@token_required
def stream_response(current_user, chat_id):
    """Stream AI response for chat"""
    if not ChatService.verify_chat_ownership(chat_id, current_user.id):
        return "Unauthorized", 403
    
    data = request.get_json()
    prompt = data['prompt']
    model = data['model']
    
    # Update chat model if changed
    current_model = ChatService.get_chat_model(chat_id)
    if model != current_model:
        ChatService.update_chat_model(chat_id, model)
    
    # Get chat history
    chat_history = ChatService.get_chat_history(chat_id, model)
    is_first_message = len(chat_history) == 0
    
    # Add user message to history
    chat_history.append({"role": "user", "content": prompt})
    ChatService.save_chat(chat_id, model, chat_history)
    
    # Track full response
    full_response = []
    
    def generate():
        try:
            stream = OllamaService.generate_response(model, chat_history, stream=True)
            for chunk in stream:
                content = chunk['message']['content']
                full_response.append(content)
                yield content
        except Exception as e:
            yield f"Error: {e}"
        finally:
            # Save complete response
            response_text = ''.join(full_response)
            chat_history.append({"role": "assistant", "content": response_text})
            ChatService.save_chat(chat_id, model, chat_history)
            
            # Generate title for first message
            if is_first_message:
                new_title = OllamaService.generate_title(prompt)
                ChatService.update_chat_title(chat_id, new_title)
    
    return Response(generate(), mimetype='text/plain')

@chat_bp.route('/chat/<chat_id>/rename', methods=['POST'])
@token_required
def rename_chat(current_user, chat_id):
    """Rename a chat"""
    if not ChatService.verify_chat_ownership(chat_id, current_user.id):
        return jsonify(success=False, error="Unauthorized"), 403
    
    data = request.get_json()
    new_title = data.get('title', '').strip()
    
    if not new_title:
        return jsonify(success=False, error="Title cannot be empty"), 400
    
    ChatService.update_chat_title(chat_id, new_title)
    return jsonify(success=True)

@chat_bp.route('/chat/<chat_id>/delete', methods=['DELETE'])
@token_required
def delete_chat(current_user, chat_id):
    """Delete a chat"""
    success = ChatService.delete_chat(chat_id, current_user.id)
    
    if not success:
        return jsonify(success=False, error="Unauthorized"), 403
    
    return jsonify(success=True)