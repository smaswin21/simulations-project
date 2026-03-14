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
- `MistralProvider`

`MistralProvider` is the local default and is intended for Ollama-compatible endpoints.

## Model Guidance
- `llama3.2:1b` is acceptable for smoke tests and parser/flow validation.
- Use a stronger local model such as `Mistral Small 3` or `Qwen3` for thesis-grade runs.
- Hosted providers can be enabled by changing config only; the simulation code stays provider-agnostic.

## Entrypoints
- `python run_simulation.py --rounds 10 --seed 42`
- `python -m scripts.run_ablation --runs 3 --rounds 10`
- `python -m scripts.plot_ablation`
