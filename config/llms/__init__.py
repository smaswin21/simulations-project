"""
Provider-agnostic LLM client factory.
"""

from config.llms.providers import LLMProvider, LLMSettings, build_settings, create_provider
from config.llms.selection import (
    HOSTED_MODEL_PRESETS,
    LOCAL_MODEL_PRESETS,
    ResolvedLLMChoice,
    add_selection_args,
    resolve_model_selection,
)

__all__ = [
    "HOSTED_MODEL_PRESETS",
    "LOCAL_MODEL_PRESETS",
    "LLMProvider",
    "LLMSettings",
    "ResolvedLLMChoice",
    "add_selection_args",
    "build_settings",
    "create_provider",
    "resolve_model_selection",
]
