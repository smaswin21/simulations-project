# Thesis Project 

A thesis project on commons governance with a local-first 10-agent simulation: 7 Herders, 2 Regulators, and 1 Scout. The project compares how memory, role asymmetry, and model choice affect coordination, sustainability, and inequality across repeated rounds.

 Demo | Demo2 |
| --- | --- |
| <img src="assets/readme-media/B1-loop.gif" alt="B1 looping replay preview" width="100%"> | <img src="assets/readme-media/V2-loop.gif" alt="V2 looping replay preview" width="100%"> |

## 01. Project

- Scenario: a shared pasture with asymmetric roles and limited ecological information
- Providers: [`Ollama`](https://ollama.com/), [`OpenAI`](https://platform.openai.com/docs/overview), [`Anthropic`](https://docs.anthropic.com/), [`Gemini`](https://ai.google.dev/gemini-api/docs)
- Storage: [`MongoDB`](https://www.mongodb.com/) is required for profiles, run logs, replay data, and memory graphs
- Outputs: simulation logs, replayable runs, memory plots, ablation plots, and post-run network graphs

Core runtime flow:

1. Load scenario and agent profiles
2. Select provider and model
3. Run round-by-round agent decisions
4. Persist logs and memory state to MongoDB
5. Generate replay, plots, and graph analysis from stored runs

## 02. Setup

Run all commands from the repository root.

### 1. Clone and enter the repo

```bash
git clone https://github.com/smaswin21/simulations-project.git
cd simulations-project
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

Recommended runtime: [`Python`](https://www.python.org/) 3.10+

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create your local env file

```bash
cp .env.example .env
```

### 5. Configure MongoDB

Use either local [`MongoDB`](https://www.mongodb.com/):

```bash
MONGODB_URI=mongodb://localhost:27017
```

Or [`MongoDB Atlas`](https://www.mongodb.com/products/platform/atlas-database):

```bash
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster-url>/?retryWrites=true&w=majority
```

The code writes to database `thesis-architecture` and uses:

- `profiles`: stores the seeded agent persona records and Big Five profile data.
  Appears after: `python -c "from config.db import seed_from_json; print(seed_from_json('EDA/cohort_personas.json'))"`
- `logs`: stores one document per simulation run with config, agent assignments, round-by-round events, replay data, and final summary.
  Appears after: `python run_simulation.py` or `python -m scripts.run_ablation ...`
- `agent_memories`: stores each agent's persisted episodic memory graph for a simulation run.
  Appears after: `python run_simulation.py` or `python -m scripts.run_ablation ...`

### 6. Seed the required profiles

```bash
python -c "from config.db import seed_from_json; print(seed_from_json('EDA/cohort_personas.json'))"
```

### 7. Optional: start Ollama

```bash
ollama serve
ollama pull qwen3.5:9b
```

Official Ollama docs: [ollama.com](https://ollama.com/)

## 03. Environment and Providers

Minimum required variables:

```bash
MONGODB_URI=
LLM_PROVIDER=ollama
LLM_MODEL=qwen3.5:9b
```

Provider-specific keys:

- OpenAI: `OPENAI_API_KEY`, optional `OPENAI_BASE_URL`, `OPENAI_REASONING_EFFORT` via [OpenAI docs](https://platform.openai.com/docs/overview)
- Anthropic: `ANTHROPIC_API_KEY` via [Anthropic docs](https://docs.anthropic.com/)
- Gemini: `GEMINI_API_KEY`, optional `GEMINI_THINKING_LEVEL` via [Gemini API docs](https://ai.google.dev/gemini-api/docs)
- Ollama: optional `OLLAMA_API_BASE`, `OLLAMA_BASE_URL`, `OLLAMA_API_KEY` via [Ollama docs](https://ollama.com/)

Useful generation defaults:

```bash
LLM_TEMPERATURE=0.4
LLM_MAX_TOKENS=450
MAX_CONCURRENT_AGENTS=5
```

The full env template lives in `.env.example`.

## 04. Run the Simulation

Baseline run:

```bash
python run_simulation.py
```

Fixed rounds and seed:

```bash
python run_simulation.py --rounds 10 --seed 42
```

Provider-specific runs:

```bash
python run_simulation.py --ollama --model qwen3.5:9b --rounds 10 --seed 42
python run_simulation.py --openai --model gpt-5.4 --rounds 10 --seed 42
python run_simulation.py --anthropic --model claude-3-5-sonnet-latest --rounds 10 --seed 42
python run_simulation.py --gemini --model gemini-3-flash-preview --rounds 10 --seed 42
```

Profile source options:

```bash
python run_simulation.py --cohort-source mongo
python run_simulation.py --cohort-file EDA/similar_traits/cohort_similar_openness.json
```

Replay a stored run:

```bash
python -m ui.pygame_app --simulation-id <SIMULATION_ID>
python -m ui.pygame_app --simulation-id <SIMULATION_ID> --round-duration-ms 1000 --width 1200 --height 800
```

Replay display uses [`Pygame`](https://www.pygame.org/docs/).

Example simulation ids:

```bash
python -m ui.pygame_app --simulation-id 69c7cc092a96982c1be09c83
python -m ui.pygame_app --simulation-id 69c7d50e166f08559d20612e
```

These ids are only examples. Your simulation ids will be different based on the logs collected in your own runs.

## 05. Graphs and Analysis

RQ1: memory ablation study:

```bash
python -m scripts.run_ablation --runs 3 --rounds 10 --tag diverse_traits --cohort-source mongo
python -m scripts.plot_ablation
```

RQ1 outputs:

- `results/ablation_A_diverse_traits.jsonl`: memory OFF runs
- `results/ablation_B_diverse_traits.jsonl`: memory ON runs
- `results/ablation_plots.png`: ablation plot for commons stock and gini over time

Plot generation uses [`Matplotlib`](https://matplotlib.org/).

Memory plot:

- `python run_simulation.py` auto-saves a memory plot when the simulation has a stored MongoDB id
- output directory: `memory_plots/`

Graph analysis from a stored simulation:

```bash
python -m results.graph_analysis --list
python -m results.graph_analysis <simulation_id>
```

Example graph analysis commands:

```bash
python -m results.graph_analysis 69c7cc092a96982c1be09c83
python -m results.graph_analysis 69c7d50e166f08559d20612e
```

These ids will vary per run because they come from the simulation documents stored in MongoDB logs.

Graph outputs:

- `results/analysis/agent-interaction-network-<simulation_id>.png`

Graph rendering uses [`NetworkX`](https://networkx.org/) with [`Matplotlib`](https://matplotlib.org/).

RQ2: similar vs diverse personality cohorts:

This is a long-running simulation workflow because it executes multiple ablation jobs across seven experimental conditions.

```bash
python -m scripts.run_ablation --runs 3 --rounds 10 --tag diverse_traits --cohort-source mongo
python -m scripts.run_ablation --runs 3 --rounds 10 --tag similar_agreeableness --cohort-file EDA/similar_traits/cohort_similar_agreeableness.json
python -m scripts.run_ablation --runs 3 --rounds 10 --tag similar_conscientiousness --cohort-file EDA/similar_traits/cohort_similar_conscientiousness.json
python -m scripts.run_ablation --runs 3 --rounds 10 --tag similar_extraversion --cohort-file EDA/similar_traits/cohort_similar_extraversion.json
python -m scripts.run_ablation --runs 3 --rounds 10 --tag similar_neuroticism --cohort-file EDA/similar_traits/cohort_similar_neuroticism.json
python -m scripts.run_ablation --runs 3 --rounds 10 --tag similar_openness --cohort-file EDA/similar_traits/cohort_similar_openness.json
```

This produces the seven conditions used for RQ2:

- `ablation_B_diverse_traits.jsonl`: diverse cohort with memory ON
- `ablation_B_similar_agreeableness.jsonl`: agreeableness cohort with memory ON
- `ablation_B_similar_conscientiousness.jsonl`: conscientiousness cohort with memory ON
- `ablation_B_similar_extraversion.jsonl`: extraversion cohort with memory ON
- `ablation_B_similar_neuroticism.jsonl`: neuroticism cohort with memory ON
- `ablation_B_similar_openness.jsonl`: openness cohort with memory ON
- `ablation_A_diverse_traits.jsonl`: memory OFF baseline

All RQ2 raw result files are written to `results/`.

RQ2 statistical study:

```bash
python -m scripts.rq2_statistics
```

Statistical outputs are written to `results/cohort-analysis/`:

- `rq2-descriptive-stats.csv`: means and sample standard deviations for Commons Stock and Gini
- `rq2-anova-summary.csv`: one-way ANOVA summary for the seven conditions
- `rq2-tukey-hsd.csv`: full Tukey HSD pairwise comparisons for both target metrics
- `rq2-statistics-report.txt`: short thesis-style text summary

Optional pairwise cohort plot:

```bash
python -m scripts.analyze_cohorts --tags diverse_traits similar_agreeableness similar_conscientiousness similar_extraversion similar_neuroticism similar_openness --baseline-tag diverse_traits --pair-tag similar_extraversion --condition B
```

## 06. Outputs

- MongoDB `logs`: run config, round history, replay state, final summary
- MongoDB `agent_memories`: persisted memory graphs
- `results/ablation_*.jsonl`: raw ablation outputs
- `results/ablation_plots.png`: ablation chart
- `results/analysis/`: post-run network and flow graphs
- `results/cohort-analysis/`: RQ2 descriptive statistics, ANOVA, Tukey HSD, and pairwise plots
- `memory_plots/`: single-run memory plots

Each run prints a simulation id such as:

```text
Simulation ID: 507f1f77bcf86cd799439011
```

Use that id for replay and graph analysis. The exact id will be different for every stored run, depending on the logs created in your database.

## 07. Troubleshooting

### `MONGODB_URI not found in .env`

Set `MONGODB_URI` before running anything that loads profiles or writes logs.

### Missing provider API key

Match the selected `LLM_PROVIDER` with its required key:

- `openai` -> `OPENAI_API_KEY`
- `anthropic` -> `ANTHROPIC_API_KEY`
- `gemini` -> `GEMINI_API_KEY`

### Ollama is not reachable

- start Ollama
- confirm `OLLAMA_API_BASE` or `OLLAMA_BASE_URL`
- make sure the model is pulled locally

### Import or test path issues

Run from the repo root. If needed:

```bash
PYTHONPATH=. pytest -q
```

### Replay or graph analysis cannot find a run

Use the exact `Simulation ID` printed by `run_simulation.py`, and make sure the run exists in MongoDB with stored rounds.
