"""
memory_graph.py — Backward-compatible shim for the modular belief-memory package.
"""

from agent_flow.memory.graph import EpisodicMemoryGraph  # noqa: F401

__all__ = ["EpisodicMemoryGraph"]
