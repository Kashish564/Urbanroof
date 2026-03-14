import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv('GOOGLE_API_KEY')
print(f"Loaded API key: {api_key[:10]}...{api_key[-5:]}")
genai.configure(api_key=api_key)

try:
    print('Available embedding models on this key:')
    for m in genai.list_models():
        if 'embed' in m.name:
            print(f" - {m.name} (Methods: {m.supported_generation_methods})")
except Exception as e:
    import traceback
    traceback.print_exc()
