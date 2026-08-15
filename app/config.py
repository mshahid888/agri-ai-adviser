import os

from dotenv import load_dotenv

load_dotenv()

OMNIROUTE_BASE_URL = os.getenv(
    "OMNIROUTE_BASE_URL",
    "http://localhost:20128/v1",
)
OMNIROUTE_API_KEY = os.getenv("OMNIROUTE_API_KEY")
AGRI_AI_MODEL = os.getenv(
    "AGRI_AI_MODEL",
    "gemini/gemini-3.1-flash-lite",
)


def require_omniroute_api_key() -> str:
    if not OMNIROUTE_API_KEY:
        raise RuntimeError(
            "OMNIROUTE_API_KEY is not configured. Set it in the environment or .env before calling the LLM."
        )
    return OMNIROUTE_API_KEY
