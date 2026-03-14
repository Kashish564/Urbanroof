import google.generativeai as genai
import os
from dotenv import load_dotenv
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
with open("models_output.txt", "w") as f:
    for m in genai.list_models():
        methods = m.supported_generation_methods
        if "generateContent" in methods:
            f.write(f"{m.name}\n")
print("Done")
