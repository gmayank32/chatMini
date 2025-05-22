from ollama import chat as ollama_chat

class OllamaService:
    """Service for interacting with Ollama AI models"""
    
    @staticmethod
    def generate_response(model, messages, stream=True):
        """Generate AI response using Ollama"""
        try:
            return ollama_chat(model=model, messages=messages, stream=stream)
        except Exception as e:
            raise Exception(f"Ollama error: {str(e)}")
    
    @staticmethod
    def generate_title(prompt, model='mistral'):
        """Generate a title for a chat based on the first message"""
        title_prompt = f"Create a very short, descriptive title (maximum 5 words) for a conversation that starts with this message: {prompt.strip()}"
        
        try:
            response = ollama_chat(
                model=model,
                messages=[{"role": "user", "content": title_prompt}],
                stream=False
            )
            title = response['message']['content'].strip()
            # Remove quotes if present
            title = title.strip('"\' ')
            return title[:50]  # Limit title length
        except Exception as e:
            print(f"Error generating title: {e}")
            return "New Chat"