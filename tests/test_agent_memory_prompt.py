import unittest
from unittest.mock import patch

from agent_flow.agent import Agent, MEMORY_ACTION_GUIDANCE


class FakeProvider:
    async def generate(self, system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> str:
        return ""


def build_agent(role: str) -> Agent:
    return Agent(
        profile={"name": "Ava"},
        persona_prompt="persona",
        scenario={},
        role=role,
        llm_provider=FakeProvider(),
    )


class AgentMemoryPromptTests(unittest.TestCase):
    def test_memory_guidance_included_for_herder_when_memory_on_and_present(self):
        agent = build_agent("Herder")
        with patch("config.config.USE_LAYER2_MEMORY", True):
            prompt = agent._build_action_prompt(
                perception="perception",
                reflection="reflection",
                memory_block="RELEVANT BELIEFS:\n  [fairness] Ben appears unfair.",
            )

        self.assertIn(MEMORY_ACTION_GUIDANCE, prompt)
        self.assertIn("prefer GRAZE_SUSTAINABLE over GRAZE_AGGRESSIVE", prompt)
        self.assertIn("RELEVANT BELIEFS:", prompt)

    def test_memory_guidance_not_included_when_memory_off(self):
        agent = build_agent("Regulator")
        with patch("config.config.USE_LAYER2_MEMORY", False):
            prompt = agent._build_action_prompt(
                perception="perception",
                reflection="reflection",
                memory_block="RELEVANT BELIEFS:\n  [fairness] Ben appears unfair.",
            )

        self.assertNotIn(MEMORY_ACTION_GUIDANCE, prompt)
        self.assertNotIn("prefer SANCTION <agent_name>", prompt)

    def test_memory_guidance_not_included_when_memory_block_empty(self):
        agent = build_agent("Scout")
        with patch("config.config.USE_LAYER2_MEMORY", True):
            prompt = agent._build_action_prompt(
                perception="perception",
                reflection="reflection",
                memory_block="",
            )

        self.assertNotIn(MEMORY_ACTION_GUIDANCE, prompt)
        self.assertNotIn("prefer REPORT_DATA", prompt)


if __name__ == "__main__":
    unittest.main()
