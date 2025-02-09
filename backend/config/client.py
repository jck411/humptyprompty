import os
import openai
from dotenv import load_dotenv
from backend.config.config import CONFIG

load_dotenv()

def setup_chat_client():
    """Initialize and return the appropriate chat client based on configuration."""
    api_host = CONFIG["API_SETTINGS"]["API_HOST"].lower()

    if api_host == "openai":
        client = openai.AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=CONFIG["API_SERVICES"]["openai"]["BASE_URL"]
        )
        deployment_name = CONFIG["API_SERVICES"]["openai"]["MODEL"]

    elif api_host == "openrouter":
        client = openai.AsyncOpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url=CONFIG["API_SERVICES"]["openrouter"]["BASE_URL"]
        )
        deployment_name = CONFIG["API_SERVICES"]["openrouter"]["MODEL"]
    
    else:
        raise ValueError(f"Unsupported API_HOST: {api_host}")

    return client, deployment_name
