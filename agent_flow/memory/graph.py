"""
graph.py — Core EpisodicMemoryGraph class.

Composes all mixin classes into the final class with init, properties,
serialization (to_dict/from_dict), and __repr__.
"""

import networkx as nx

from agent_flow.memory.scoring import ScoringMixin
from agent_flow.memory.nodes import NodesMixin
from agent_flow.memory.contradiction import ContradictionMixin
from agent_flow.memory.retrieval import RetrievalMixin
from agent_flow.memory.formatting import FormattingMixin
from agent_flow.embedding import embed_text

DEFAULT_EVENT_ROUNDS = {5, 8, 12, 15}


class EpisodicMemoryGraph(
    ScoringMixin,
    NodesMixin,
    ContradictionMixin,
    RetrievalMixin,
    FormattingMixin,
):
    """
    Stores the episodic memories as nodes in a directed graph.
    Each episode represents one round of the simulation from this agent's
    perspective: what they perceived and what outcomes were produced.

    Node types:
        episode  — one round of raw observation + outcomes
        fact     — short factual statement extracted from an episode
        commitment — a promise/agreement detected in speech

    Edge types:
        NEXT           — temporal ordering between episodes
        EXTRACTED_FROM — provenance link from fact/commitment -> episode
        CONTRADICTS    — bidirectional link between facts that contradict
                         each other (Phase 4)
    """

    def __init__(self, agent_name: str, event_rounds: set[int] | None = None):
        self.agent_name = agent_name
        self.episode_counter = 0
        self.fact_counter = 0
        self.commitment_counter = 0
        self.event_rounds = event_rounds if event_rounds is not None else DEFAULT_EVENT_ROUNDS
        self.graph = nx.DiGraph()

    @property
    def episode_count(self) -> int:
        return self.episode_counter

    @property
    def fact_count(self) -> int:
        return self.fact_counter

    @property
    def commitment_count(self) -> int:
        return self.commitment_counter

    def to_dict(self) -> dict:
        """
        Serialize the memory graph to a plain dict (MongoDB-safe).

        Uses nx.node_link_data() for the graph structure, plus metadata.
        Strips numpy embeddings (None for now) to keep it JSON-serializable.
        """
        # Make a copy of graph data, ensuring all values are JSON-safe
        graph_data = nx.node_link_data(self.graph)

        # Strip embedding arrays (they'll be None in Phase 1,
        # but future-proof for Phase 3 numpy arrays)
        for node in graph_data.get("nodes", []):
            if "embedding" in node:
                node["embedding"] = None

        return {
            "agent_name": self.agent_name,
            "episode_counter": self.episode_counter,
            "fact_counter": self.fact_counter,
            "commitment_counter": self.commitment_counter,
            "event_rounds": sorted(self.event_rounds),
            "graph": graph_data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EpisodicMemoryGraph":
        """
        Reconstruct an EpisodicMemoryGraph from a serialized dict.

        Use this to resume a simulation or replay from saved MongoDB data.
        Embeddings are stripped during serialization, so this method
        re-embeds all nodes that have a 'content' attribute.
        """
        agent_name = data["agent_name"]
        event_rounds = set(data.get("event_rounds", DEFAULT_EVENT_ROUNDS))

        instance = cls(agent_name=agent_name, event_rounds=event_rounds)
        instance.graph = nx.node_link_graph(data["graph"])
        instance.episode_counter = data.get("episode_counter", 0)
        instance.fact_counter = data.get("fact_counter", 0)
        instance.commitment_counter = data.get("commitment_counter", 0)

        # Re-embed all nodes (embeddings are stripped during serialization)
        instance.re_embed_all()

        return instance

    def re_embed_all(self) -> int:
        """
        Re-compute embeddings for all nodes that have content but no embedding.

        Called automatically after deserialization (from_dict). Can also be
        called manually if the embedding model was unavailable at load time
        and becomes available later.

        Returns:
            Number of nodes that were (re-)embedded.
        """
        count = 0
        for nid, data in self.graph.nodes(data=True):
            if data.get("embedding") is not None:
                continue
            content = data.get("content")
            if content:
                vec = embed_text(content)
                if vec is not None:
                    self.graph.nodes[nid]["embedding"] = vec
                    count += 1
        return count

    def __repr__(self) -> str:
        return (
            f"EpisodicMemoryGraph(agent={self.agent_name}, "
            f"episodes={self.episode_counter}, "
            f"facts={self.fact_counter}, "
            f"commitments={self.commitment_counter})"
        )
