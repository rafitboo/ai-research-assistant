import os
import google.generativeai as genai

# Load Gemini globally once
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_gemini_model(model_name: str = "gemini-2.0-flash"):
    """Global helper function to get a configured Gemini model across any feature."""
    return genai.GenerativeModel(model_name)