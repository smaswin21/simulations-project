"""
agent_flow.memory — Modular episodic memory graph package.

Re-exports EpisodicMemoryGraph so existing imports continue to work:
    from agent_flow.memory_graph import EpisodicMemoryGraph
    from agent_flow.memory import EpisodicMemoryGraph   # also works
"""

from agent_flow.memory.graph import EpisodicMemoryGraph

__all__ = ["EpisodicMemoryGraph"]
