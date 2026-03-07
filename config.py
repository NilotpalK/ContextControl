import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
SQLITE_PATH = BASE_DIR / "context_control.db"

# ── Ollama ─────────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
TAGGER_MODEL    = os.getenv("TAGGER_MODEL", "llama3.2:3b")
MEM0_MODEL      = os.getenv("MEM0_MODEL", "llama3.2:3b")
EMBED_MODEL     = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# ── OpenRouter ─────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MAIN_MODEL          = os.getenv("MAIN_MODEL", "openai/gpt-4o-mini")

# ── mem0 ───────────────────────────────────────────────────────────────────────
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "context_control")
CHROMA_PATH       = os.getenv("CHROMA_PATH", "chroma_db")
KUZU_PATH         = os.getenv("KUZU_PATH", "kuzu_db")

MEM0_CONFIG = {
    "version": "v1.1",
    "embedder": {
        "provider": "huggingface",
        "config": {
            "model": EMBED_MODEL,
        }
    },
    "llm": {
        "provider": "openai",
        "config": {
            "model": MAIN_MODEL,
        }
    },
    "vector_store": {
        "provider": "chroma",
        "config": {
            "collection_name": CHROMA_COLLECTION,
            "path": str(BASE_DIR / CHROMA_PATH),
        }
    },
    "graph_store": {
        "provider": "kuzu",
        "config": {
            "database_path": str(BASE_DIR / KUZU_PATH),
        }
    },
}

# ── Tagger ─────────────────────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.70"))
MENTION_EXCHANGE_MIN = int(os.getenv("MENTION_EXCHANGE_MIN", "1"))

# ── Context assembly ───────────────────────────────────────────────────────────
MAX_EXCHANGES_IN_CONTEXT = int(os.getenv("MAX_EXCHANGES_IN_CONTEXT", "20"))
MAX_TOKENS_CONTEXT       = int(os.getenv("MAX_TOKENS_CONTEXT", "4000"))

# ── Chain reference keywords ───────────────────────────────────────────────────
CHAIN_REFERENCE_KEYWORDS = [
    "that", "it", "those", "what you said", "how does that",
    "what about that", "the same", "as mentioned", "you mentioned",
    "earlier", "before", "previously", "like you said",
    "what we discussed", "you covered", "expand on",
    "going back", "tell me more about that",
]