# Heterogeneous MASTOC Simulation

This project runs a local-first multi-agent commons simulation with 10 asymmetric agents:
- 7 `Herders`
- 2 `Regulators`
- 1 `Scout`

## Runtime Flow
1. The environment generates role-aware perception.
2. Each agent produces a private `REFLECTION::`.
3. Episodic belief memory retrieves relevant beliefs using reflection-aligned scoring.
4. Each agent produces a public `MESSAGE::` and one discrete `ACTION::`.
5. The environment resolves movement, grazing, sanctions, reports, and council messages.
6. Beliefs about `resource_health` and `reputation` are extracted into memory.
7. Metrics track stock, Gini, and related coordination/accountability signals.

## Memory Model
- Episode nodes store round-local perception plus outcomes.
- Fact nodes store beliefs with categories such as `resource_health` and `reputation`.
- Contradiction edges flag conflicting beliefs.
- Memory OFF disables retrieval only; storage and logging remain available for analysis.

## Local-First LLM Architecture
The provider layer lives under [config/llms/providers.py](/Users/sm_aswin21/Desktop/thesis-code/simulations-project/config/llms/providers.py) and exposes one async interface:
- `OpenAIProvider`
- `AnthropicProvider`
- `GeminiProvider`
- `OllamaProvider`

`OllamaProvider` is the local default and is intended for Ollama-compatible endpoints.
If `LLM_PROVIDER` is unset, `python run_simulation.py` will try `http://localhost:11434/v1`.

## Model Guidance
- `llama3.2:1b` is acceptable for smoke tests and parser/flow validation.
- Use a stronger local model such as `Mistral Small 3` or `Qwen3` for thesis-grade runs.
- Hosted providers can be enabled by changing config only; the simulation code stays provider-agnostic.

## Hosted API Keys
To use hosted providers, keep the API keys in `.env`:
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`

You can now choose provider and model at launch time instead of editing `LLM_PROVIDER` and `LLM_MODEL` for each run.
OpenAI GPT-5 runs use `reasoning_effort=medium` by default in this repo.
Gemini 3 runs use `GEMINI_THINKING_LEVEL=low` by default in this repo.

## Entrypoints
- `python run_simulation.py`
- `python run_simulation.py --rounds 10 --seed 42`
- `python run_simulation.py --ollama --model qwen3.5:9b --rounds 10 --seed 42`
- `python run_simulation.py --openai --model gpt-5.4 --rounds 10 --seed 42`
- `python run_simulation.py --anthropic --model claude-3-5-sonnet-latest --rounds 10 --seed 42`
- `python run_simulation.py --gemini --model gemini-3-flash-preview --rounds 10 --seed 42`
- `LLM_MAX_TOKENS=200 python run_simulation.py --gemini --model gemini-3-flash-preview --rounds 15 --seed 42`
- `python -m scripts.run_ablation --runs 3 --rounds 10`
- `python -m scripts.run_ablation --runs 3 --rounds 10 --ollama --model qwen3.5:9b`
- `python -m scripts.plot_ablation`
