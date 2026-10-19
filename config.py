import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma")
COMPETITORS_FILE = os.path.join(DATA_DIR, "competitors.json")
STATIC_DIR = os.path.join(BASE_DIR, "static")

CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "86400"))
MAX_PAGES_PER_SITE = int(os.getenv("MAX_PAGES_PER_SITE", "15"))
MIN_TEXT_CHARS = 200

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120

# ---------- OCR settings ----------
OCR_ENABLED = os.getenv("OCR_ENABLED", "true").strip().lower() == "true"
OCR_LANG = os.getenv("OCR_LANG", "eng").strip()
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "").strip()
MAX_IMAGES_PER_PAGE = int(os.getenv("MAX_IMAGES_PER_PAGE", "6"))
MIN_IMAGE_WIDTH = 200
MIN_IMAGE_HEIGHT = 60
MAX_IMAGE_BYTES = 5_000_000

# ---------- LLM settings ----------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none").strip().lower()
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()

# These providers expose an OpenAI-compatible API.
OPENAI_COMPATIBLE_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "openai": "https://api.openai.com/v1",
    "ollama": "http://localhost:11434/v1",
}
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip() or OPENAI_COMPATIBLE_BASE_URLS.get(
    LLM_PROVIDER, ""
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

for _dir in (DATA_DIR, CACHE_DIR, CHROMA_DIR, STATIC_DIR):
    os.makedirs(_dir, exist_ok=True)