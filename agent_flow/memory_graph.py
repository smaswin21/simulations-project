"""
memory_graph.py — Backward-compatible shim.

The implementation has been modularized into the agent_flow.memory package:
  - agent_flow/memory/graph.py          — core class, init, serialization
  - agent_flow/memory/scoring.py        — importance scoring
  - agent_flow/memory/nodes.py          — episode/fact/commitment node management
  - agent_flow/memory/contradiction.py  — Phase 4 contradiction detection
  - agent_flow/memory/retrieval.py      — embedding + heuristic retrieval
  - agent_flow/memory/formatting.py     — prompt injection formatting

This file re-exports EpisodicMemoryGraph so existing imports keep working:
    from agent_flow.memory_graph import EpisodicMemoryGraph
"""

from agent_flow.memory.graph import EpisodicMemoryGraph  # noqa: F401

__all__ = ["EpisodicMemoryGraph"]
