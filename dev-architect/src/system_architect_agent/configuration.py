import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def get_client():
    return OpenAI(
        api_key=os.getenv("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1"
    )