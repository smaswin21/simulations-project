import unittest
from types import SimpleNamespace

from config.orchestrator import Orchestrator, _speech_log_filename


class SpeechLogPathTests(unittest.TestCase):
    def test_speech_log_filename_uses_model_and_simulation_id(self):
        filename = _speech_log_filename(
            model="gpt-5.4",
            simulation_id="abc123",
        )

        self.assertEqual(filename, "speech_log_gpt-5.4_abc123.jsonl")

    def test_speech_log_filename_uses_model_condition_and_seed(self):
        filename = _speech_log_filename(
            model="qwen3.5:9b",
            condition="B",
            seed=42,
        )

        self.assertEqual(filename, "speech_log_qwen3.5-9b_B_42.jsonl")

    def test_orchestrator_uses_sanitized_model_name_in_speech_log_path(self):
        orch = Orchestrator(
            agents=[],
            environment=object(),
            logger=SimpleNamespace(simulation_id="abc123"),
            llm_provider=SimpleNamespace(settings=SimpleNamespace(model="provider/model:latest")),
            scenario={},
        )

        self.assertEqual(
            orch._speech_log_path.name,
            "speech_log_provider-model-latest_abc123.jsonl",
        )


if __name__ == "__main__":
    unittest.main()
