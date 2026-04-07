import unittest
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from openai import APIConnectionError

from config.llms.providers import (
    GeminiProvider,
    LLMSettings,
    OllamaProvider,
    OpenAIProvider,
    build_settings,
    create_provider,
)


class OpenAIProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_uses_reasoning_effort_for_gpt5_openai_models(self):
        fake_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="MESSAGE:: hi\nACTION:: WAIT"))]
        )
        create = AsyncMock(return_value=fake_response)
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )

        with patch("config.llms.providers.AsyncOpenAI", return_value=fake_client):
            provider = OpenAIProvider(
                LLMSettings(
                    provider="openai",
                    model="gpt-5.4",
                    max_tokens=450,
                    temperature=0.4,
                    openai_api_key="test-key",
                    openai_reasoning_effort="medium",
                )
            )
            result = await provider.generate(
                system_prompt="system prompt",
                user_prompt="user prompt",
                max_tokens=123,
                temperature=0.2,
            )

        self.assertEqual(result, "MESSAGE:: hi\nACTION:: WAIT")
        create.assert_awaited_once()
        kwargs = create.await_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-5.4")
        self.assertEqual(kwargs["max_completion_tokens"], 123)
        self.assertNotIn("temperature", kwargs)
        self.assertEqual(kwargs["reasoning_effort"], "medium")
        self.assertNotIn("max_tokens", kwargs)

    async def test_generate_omits_reasoning_effort_for_non_gpt5_openai_models(self):
        fake_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="MESSAGE:: hi\nACTION:: WAIT"))]
        )
        create = AsyncMock(return_value=fake_response)
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )

        with patch("config.llms.providers.AsyncOpenAI", return_value=fake_client):
            provider = OpenAIProvider(
                LLMSettings(
                    provider="openai",
                    model="gpt-custom-benchmark",
                    max_tokens=450,
                    temperature=0.4,
                    openai_api_key="test-key",
                    openai_reasoning_effort="medium",
                )
            )
            await provider.generate(
                system_prompt="system prompt",
                user_prompt="user prompt",
                max_tokens=123,
                temperature=0.2,
            )

        kwargs = create.await_args.kwargs
        self.assertNotIn("reasoning_effort", kwargs)


class ProviderConfigurationTests(unittest.TestCase):
    def test_build_settings_uses_repo_default_openai_reasoning_effort(self):
        settings = build_settings(provider="openai", model="gpt-5.4")

        self.assertEqual(settings.openai_reasoning_effort, "low")

    def test_build_settings_uses_repo_default_gemini_thinking_level(self):
        settings = build_settings(provider="gemini", model="gemini-3-flash-preview")

        self.assertEqual(settings.gemini_thinking_level, "low")

    def test_create_provider_requires_openai_api_key(self):
        with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
            create_provider(
                LLMSettings(
                    provider="openai",
                    model="gpt-5.4",
                    max_tokens=450,
                    temperature=0.4,
                    openai_api_key="",
                )
            )

    def test_create_provider_requires_anthropic_api_key(self):
        with self.assertRaisesRegex(ValueError, "ANTHROPIC_API_KEY"):
            create_provider(
                LLMSettings(
                    provider="anthropic",
                    model="claude-3-5-sonnet-latest",
                    max_tokens=450,
                    temperature=0.4,
                    anthropic_api_key="",
                )
            )

    def test_create_provider_requires_gemini_api_key(self):
        with self.assertRaisesRegex(ValueError, "GEMINI_API_KEY"):
            create_provider(
                LLMSettings(
                    provider="gemini",
                    model="gemini-3-flash-preview",
                    max_tokens=450,
                    temperature=0.4,
                    gemini_api_key="",
                )
            )

    def test_create_provider_rejects_local_default_model_for_openai(self):
        with self.assertRaisesRegex(ValueError, "LLM_MODEL=.*gpt-5.4"):
            create_provider(
                LLMSettings(
                    provider="openai",
                    model="llama3.2:1b",
                    max_tokens=450,
                    temperature=0.4,
                    openai_api_key="test-key",
                )
            )

    def test_create_provider_requires_anthropic_model(self):
        with self.assertRaisesRegex(ValueError, "LLM_MODEL=.*claude-3-5-sonnet-latest"):
            create_provider(
                LLMSettings(
                    provider="anthropic",
                    model="",
                    max_tokens=450,
                    temperature=0.4,
                    anthropic_api_key="test-key",
                )
            )

    def test_create_provider_requires_gemini_model(self):
        with self.assertRaisesRegex(ValueError, "LLM_MODEL=.*gemini-3-flash-preview"):
            create_provider(
                LLMSettings(
                    provider="gemini",
                    model="",
                    max_tokens=450,
                    temperature=0.4,
                    gemini_api_key="test-key",
                )
            )

    def test_create_provider_requires_ollama_model(self):
        with self.assertRaisesRegex(ValueError, "LLM_PROVIDER=ollama requires LLM_MODEL"):
            create_provider(
                LLMSettings(
                    provider="ollama",
                    model="",
                    max_tokens=450,
                    temperature=0.4,
                )
            )


class GeminiProviderTests(unittest.TestCase):
    def test_generate_sync_includes_thinking_level_for_gemini3_models(self):
        request_payload = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    {
                        "candidates": [
                            {
                                "content": {
                                    "parts": [{"text": "MESSAGE:: hi\nACTION:: WAIT"}]
                                }
                            }
                        ]
                    }
                ).encode("utf-8")

        def fake_urlopen(req, timeout=90):
            del timeout
            request_payload["body"] = json.loads(req.data.decode("utf-8"))
            return FakeResponse()

        provider = GeminiProvider(
            LLMSettings(
                provider="gemini",
                model="gemini-3-flash-preview",
                max_tokens=450,
                temperature=0.4,
                gemini_api_key="test-key",
                gemini_thinking_level="low",
            )
        )

        with patch("config.llms.providers.request.urlopen", side_effect=fake_urlopen):
            result = provider._generate_sync(
                system_prompt="system prompt",
                user_prompt="user prompt",
                max_tokens=200,
                temperature=0.2,
            )

        self.assertEqual(result, "MESSAGE:: hi\nACTION:: WAIT")
        generation_config = request_payload["body"]["generationConfig"]
        self.assertEqual(generation_config["maxOutputTokens"], 200)
        self.assertEqual(generation_config["temperature"], 0.2)
        self.assertEqual(
            generation_config["thinkingConfig"]["thinkingLevel"],
            "low",
        )

    def test_generate_sync_omits_thinking_level_for_non_gemini3_models(self):
        request_payload = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    {
                        "candidates": [
                            {
                                "content": {
                                    "parts": [{"text": "MESSAGE:: hi\nACTION:: WAIT"}]
                                }
                            }
                        ]
                    }
                ).encode("utf-8")

        def fake_urlopen(req, timeout=90):
            del timeout
            request_payload["body"] = json.loads(req.data.decode("utf-8"))
            return FakeResponse()

        provider = GeminiProvider(
            LLMSettings(
                provider="gemini",
                model="gemini-2.0-flash",
                max_tokens=450,
                temperature=0.4,
                gemini_api_key="test-key",
                gemini_thinking_level="low",
            )
        )

        with patch("config.llms.providers.request.urlopen", side_effect=fake_urlopen):
            provider._generate_sync(
                system_prompt="system prompt",
                user_prompt="user prompt",
                max_tokens=200,
                temperature=0.2,
            )

        generation_config = request_payload["body"]["generationConfig"]
        self.assertNotIn("thinkingConfig", generation_config)


class OllamaProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_adds_openai_hint_when_ollama_connection_fails(self):
        request = httpx.Request("POST", "http://localhost:11434/v1/chat/completions")
        create = AsyncMock(
            side_effect=APIConnectionError(message="Connection error.", request=request)
        )
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )

        with patch("config.llms.providers.AsyncOpenAI", return_value=fake_client):
            provider = OllamaProvider(
                LLMSettings(
                    provider="ollama",
                    model="llama3.2:1b",
                    max_tokens=450,
                    temperature=0.4,
                    base_url="http://localhost:11434/v1",
                    openai_api_key="test-key",
                )
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "defaults to Ollama.*LLM_PROVIDER=openai.*LLM_MODEL=gpt-5.4",
            ):
                await provider.generate(
                    system_prompt="system prompt",
                    user_prompt="user prompt",
                    max_tokens=123,
                    temperature=0.2,
                )


if __name__ == "__main__":
    unittest.main()
