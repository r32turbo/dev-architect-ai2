import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

def get_llm():
    return Groq(api_key=os.getenv("GROQ_API_KEY"))