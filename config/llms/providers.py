"""
providers.py — Provider-agnostic LLM setup and generation logic.
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib import error, request

import anthropic
from openai import APIConnectionError, AsyncOpenAI

from config import config as cfg
from config.llms.selection import LOCAL_MODEL_PRESETS

OPENAI_EXAMPLE_MODEL = "gpt-5.4"
ANTHROPIC_EXAMPLE_MODEL = "claude-3-5-sonnet-latest"
GEMINI_EXAMPLE_MODEL = "gemini-3-flash-preview"
LOCAL_DEFAULT_MODEL = "llama3.2:1b"


@dataclass(slots=True)
class LLMSettings:
    provider: str
    model: str
    max_tokens: int
    temperature: float
    base_url: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    ollama_api_key: str = "ollama"
    openai_reasoning_effort: str = "medium"
    gemini_thinking_level: str = "low"


class LLMProvider(ABC):
    """Abstract provider interface used by Agent.decide()."""

    def __init__(self, settings: LLMSettings):
        self.settings = settings

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        raise NotImplementedError


def _validate_settings(settings: LLMSettings) -> None:
    provider = settings.provider

    if provider == "openai":
        _validate_hosted_settings(
            settings=settings,
            api_key=settings.openai_api_key,
            api_key_name="OPENAI_API_KEY",
            example_model=OPENAI_EXAMPLE_MODEL,
            provider_label="OpenAI",
        )
        return

    if provider == "anthropic":
        _validate_hosted_settings(
            settings=settings,
            api_key=settings.anthropic_api_key,
            api_key_name="ANTHROPIC_API_KEY",
            example_model=ANTHROPIC_EXAMPLE_MODEL,
            provider_label="Anthropic",
        )
        return

    if provider == "gemini":
        _validate_hosted_settings(
            settings=settings,
            api_key=settings.gemini_api_key,
            api_key_name="GEMINI_API_KEY",
            example_model=GEMINI_EXAMPLE_MODEL,
            provider_label="Gemini",
        )
        return

    if provider == "ollama" and not settings.model:
        raise ValueError(
            "LLM_PROVIDER=ollama requires LLM_MODEL to be set to a local Ollama "
            f"model id. Example: LLM_MODEL={LOCAL_DEFAULT_MODEL}."
        )


def _validate_hosted_settings(
    *,
    settings: LLMSettings,
    api_key: str,
    api_key_name: str,
    example_model: str,
    provider_label: str,
) -> None:
    if not api_key:
        raise ValueError(f"LLM_PROVIDER={settings.provider} requires {api_key_name} to be set.")

    if not settings.model:
        raise ValueError(
            f"LLM_PROVIDER={settings.provider} requires LLM_MODEL to be set to a valid "
            f"{provider_label} model id. Example: LLM_MODEL={example_model}."
        )

    if settings.model in LOCAL_MODEL_PRESETS:
        raise ValueError(
            f"LLM_PROVIDER={settings.provider} cannot use local Ollama model "
            f"{settings.model!r}. Choose a hosted {provider_label} model id such as "
            f"LLM_MODEL={example_model}."
        )


def _ollama_connection_hint(settings: LLMSettings) -> str:
    base_url = settings.base_url or cfg.OLLAMA_BASE_URL
    return (
        f"Failed to reach Ollama at {base_url}. This project defaults to Ollama "
        "when LLM_PROVIDER is unset. OPENAI_API_KEY is set, but OpenAI is not "
        "active. To run against OpenAI, use "
        f"`python run_simulation.py --openai --model {OPENAI_EXAMPLE_MODEL}` "
        "or set LLM_PROVIDER=openai and "
        f"LLM_MODEL={OPENAI_EXAMPLE_MODEL} before running python run_simulation.py."
    )


class OpenAIProvider(LLMProvider):
    def __init__(self, settings: LLMSettings):
        super().__init__(settings)
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.base_url or cfg.OPENAI_BASE_URL,
        )

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        request_kwargs = {
            "model": self.settings.model,
            "max_completion_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if _supports_openai_temperature(self.settings.model):
            request_kwargs["temperature"] = temperature
        if _uses_openai_reasoning(self.settings.model) and self.settings.openai_reasoning_effort:
            request_kwargs["reasoning_effort"] = self.settings.openai_reasoning_effort

        response = await self.client.chat.completions.create(
            **request_kwargs,
        )
        return response.choices[0].message.content or ""


class AnthropicProvider(LLMProvider):
    def __init__(self, settings: LLMSettings):
        super().__init__(settings)
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        response = await self.client.messages.create(
            model=self.settings.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text


class GeminiProvider(LLMProvider):
    def __init__(self, settings: LLMSettings):
        super().__init__(settings)
        self.api_key = settings.gemini_api_key
        self.model = settings.model

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        return await asyncio.to_thread(
            self._generate_sync,
            system_prompt,
            user_prompt,
            max_tokens,
            temperature,
        )

    def _generate_sync(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if _uses_gemini_thinking_level(self.model) and self.settings.gemini_thinking_level:
            payload["generationConfig"]["thinkingConfig"] = {
                "thinkingLevel": self.settings.gemini_thinking_level
            }
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=90) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini request failed: {details}") from exc

        candidates = body.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "\n".join(part.get("text", "") for part in parts).strip()


class OllamaProvider(LLMProvider):
    """
    Local-first provider using an OpenAI-compatible endpoint such as Ollama.
    """

    def __init__(self, settings: LLMSettings):
        super().__init__(settings)
        self.client = AsyncOpenAI(
            api_key=settings.ollama_api_key or "ollama",
            base_url=settings.base_url or cfg.OLLAMA_BASE_URL,
        )

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.settings.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except APIConnectionError as exc:
            if self.settings.openai_api_key:
                raise RuntimeError(_ollama_connection_hint(self.settings)) from exc
            raise
        return response.choices[0].message.content or ""


def _uses_openai_reasoning(model: str) -> bool:
    return model.strip().lower().startswith("gpt-5")


def _supports_openai_temperature(model: str) -> bool:
    # GPT-5 chat completions currently reject non-default temperature values,
    # so omit the field entirely and let the API apply its default behavior.
    return not _uses_openai_reasoning(model)


def _uses_gemini_thinking_level(model: str) -> bool:
    return model.strip().lower().startswith("gemini-3")


def build_settings(
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> LLMSettings:
    provider = (cfg.LLM_PROVIDER if provider is None else provider).strip().lower()
    if provider == "claude":
        provider = "anthropic"

    resolved_model = (cfg.LLM_MODEL if model is None else model).strip()
    default_base_url = cfg.LLM_BASE_URL if base_url is None else base_url
    if not default_base_url:
        if provider == "openai":
            default_base_url = cfg.OPENAI_BASE_URL
        elif provider == "ollama":
            default_base_url = cfg.OLLAMA_BASE_URL

    return LLMSettings(
        provider=provider,
        model=resolved_model,
        max_tokens=cfg.MAX_TOKENS,
        temperature=cfg.TEMPERATURE,
        base_url=default_base_url,
        openai_api_key=cfg.OPENAI_API_KEY,
        anthropic_api_key=cfg.ANTHROPIC_API_KEY,
        gemini_api_key=cfg.GEMINI_API_KEY,
        ollama_api_key=cfg.OLLAMA_API_KEY,
        openai_reasoning_effort=cfg.OPENAI_REASONING_EFFORT,
        gemini_thinking_level=cfg.GEMINI_THINKING_LEVEL,
    )


def create_provider(settings: LLMSettings | None = None) -> LLMProvider:
    settings = settings or build_settings()
    _validate_settings(settings)
    provider = settings.provider

    if provider == "openai":
        return OpenAIProvider(settings)
    if provider == "anthropic":
        return AnthropicProvider(settings)
    if provider == "gemini":
        return GeminiProvider(settings)
    if provider == "ollama":
        return OllamaProvider(settings)

    raise ValueError(
        f"Unsupported LLM provider '{provider}'. "
        "Expected one of: openai, anthropic, gemini, ollama."
    )
