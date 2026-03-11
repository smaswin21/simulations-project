"""
nodes.py — Node management for the episodic memory graph.

Episode, fact, and commitment node creation + query helpers.
"""

from agent_flow.embedding import embed_text


class NodesMixin:
    """Mixin providing node management methods for EpisodicMemoryGraph."""

    def add_episode(
        self,
        round_num: int,
        perception_text: str,
        outcomes: list[dict],
    ) -> str:
        """
        Store one round's observation as an episode node.

        Args:
            round_num: which simulation round (1-indexed)
            perception_text: the full perception string the agent received
            outcomes: list of resolved outcome dicts from environment.resolve_actions(),
                      filtered to only those relevant to this agent

        Returns:
            The node ID of the created episode (e.g. "ep_0").
        """
        node_id = f"ep_{self.episode_counter}"
        importance = self._score_importance(round_num, outcomes)

        # Phase 3: embed the perception text at storage time
        vec = embed_text(perception_text)

        self.graph.add_node(
            node_id,
            type="episode",
            round=round_num,
            content=perception_text,
            outcomes=outcomes,
            importance=importance,
            embedding=vec,  # np.ndarray (384,) or None if model unavailable
        )

        # This links to previous episode for temporal ordering.
        if self.episode_counter > 0:
            prev_id = f"ep_{self.episode_counter - 1}"
            self.graph.add_edge(prev_id, node_id, rel="NEXT")

        self.episode_counter += 1
        return node_id

    # ── Phase 2: Fact nodes (Step 6 + Step 8) ────────────────

    def add_fact(
        self,
        content: str,
        subject: str,
        round_num: int,
        confidence: float,
        source_episode_id: str,
    ) -> str:
        """
        Create a fact node and link it to its source episode.

        Node schema (Step 6):
            id:         fact_0, fact_1, ...
            type:       "fact"
            content:    short factual statement
            subject:    which agent or object this fact is about
            round:      when this fact was extracted
            confidence: float 0–1

        Edge (Step 8):
            fact_id → source_episode_id  with rel="EXTRACTED_FROM"

        Returns:
            The node ID of the created fact (e.g. "fact_0").
        """
        node_id = f"fact_{self.fact_counter}"

        # Phase 3: embed the fact content
        vec = embed_text(content)

        self.graph.add_node(
            node_id,
            type="fact",
            content=content,
            subject=subject,
            round=round_num,
            confidence=confidence,
            embedding=vec,
        )

        # Provenance edge: fact traces back to the raw episode
        if source_episode_id in self.graph:
            self.graph.add_edge(node_id, source_episode_id, rel="EXTRACTED_FROM")

        # Phase 4: Check for contradictions against prior facts on the same subject
        self._detect_contradictions(node_id, content, subject, vec)

        self.fact_counter += 1
        return node_id

    # ── Phase 2: Commitment nodes (Step 9) ───────────────────

    def add_commitment(
        self,
        agent: str,
        content: str,
        round_made: int,
        source_episode_id: str,
        status: str = "pending",
    ) -> str:
        """
        Create a commitment node and link it to its source episode.

        Node schema (Step 9):
            id:         commit_{agent}_{round}
            type:       "commitment"
            agent:      who made the promise
            content:    what they promised
            round_made: when the promise was made
            status:     "pending" | "kept" | "broken"

        Edge:
            commit_id → source_episode_id  with rel="EXTRACTED_FROM"

        Returns:
            The node ID of the created commitment.
        """
        node_id = f"commit_{agent}_{round_made}"

        # If a commitment from this agent in this round already exists,
        # append a counter suffix to keep IDs unique
        if node_id in self.graph:
            node_id = f"commit_{agent}_{round_made}_{self.commitment_counter}"

        self.graph.add_node(
            node_id,
            type="commitment",
            agent=agent,
            content=content,
            round_made=round_made,
            status=status,
            embedding=embed_text(content),  # Phase 3
        )

        # Provenance edge
        if source_episode_id in self.graph:
            self.graph.add_edge(node_id, source_episode_id, rel="EXTRACTED_FROM")

        self.commitment_counter += 1
        return node_id

    def update_commitment_status(self, commitment_id: str, new_status: str) -> bool:
        """
        Update a commitment's status to 'kept' or 'broken'.

        Returns True if the node exists and was updated.
        """
        if commitment_id in self.graph and self.graph.nodes[commitment_id].get("type") == "commitment":
            self.graph.nodes[commitment_id]["status"] = new_status
            return True
        return False

    # ── Query helpers for Phase 2 nodes ──────────────────────

    def get_all_facts(self) -> list[tuple[str, dict]]:
        """Return all fact nodes as (node_id, attributes) pairs, sorted by round."""
        facts = [
            (nid, data)
            for nid, data in self.graph.nodes(data=True)
            if data.get("type") == "fact"
        ]
        facts.sort(key=lambda x: x[1].get("round", 0))
        return facts

    def get_all_commitments(self) -> list[tuple[str, dict]]:
        """Return all commitment nodes as (node_id, attributes) pairs."""
        commits = [
            (nid, data)
            for nid, data in self.graph.nodes(data=True)
            if data.get("type") == "commitment"
        ]
        commits.sort(key=lambda x: x[1].get("round_made", 0))
        return commits

    def get_facts_for_episode(self, episode_id: str) -> list[tuple[str, dict]]:
        """Return facts extracted from a specific episode."""
        facts = []
        for pred in self.graph.predecessors(episode_id):
            edge_data = self.graph.edges[pred, episode_id]
            node_data = self.graph.nodes[pred]
            if edge_data.get("rel") == "EXTRACTED_FROM" and node_data.get("type") == "fact":
                facts.append((pred, dict(node_data)))
        return facts

    def get_episode(self, episode_id: str) -> dict | None:
        """Get a single episode's attributes by node ID."""
        if episode_id in self.graph:
            return dict(self.graph.nodes[episode_id])
        return None

    def get_all_episodes(self) -> list[tuple[str, dict]]:
        """Return all episode nodes as (node_id, attributes) pairs, sorted by round."""
        episodes = [
            (nid, data)
            for nid, data in self.graph.nodes(data=True)
            if data.get("type") == "episode"
        ]
        episodes.sort(key=lambda x: x[1].get("round", 0))
        return episodes
