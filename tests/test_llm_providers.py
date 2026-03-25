import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from openai import APIConnectionError

from config.llms.providers import (
    LLMSettings,
    OllamaProvider,
    OpenAIProvider,
    create_provider,
)


class OpenAIProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_uses_max_completion_tokens_for_openai(self):
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
                    model="gpt-5-nano",
                    max_tokens=450,
                    temperature=0.4,
                    openai_api_key="test-key",
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
        self.assertEqual(kwargs["model"], "gpt-5-nano")
        self.assertEqual(kwargs["max_completion_tokens"], 123)
        self.assertEqual(kwargs["temperature"], 0.2)
        self.assertNotIn("max_tokens", kwargs)


class ProviderConfigurationTests(unittest.TestCase):
    def test_create_provider_requires_openai_api_key(self):
        with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
            create_provider(
                LLMSettings(
                    provider="openai",
                    model="gpt-5.1",
                    max_tokens=450,
                    temperature=0.4,
                    openai_api_key="",
                )
            )

    def test_create_provider_rejects_local_default_model_for_openai(self):
        with self.assertRaisesRegex(ValueError, "LLM_MODEL=.*gpt-5.1"):
            create_provider(
                LLMSettings(
                    provider="openai",
                    model="llama3.2:1b",
                    max_tokens=450,
                    temperature=0.4,
                    openai_api_key="test-key",
                )
            )


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
                "defaults to Ollama.*LLM_PROVIDER=openai.*LLM_MODEL=gpt-5.1",
            ):
                await provider.generate(
                    system_prompt="system prompt",
                    user_prompt="user prompt",
                    max_tokens=123,
                    temperature=0.2,
                )


if __name__ == "__main__":
    unittest.main()
