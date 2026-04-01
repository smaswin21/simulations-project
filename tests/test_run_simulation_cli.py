import os
import unittest
from unittest.mock import patch

import run_simulation


class RunSimulationCLITests(unittest.TestCase):
    def _parse_args(self, *args: str):
        parser = run_simulation.build_parser()
        return parser.parse_args(list(args))

    @patch.dict(os.environ, {}, clear=True)
    @patch("config.llms.selection.discover_ollama_models", return_value=[])
    def test_no_provider_or_model_prompts_for_provider_and_model(self, _discover_mock):
        args = self._parse_args()
        prompts = []
        responses = iter(["1", "2"])

        def fake_input(prompt: str) -> str:
            prompts.append(prompt)
            return next(responses)

        settings = run_simulation.resolve_llm_settings(
            args,
            input_func=fake_input,
            is_interactive=True,
        )

        self.assertEqual(settings.provider, "ollama")
        self.assertEqual(settings.model, "llama3.2:1b")
        self.assertEqual(prompts, ["Provider [1]: ", "Model [llama3.2:1b]: "])

    @patch.dict(os.environ, {}, clear=True)
    def test_partial_flags_prompt_only_for_model(self):
        args = self._parse_args("--openai")
        prompts = []
        responses = iter(["2"])

        def fake_input(prompt: str) -> str:
            prompts.append(prompt)
            return next(responses)

        settings = run_simulation.resolve_llm_settings(
            args,
            input_func=fake_input,
            is_interactive=True,
        )

        self.assertEqual(settings.provider, "openai")
        self.assertEqual(settings.model, "gpt-5-nano")
        self.assertEqual(prompts, ["Model [gpt-5.4]: "])

    def test_full_flags_skip_prompting(self):
        args = self._parse_args("--gemini", "--model", "gemini-3-flash-preview")

        def unexpected_input(_prompt: str) -> str:
            raise AssertionError("input() should not be called when provider and model are provided")

        settings = run_simulation.resolve_llm_settings(
            args,
            input_func=unexpected_input,
            is_interactive=True,
        )

        self.assertEqual(settings.provider, "gemini")
        self.assertEqual(settings.model, "gemini-3-flash-preview")

    def test_claude_flag_maps_to_anthropic(self):
        args = self._parse_args("--claude", "--model", "claude-3-5-sonnet-latest")

        settings = run_simulation.resolve_llm_settings(
            args,
            is_interactive=False,
        )

        self.assertEqual(settings.provider, "anthropic")
        self.assertEqual(settings.model, "claude-3-5-sonnet-latest")

    def test_conflicting_provider_flags_raise_error(self):
        args = self._parse_args("--openai", "--gemini", "--model", "placeholder-model")

        with self.assertRaisesRegex(ValueError, "Conflicting provider flags"):
            run_simulation.resolve_llm_settings(args, is_interactive=False)

    @patch.dict(os.environ, {}, clear=True)
    def test_hosted_prompt_allows_custom_model_id(self):
        args = self._parse_args("--openai")
        prompts = []
        responses = iter(["3", "gpt-custom-benchmark"])

        def fake_input(prompt: str) -> str:
            prompts.append(prompt)
            return next(responses)

        settings = run_simulation.resolve_llm_settings(
            args,
            input_func=fake_input,
            is_interactive=True,
        )

        self.assertEqual(settings.provider, "openai")
        self.assertEqual(settings.model, "gpt-custom-benchmark")
        self.assertEqual(prompts, ["Model [gpt-5.4]: ", "Custom model id: "])


if __name__ == "__main__":
    unittest.main()
