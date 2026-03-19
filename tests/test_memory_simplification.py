import asyncio
import unittest
from unittest.mock import patch

import numpy as np

from agent_flow.fact_extractor import extract_beliefs
from agent_flow.memory.graph import EpisodicMemoryGraph


class FakeLLMProvider:
    def __init__(self, response: str):
        self.response = response

    async def generate(self, system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> str:
        return self.response


class MemorySimplificationTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            patch("agent_flow.memory.nodes.embed_text", return_value=None),
            patch("agent_flow.memory.retrieval.embed_text", return_value=None),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()

    def test_graph_uses_only_episode_provenance_edges(self):
        memory = EpisodicMemoryGraph(agent_name="Ava")
        episode_id = memory.add_episode(round_num=1, perception_text="round one", outcomes=[])
        memory.add_fact(
            content="Ava took 2 units from the commons this round.",
            subject="Ava",
            round_num=1,
            confidence=1.0,
            source_episode_id=episode_id,
            category="fairness",
            numeric_value=2.0,
        )

        edge_rels = {data["rel"] for _, _, data in memory.graph.edges(data=True)}
        self.assertEqual(edge_rels, {"EXTRACTED_FROM"})

    def test_extract_beliefs_adds_fairness_and_health_only(self):
        memory = EpisodicMemoryGraph(agent_name="Ava")
        episode_id = memory.add_episode(round_num=2, perception_text="round two", outcomes=[])
        outcomes = [
            {"agent": "Ben", "action": "graze", "detail": "Grazed 2 units via aggressive harvest"},
            {"agent": "Rae", "action": "sanction", "detail": "Queued sanction against Ben for next round."},
            {"agent": "Scout", "action": "report", "detail": "Scout ecological report: stock=35 units, regeneration=12, last_round_grazed=5"},
        ]

        result = asyncio.run(
            extract_beliefs(
                memory=memory,
                episode_id=episode_id,
                round_num=2,
                outcomes=outcomes,
                agent_inventories={"Ava": 1, "Ben": 4, "Cara": 1},
                llm_provider=None,
            )
        )

        categories = {belief["category"] for belief in result["beliefs"]}
        self.assertEqual(categories, {"fairness", "resource_health"})
        self.assertTrue(any("taking more than a fair share" in belief["content"] for belief in result["beliefs"]))
        self.assertTrue(any("substantially more than the rest" in belief["content"] for belief in result["beliefs"]))

    def test_message_extraction_accepts_only_fairness_beliefs(self):
        memory = EpisodicMemoryGraph(agent_name="Ava")
        episode_id = memory.add_episode(round_num=3, perception_text="round three", outcomes=[])
        outcomes = [
            {
                "agent": "Ava",
                "action": "message",
                "detail": "Ben is taking too much from the commons again.",
            }
        ]
        provider = FakeLLMProvider(
            '{"beliefs":[{"subject":"Ben","content":"Ben appears to be taking more than a fair share."},'
            '{"subject":"pasture","content":"The pasture looks stressed."}]}'
        )

        result = asyncio.run(
            extract_beliefs(
                memory=memory,
                episode_id=episode_id,
                round_num=3,
                outcomes=outcomes,
                agent_inventories={"Ava": 1, "Ben": 3},
                llm_provider=provider,
            )
        )

        self.assertEqual(len(result["beliefs"]), 1)
        self.assertEqual(result["beliefs"][0]["category"], "fairness")
        self.assertEqual(result["beliefs"][0]["subject"], "Ben")

    def test_ranked_retrieval_does_not_change_for_nearby_subjects(self):
        memory = EpisodicMemoryGraph(agent_name="Ava")
        ben_episode = memory.add_episode(round_num=2, perception_text="Ben episode", outcomes=[])
        cara_episode = memory.add_episode(round_num=2, perception_text="Cara episode", outcomes=[])

        ben_fact = memory.add_fact(
            content="Ben took 2 units from the commons this round.",
            subject="Ben",
            round_num=2,
            confidence=1.0,
            source_episode_id=ben_episode,
            category="fairness",
        )
        cara_fact = memory.add_fact(
            content="Cara coordinated a fair harvest this round.",
            subject="Cara",
            round_num=2,
            confidence=1.0,
            source_episode_id=cara_episode,
            category="fairness",
        )

        memory.graph.nodes[ben_fact]["embedding"] = np.asarray([0.6, 0.8], dtype=np.float32)
        memory.graph.nodes[cara_fact]["embedding"] = np.asarray(
            [0.7, np.sqrt(1.0 - 0.49)],
            dtype=np.float32,
        )

        query_vec = np.asarray([1.0, 0.0], dtype=np.float32)
        with patch("agent_flow.memory.retrieval.embed_text", return_value=query_vec):
            without_nearby = memory.retrieve_relevant(
                current_reflection="fair harvesting",
                current_round=2,
                nearby_agents=set(),
            )
            with_nearby = memory.retrieve_relevant(
                current_reflection="fair harvesting",
                current_round=2,
                nearby_agents={"Ben"},
            )

        self.assertEqual(without_nearby[0][0], cara_fact)
        self.assertEqual(with_nearby[0][0], cara_fact)
        self.assertEqual(
            [node_id for node_id, _, _ in without_nearby[:2]],
            [node_id for node_id, _, _ in with_nearby[:2]],
        )

    def test_heuristic_retrieval_does_not_change_for_nearby_subjects(self):
        memory = EpisodicMemoryGraph(agent_name="Ava")
        ben_episode = memory.add_episode(round_num=2, perception_text="Ben episode", outcomes=[])
        cara_episode = memory.add_episode(round_num=2, perception_text="Cara episode", outcomes=[])

        ben_fact = memory.add_fact(
            content="Ben took 2 units from the commons this round.",
            subject="Ben",
            round_num=2,
            confidence=0.7,
            source_episode_id=ben_episode,
            category="fairness",
        )
        cara_fact = memory.add_fact(
            content="Cara kept to a fair share this round.",
            subject="Cara",
            round_num=2,
            confidence=0.8,
            source_episode_id=cara_episode,
            category="fairness",
        )

        without_nearby = memory.retrieve_memories(
            current_round=2,
            nearby_agents=set(),
        )
        with_nearby = memory.retrieve_memories(
            current_round=2,
            nearby_agents={"Ben"},
        )

        self.assertEqual(without_nearby["facts"][0][0], cara_fact)
        self.assertEqual(with_nearby["facts"][0][0], cara_fact)
        self.assertEqual(
            [fact_id for fact_id, _ in without_nearby["facts"][:2]],
            [fact_id for fact_id, _ in with_nearby["facts"][:2]],
        )
        self.assertNotEqual(ben_fact, cara_fact)


if __name__ == "__main__":
    unittest.main()
