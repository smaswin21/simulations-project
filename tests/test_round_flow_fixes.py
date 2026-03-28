import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from agent_flow.environment import Environment
from agent_flow.memory.graph import EpisodicMemoryGraph
from config.logger import Logger
from config.orchestrator import Orchestrator


class StubAgent:
    def __init__(self, name: str, role: str, decision: dict):
        self.name = name
        self.role = role
        self.location = ""
        self.resource = 0
        self.memory = EpisodicMemoryGraph(agent_name=name)
        self._decision = decision

    async def decide(self, perception: str, round_num: int = 0, nearby_agents: set[str] | None = None) -> dict:
        del perception, round_num, nearby_agents
        return {
            "agent": self.name,
            "role": self.role,
            "reflection": self._decision.get("reflection", "Testing round flow."),
            "message": self._decision.get("message", "NONE"),
            "action_text": self._decision.get("action_text", "WAIT"),
            "reflection_raw": "",
            "response_raw": "",
            "retrieved_labels": [],
        }


class FailingAgent:
    def __init__(self, name: str, role: str, error_message: str):
        self.name = name
        self.role = role
        self.location = ""
        self.resource = 0
        self.memory = EpisodicMemoryGraph(agent_name=name)
        self._error_message = error_message

    async def decide(self, perception: str, round_num: int = 0, nearby_agents: set[str] | None = None) -> dict:
        del perception, round_num, nearby_agents
        raise RuntimeError(self._error_message)


class RoundFlowFixTests(unittest.TestCase):
    def setUp(self):
        self.scenario = {
            "simulation": {"name": "Test Commons", "max_rounds": 3},
            "locations": [
                {"name": "Village Council", "starting_location": True},
                {"name": "Pasture"},
            ],
            "resource": {
                "name": "grazing_units",
                "unit": "units",
                "location": "Pasture",
                "initial_supply": 120,
            },
            "commons": {
                "regeneration_per_round": 12,
                "collapse_threshold": 20,
                "max_stock": 120,
                "suggested_quota_per_agent": 1,
            },
        }
        self.embed_patch = patch("agent_flow.memory.nodes.embed_text", return_value=None)
        self.embed_patch.start()

    def tearDown(self):
        self.embed_patch.stop()

    def test_message_location_stays_in_council_and_is_public_to_all_agents(self):
        agents = [
            StubAgent(
                "Ava",
                "Herder",
                {"message": "We should slow down.", "action_text": "MOVE_PASTURE"},
            ),
            StubAgent("Ben", "Regulator", {"message": "NONE", "action_text": "WAIT"}),
        ]
        env = Environment(agents, self.scenario)
        logger = Logger()
        orch = Orchestrator(
            agents=agents,
            environment=env,
            logger=logger,
            llm_provider=None,
            scenario=self.scenario,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            orch._speech_log_path = Path(tmpdir) / "speech.jsonl"
            with patch("config.orchestrator.extract_beliefs", new=AsyncMock(return_value={"facts": 0, "beliefs": []})):
                asyncio.run(orch.run_round())

            records = [
                json.loads(line)
                for line in orch._speech_log_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(env.agents["Ava"].location, "Pasture")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["speaker"], "Ava")
        self.assertEqual(records[0]["location"], "Village Council")

        ben_episode = agents[1].memory.get_all_episodes()[0][1]
        ben_message_outcomes = [
            outcome
            for outcome in ben_episode["outcomes"]
            if outcome.get("action") == "message"
        ]
        self.assertEqual(len(ben_message_outcomes), 1)
        self.assertEqual(ben_message_outcomes[0]["agent"], "Ava")
        self.assertEqual(ben_message_outcomes[0]["event_location"], "Village Council")

    def test_report_outcomes_record_stable_event_location(self):
        scout = StubAgent("Cy", "Scout", {"message": "NONE", "action_text": "REPORT_DATA"})
        env = Environment([scout], self.scenario)
        env._set_location("Cy", "Pasture")

        outcomes = env.resolve_actions(
            [
                {
                    "agent": "Cy",
                    "role": "Scout",
                    "type": "report",
                    "message": "NONE",
                }
            ],
            start_locations={"Cy": "Pasture"},
        )

        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0]["action"], "report")
        self.assertEqual(outcomes[0]["event_location"], "Village Council")

    def test_run_round_raises_when_all_agent_decisions_fail(self):
        agents = [
            FailingAgent("Ava", "Herder", "Anthropic billing error"),
            FailingAgent("Ben", "Regulator", "Anthropic billing error"),
        ]
        env = Environment(agents, self.scenario)
        logger = Logger()
        orch = Orchestrator(
            agents=agents,
            environment=env,
            logger=logger,
            llm_provider=None,
            scenario=self.scenario,
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "All agent decisions failed in round 1.*Anthropic billing error",
        ):
            asyncio.run(orch.run_round())


if __name__ == "__main__":
    unittest.main()
