"""
nodes.py — Episode and fact node management.
"""

from agent_flow.embedding import embed_text


class NodesMixin:
    def add_episode(self, round_num: int, perception_text: str, outcomes: list[dict]) -> str:
        node_id = f"ep_{self.episode_counter}"
        importance = self._score_importance(round_num, outcomes)
        self.graph.add_node(
            node_id,
            type="episode",
            round=round_num,
            content=perception_text,
            outcomes=outcomes,
            importance=importance,
            embedding=embed_text(perception_text),
        )
        self.episode_counter += 1
        return node_id

    def add_fact(
        self,
        content: str,
        subject: str,
        round_num: int,
        confidence: float,
        source_episode_id: str,
        category: str,
        numeric_value: float | None = None,
        source_kind: str = "observation",
    ) -> str:
        node_id = f"fact_{self.fact_counter}"
        vec = embed_text(content)
        self.graph.add_node(
            node_id,
            type="fact",
            content=content,
            category=category,
            subject=subject,
            round=round_num,
            confidence=confidence,
            numeric_value=numeric_value,
            source_kind=source_kind,
            embedding=vec,
        )
        if source_episode_id in self.graph:
            self.graph.add_edge(node_id, source_episode_id, rel="EXTRACTED_FROM")
        else:
            print(f"[memory] Warning: source episode '{source_episode_id}' not in graph — fact '{node_id}' is orphaned")
        self.fact_counter += 1
        return node_id

    def _get_nodes_by_type(self, node_type: str) -> list[tuple[str, dict]]:
        nodes = [
            (node_id, data)
            for node_id, data in self.graph.nodes(data=True)
            if data.get("type") == node_type
        ]
        nodes.sort(key=lambda item: item[1].get("round", 0))
        return nodes

    def get_all_facts(self) -> list[tuple[str, dict]]:
        return self._get_nodes_by_type("fact")

    def get_all_episodes(self) -> list[tuple[str, dict]]:
        return self._get_nodes_by_type("episode")

    def get_facts_for_episode(self, episode_id: str) -> list[tuple[str, dict]]:
        facts = []
        for predecessor in self.graph.predecessors(episode_id):
            edge_data = self.graph.edges[predecessor, episode_id]
            node_data = self.graph.nodes[predecessor]
            if edge_data.get("rel") == "EXTRACTED_FROM" and node_data.get("type") == "fact":
                facts.append((predecessor, dict(node_data)))
        return facts

    def get_episode(self, episode_id: str) -> dict | None:
        if episode_id in self.graph:
            return dict(self.graph.nodes[episode_id])
        return None
