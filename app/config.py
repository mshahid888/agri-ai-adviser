from pathlib import Path
from dotenv import load_dotenv
import os
load_dotenv()
OMNIROUTE_BASE_URL = os.getenv(
    "OMNIROUTE_BASE_URL",
    "http://localhost:20128/v1",
)
OMNIROUTE_API_KEY = os.getenv("OMNIROUTE_API_KEY")
AGRI_AI_MODEL = os.getenv(
    "AGRI_AI_MODEL",
    "gemini/gemini-3-flash-preview",
)
if not OMNIROUTE_API_KEY:
    raise RuntimeError("OMNIROUTE_API_KEY is not configured.")
