import os
import logging

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
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "text-embedding-3-small",
)
SEMANTIC_BOOST_FACTOR = float(
    os.getenv("SEMANTIC_BOOST_FACTOR", "5.0")
)
AGENT_DB_PATH = os.getenv(
    "AGENT_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "agent.db")
)

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_KEY = os.getenv("API_KEY")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "120"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF_FACTOR = float(os.getenv("RETRY_BACKOFF_FACTOR", "2.0"))
UPLOAD_MAX_SIZE = int(os.getenv("UPLOAD_MAX_SIZE", str(10 * 1024 * 1024)))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


def require_omniroute_api_key() -> str:
    if not OMNIROUTE_API_KEY:
        raise RuntimeError(
            "OMNIROUTE_API_KEY is not configured. Set it in the environment or .env before calling the LLM."
        )
    return OMNIROUTE_API_KEY


def configure_logging():
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s' if ENVIRONMENT == "production" else '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
