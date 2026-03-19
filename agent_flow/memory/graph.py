"""
graph.py — Core EpisodicMemoryGraph class for belief-oriented memory.
"""

import networkx as nx

from agent_flow.embedding import embed_text
from agent_flow.memory.formatting import FormattingMixin
from agent_flow.memory.nodes import NodesMixin
from agent_flow.memory.retrieval import RetrievalMixin
from agent_flow.memory.scoring import ScoringMixin

DEFAULT_EVENT_ROUNDS = {5, 8, 12, 15}


class EpisodicMemoryGraph(
    ScoringMixin,
    NodesMixin,
    RetrievalMixin,
    FormattingMixin,
):
    def __init__(self, agent_name: str, event_rounds: set[int] | None = None):
        self.agent_name = agent_name
        self.episode_counter = 0
        self.fact_counter = 0
        self.event_rounds = event_rounds if event_rounds is not None else DEFAULT_EVENT_ROUNDS
        self.graph = nx.DiGraph()

    @property
    def episode_count(self) -> int:
        return self.episode_counter

    @property
    def fact_count(self) -> int:
        return self.fact_counter

    def to_dict(self) -> dict:
        graph_data = nx.node_link_data(self.graph)
        for node in graph_data.get("nodes", []):
            if "embedding" in node:
                node["embedding"] = None

        return {
            "agent_name": self.agent_name,
            "episode_counter": self.episode_counter,
            "fact_counter": self.fact_counter,
            "event_rounds": sorted(self.event_rounds),
            "graph": graph_data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EpisodicMemoryGraph":
        agent_name = data["agent_name"]
        event_rounds = set(data.get("event_rounds", DEFAULT_EVENT_ROUNDS))
        instance = cls(agent_name=agent_name, event_rounds=event_rounds)
        instance.graph = nx.node_link_graph(data["graph"])
        instance.episode_counter = data.get("episode_counter", 0)
        instance.fact_counter = data.get("fact_counter", 0)
        instance.re_embed_all()
        return instance

    def re_embed_all(self) -> int:
        count = 0
        for node_id, data in self.graph.nodes(data=True):
            if data.get("embedding") is not None:
                continue
            content = data.get("content")
            if not content:
                continue
            vec = embed_text(content)
            if vec is None:
                continue
            self.graph.nodes[node_id]["embedding"] = vec
            count += 1
        return count

    def __repr__(self) -> str:
        return (
            f"EpisodicMemoryGraph(agent={self.agent_name}, "
            f"episodes={self.episode_counter}, facts={self.fact_counter})"
        )
