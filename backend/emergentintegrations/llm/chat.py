import google.generativeai as genai
import os

class UserMessage:
    def __init__(self, text):
        self.text = text

class LlmChat:
    def __init__(self, key, session_id, system_message):
        self.key = key
        self.session_id = session_id
        self.system_message = system_message
        self.model_name = "gemini-1.5-flash"
        if key:
            genai.configure(api_key=key)
        
    def with_model(self, provider, model):
        self.model_name = "gemini-1.5-flash"
        return self
        
    async def send_message(self, user_msg):
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self.system_message
        )
        response = await model.generate_content_async(user_msg.text)
        return response.text
