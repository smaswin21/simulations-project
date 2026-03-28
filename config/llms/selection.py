"""
selection.py — Resolve provider/model choices for local and hosted runs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from urllib import error, request

import config.config as cfg

PROVIDER_ALIASES = {
    "claude": "anthropic",
}
SUPPORTED_PROVIDERS = ("ollama", "openai", "anthropic", "gemini")
PROVIDER_LABELS = {
    "ollama": "Ollama (local)",
    "openai": "OpenAI",
    "anthropic": "Anthropic (Claude)",
    "gemini": "Gemini",
}
LOCAL_MODEL_PRESETS = [
    "qwen3.5:9b",
    "llama3.2:1b",
]
HOSTED_MODEL_PRESETS = {
    "openai": [
        "gpt-5.4",
        "gpt-5-nano",
    ],
    "anthropic": [
        "claude-3-5-sonnet-latest",
        "claude-3-5-haiku-latest",
    ],
    "gemini": [
        "gemini-3-flash-preview",
        "gemini-2.0-flash",
    ],
}
OLLAMA_DISCOVERY_TIMEOUT_SECONDS = 0.75


@dataclass(slots=True)
class ResolvedLLMChoice:
    provider: str
    model: str


def add_selection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="LLM provider to use: ollama, openai, anthropic/claude, or gemini",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model id to use with the selected provider",
    )
    parser.add_argument(
        "--ollama",
        action="store_true",
        help="Shortcut for --provider ollama",
    )
    parser.add_argument(
        "--openai",
        action="store_true",
        help="Shortcut for --provider openai",
    )
    parser.add_argument(
        "--anthropic",
        action="store_true",
        help="Shortcut for --provider anthropic",
    )
    parser.add_argument(
        "--claude",
        action="store_true",
        help="Shortcut for --provider anthropic",
    )
    parser.add_argument(
        "--gemini",
        action="store_true",
        help="Shortcut for --provider gemini",
    )


def canonicalize_provider(provider: str | None) -> str | None:
    if provider is None:
        return None
    normalized = provider.strip().lower()
    if not normalized:
        return None
    normalized = PROVIDER_ALIASES.get(normalized, normalized)
    if normalized not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unsupported provider '{provider}'. "
            "Expected one of: ollama, openai, anthropic/claude, gemini."
        )
    return normalized


def resolve_model_selection(
    args,
    *,
    input_func=input,
    is_interactive: bool | None = None,
) -> ResolvedLLMChoice:
    interactive = (
        is_interactive
        if is_interactive is not None
        else sys.stdin.isatty() and sys.stdout.isatty()
    )

    explicit_env_provider = _explicit_env_provider()
    explicit_env_model = _explicit_env_model()

    provider = _resolve_provider_from_args(args)
    if provider is None:
        if interactive:
            provider = _prompt_for_provider(
                default_provider=explicit_env_provider or cfg.LLM_PROVIDER,
                input_func=input_func,
            )
        else:
            provider = explicit_env_provider or cfg.LLM_PROVIDER

    model = _normalize_model(getattr(args, "model", None))
    if model is None:
        default_env_model = (
            explicit_env_model
            if explicit_env_model and explicit_env_provider == provider
            else None
        )
        if interactive:
            model = _prompt_for_model(
                provider=provider,
                default_model=default_env_model,
                input_func=input_func,
            )
        else:
            model = default_env_model or _default_model_for_provider(provider)

    return ResolvedLLMChoice(provider=provider, model=model)


def discover_ollama_models(timeout_seconds: float = OLLAMA_DISCOVERY_TIMEOUT_SECONDS) -> list[str]:
    endpoint = _ollama_tags_endpoint()
    req = request.Request(endpoint, method="GET")
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, TimeoutError, OSError, ValueError):
        return []

    names = []
    for model in payload.get("models", []):
        name = str(model.get("name", "")).strip()
        if name:
            names.append(name)
    return _dedupe(names)


def ollama_model_options() -> list[str]:
    return _dedupe(LOCAL_MODEL_PRESETS + discover_ollama_models())


def _resolve_provider_from_args(args) -> str | None:
    provider_choices: list[tuple[str, str]] = []

    provider_arg = canonicalize_provider(getattr(args, "provider", None))
    if provider_arg is not None:
        provider_choices.append(("--provider", provider_arg))

    for attr_name, provider in (
        ("ollama", "ollama"),
        ("openai", "openai"),
        ("anthropic", "anthropic"),
        ("claude", "anthropic"),
        ("gemini", "gemini"),
    ):
        if getattr(args, attr_name, False):
            provider_choices.append((f"--{attr_name}", provider))

    if not provider_choices:
        return None

    unique_choices = {provider for _, provider in provider_choices}
    if len(unique_choices) > 1:
        flags = ", ".join(source for source, _ in provider_choices)
        raise ValueError(f"Conflicting provider flags: {flags}")

    return provider_choices[0][1]


def _prompt_for_provider(default_provider: str, *, input_func=input) -> str:
    providers = list(SUPPORTED_PROVIDERS)
    default_provider = canonicalize_provider(default_provider) or "ollama"
    default_index = providers.index(default_provider) + 1

    print("\nSelect an LLM provider:")
    for idx, provider in enumerate(providers, start=1):
        suffix = " [default]" if provider == default_provider else ""
        print(f"  {idx}. {PROVIDER_LABELS[provider]}{suffix}")

    while True:
        raw = input_func(f"Provider [{default_index}]: ").strip()
        if not raw:
            return default_provider
        if raw.isdigit():
            index = int(raw)
            if 1 <= index <= len(providers):
                return providers[index - 1]
        try:
            provider = canonicalize_provider(raw)
        except ValueError:
            provider = None
        if provider is not None:
            return provider
        print("Please choose a provider number or name.")


def _prompt_for_model(
    provider: str,
    *,
    default_model: str | None,
    input_func=input,
) -> str:
    options = _model_options_for_provider(provider)
    prompt_default = default_model or _default_model_for_provider(provider)
    custom_index = len(options) + 1

    print(f"\nSelect a model for {PROVIDER_LABELS[provider]}:")
    for idx, model in enumerate(options, start=1):
        suffix = " [default]" if model == prompt_default else ""
        print(f"  {idx}. {model}{suffix}")
    print(f"  {custom_index}. Enter a custom model id")

    while True:
        raw = input_func(f"Model [{prompt_default}]: ").strip()
        if not raw:
            return prompt_default
        if raw.isdigit():
            index = int(raw)
            if 1 <= index <= len(options):
                return options[index - 1]
            if index == custom_index:
                custom_model = _prompt_for_custom_model(input_func=input_func)
                if custom_model:
                    return custom_model
            print("Please choose a listed model number or enter a model id.")
            continue
        if raw.lower() == "custom":
            custom_model = _prompt_for_custom_model(input_func=input_func)
            if custom_model:
                return custom_model
        if raw in options:
            return raw
        return raw


def _prompt_for_custom_model(*, input_func=input) -> str:
    while True:
        raw = input_func("Custom model id: ").strip()
        if raw:
            return raw
        print("Please enter a non-empty model id.")


def _model_options_for_provider(provider: str) -> list[str]:
    if provider == "ollama":
        return ollama_model_options()
    return list(HOSTED_MODEL_PRESETS.get(provider, []))


def _default_model_for_provider(provider: str) -> str:
    if provider == "ollama":
        explicit_env_model = _explicit_env_model()
        explicit_env_provider = _explicit_env_provider()
        if explicit_env_model and explicit_env_provider == "ollama":
            return explicit_env_model
        if cfg.LLM_MODEL and canonicalize_provider(cfg.LLM_PROVIDER) == "ollama":
            return cfg.LLM_MODEL
        return LOCAL_MODEL_PRESETS[0]

    presets = HOSTED_MODEL_PRESETS.get(provider, [])
    if presets:
        return presets[0]

    raise ValueError(f"No model presets configured for provider '{provider}'.")


def _explicit_env_provider() -> str | None:
    return canonicalize_provider(os.getenv("LLM_PROVIDER"))


def _explicit_env_model() -> str | None:
    return _normalize_model(os.getenv("LLM_MODEL"))


def _normalize_model(model: str | None) -> str | None:
    if model is None:
        return None
    normalized = model.strip()
    return normalized or None


def _ollama_tags_endpoint() -> str:
    base_url = (cfg.OLLAMA_BASE_URL or cfg.OLLAMA_API_BASE).rstrip("/")
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]
    return f"{base_url}/api/tags"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
