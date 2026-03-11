"""
config.py — Simulation settings in one place.
"""

import os
from dotenv import load_dotenv
load_dotenv()

# --- LLM Settings --- 
USE_OLLAMA = True 

# Ollama settings
MODEL_NAME = "llama3.2:1b"  # 1B params - fast and local
API_BASE = "http://localhost:11434/v1"
API_KEY = "ollama" 

# Anthropic settings 
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

TEMPERATURE = 0.7
MAX_TOKENS = 400
MAX_CONCURRENT_AGENTS = 5

# --- Embedding / Memory Retrieval Settings (Phase 3) ---
EMBEDDING_MODEL = "all-MiniLM-L6-v2"   # 384-dim, ~80 MB, CPU-friendly
EMBEDDING_DIM = 384
RECENCY_DECAY = 0.15                    # exp(-RECENCY_DECAY * rounds_ago)
RETRIEVAL_TOP_K = 7                     # memories injected per LLM call

# --- Contradiction Detection & Graph Expansion (Phase 4) ---
COSINE_CONTRADICT_THRESHOLD = 0.30      # below this → flag as contradiction
CONTRADICTION_BONUS = 1.5               # score multiplier for nodes with CONTRADICTS edge
BROKEN_COMMIT_BONUS = 1.3               # score multiplier for broken commitments
EXPANSION_BONUS = 1.1                   # score multiplier for nodes pulled via one-hop expansion
COMMITMENT_KEPT_ROUNDS = 2              # rounds without contradiction before marking "kept"
USE_LLM_CONTRADICTION = False           # True = add LLM-based contradiction check (expensive)

# --- Phase 5: Ablation toggle ---
USE_LAYER2_MEMORY = True   # False = Condition A (no memory), True = Condition B (memory ON)

# --- Settings ---
NUM_ROUNDS = 15

# Past rounds of speech to display in each agent's perception
SPEECH_HISTORY_ROUNDS = 2
