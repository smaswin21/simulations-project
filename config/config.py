"""
config.py — Central simulation and model settings.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# --- LLM provider settings ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mistral").strip().lower()
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:1b").strip()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434/v1").strip()

# Useful aliases for local-first runs. Mistral uses the OpenAI-compatible
# Ollama endpoint in this project.
MISTRAL_BASE_URL = os.getenv("MISTRAL_BASE_URL", OLLAMA_API_BASE).strip()
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "ollama")

# Legacy compatibility flags retained for older scripts.
USE_OLLAMA = LLM_PROVIDER == "mistral"
API_BASE = OLLAMA_API_BASE
API_KEY = MISTRAL_API_KEY
MODEL_NAME = LLM_MODEL
ANTHROPIC_MODEL = LLM_MODEL

TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.4"))
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "450"))
MAX_CONCURRENT_AGENTS = int(os.getenv("MAX_CONCURRENT_AGENTS", "5"))

# --- Embedding / Memory Retrieval Settings ---
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))
RECENCY_DECAY = float(os.getenv("RECENCY_DECAY", "0.15"))
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "7"))
BELIEF_ALIGNMENT_BOOST = float(os.getenv("BELIEF_ALIGNMENT_BOOST", "1.5"))

# --- Contradiction Detection ---
COSINE_CONTRADICT_THRESHOLD = float(
    os.getenv("COSINE_CONTRADICT_THRESHOLD", "0.30")
)
CONTRADICTION_BONUS = float(os.getenv("CONTRADICTION_BONUS", "1.5"))
EXPANSION_BONUS = float(os.getenv("EXPANSION_BONUS", "1.1"))
USE_LLM_CONTRADICTION = _get_bool("USE_LLM_CONTRADICTION", False)

# --- Memory toggle for ablations ---
USE_LAYER2_MEMORY = _get_bool("USE_LAYER2_MEMORY", True)

# --- Simulation settings ---
DEFAULT_SEED = int(os.getenv("SIMULATION_SEED", "42"))
NUM_ROUNDS = int(os.getenv("NUM_ROUNDS", "15"))
SPEECH_HISTORY_ROUNDS = int(os.getenv("SPEECH_HISTORY_ROUNDS", "2"))
