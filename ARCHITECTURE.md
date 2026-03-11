# Architecture: LLM-Based Multi-Agent Simulation

> A complete reverse-engineered architecture document for the persona-grounded,
> memory-augmented multi-agent simulation system.

---

## 1. Architecture Overview

This is a **multi-agent social simulation** where LLM-driven agents — grounded
in psychometric personas from the Twin-2K-500 dataset — navigate a medicine
shortage scenario. Agents perceive their environment, retrieve memories, make
decisions via LLM calls, and reflect on outcomes, producing emergent
cooperative/defective behaviors measured via Gini coefficient and
accountability metrics.

The system is organized into **three layers**:

```
┌─────────────────────────────────┐
│  Layer 1: Persona Grounding     │  agent_flow/persona_generator.py
│  Big Five → natural-language    │  data/agent_profiles.json
│  system prompt per agent        │  config/db.py (MongoDB profiles)
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│  Layer 2: Memory Modules        │  agent_flow/memory/graph.py
│  EpisodicMemoryGraph (NetworkX) │  agent_flow/memory/nodes.py
│  episodes / facts / commitments │  agent_flow/memory/retrieval.py
│  contradiction detection        │  agent_flow/memory/contradiction.py
│  embedding-based retrieval      │  agent_flow/memory/scoring.py
│                                 │  agent_flow/memory/formatting.py
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│  Layer 3: Action-Perception     │  config/orchestrator.py
│  Loop                           │  agent_flow/agent.py
│  Perceive → Retrieve → Decide  │  agent_flow/environment.py
│  → Act → Compare → Reflect     │  agent_flow/action_parser.py
│  (repeat N rounds)              │  agent_flow/fact_extractor.py
└─────────────────────────────────┘
```

**Data flow per agent per round:**

```
Persona ──→ Memory ──→ Action-Perception
  │            │              │
  │  system    │  injection   │  LLM call → action → resolve
  │  prompt    │  block       │  → outcomes → episode → facts
  └────────────┴──────────────┘
```

**Layer 1 (Persona Grounding):** Big Five personality traits, CRT scores, risk
preferences, and dependent status are converted into natural-language system
prompts via `agent_flow/persona_generator.py:generate_persona_prompt()`.

**Layer 2 (Memory Modules):** A per-agent NetworkX directed graph
(`EpisodicMemoryGraph`) stores episodes, extracted facts, and commitments with
temporal ordering (`NEXT`), provenance links (`EXTRACTED_FROM`), and
contradiction edges (`CONTRADICTS`). Retrieval uses 384-dim
sentence-transformer embeddings (`all-MiniLM-L6-v2`) with cosine similarity,
recency decay, importance weighting, and one-hop graph expansion.

**Layer 3 (Action-Perception Loop):** The orchestrator runs N rounds. Each
round: generate perceptions, retrieve memories, call LLMs in parallel, parse
actions, resolve in environment, extract facts, detect contradictions, update
commitment statuses, log, and persist.

---

## 2. Module-Level Dependency Graph

```
run_simulation.py ─────────────────────────────────────────────────
  │                                                                │
  ├── config/config.py ........... all constants & toggles         │
  ├── config/scenario_loader.py .. YAML/JSON/MD loading            │
  ├── config/db.py ............... MongoDB CRUD ──→ [MongoDB]       │
  ├── config/logger.py ........... simulation logging              │
  ├── config/orchestrator.py ..... SIMULATION LOOP                 │
  │     ├── agent_flow/action_parser.py ... parse LLM → action     │
  │     ├── agent_flow/fact_extractor.py .. outcomes → facts        │
  │     ├── agent_flow/environment.py ..... world state             │
  │     └── metrics/collector.py .......... Gini & accountability   │
  │                                                                │
  ├── agent_flow/agent.py ................ agent decision logic     │
  │     └── agent_flow/memory_graph.py ... re-export of EMG        │
  │           └── agent_flow/memory/graph.py                       │
  │                 ├── memory/nodes.py ......... node CRUD         │
  │                 ├── memory/scoring.py ........ importance       │
  │                 ├── memory/retrieval.py ...... embedding search │
  │                 ├── memory/contradiction.py .. detect conflicts │
  │                 └── memory/formatting.py ..... prompt blocks    │
  │                                                                │
  ├── agent_flow/persona_generator.py .... Big Five → prompt       │
  ├── agent_flow/environment.py .......... world graph (NetworkX)  │
  └── agent_flow/embedding.py ........... sentence-transformers    │
                                           └──→ [SentenceTransformer]
External services:
  - Ollama (local LLM, llama3.2:1b) or Anthropic API (Claude)
  - MongoDB (profiles, logs, memory graphs)
  - sentence-transformers (all-MiniLM-L6-v2, 384-dim)
```

**Core modules** (must understand to work on the system):
- `config/config.py` — all constants and feature toggles
- `config/orchestrator.py` — the simulation loop
- `agent_flow/agent.py` — agent decision logic
- `agent_flow/environment.py` — world state and action resolution
- `agent_flow/memory/` — the entire memory subsystem

**Edge modules** (standalone, post-hoc):
- `scripts/run_ablation.py` — ablation study runner (memory ON vs OFF)
- `scripts/plot_ablation.py` — matplotlib visualization of ablation results
- `scripts/classify_accountability.py` — post-hoc LLM classification of speech
- `results/graph_analysis.py` — social and medicine flow graph analysis
- `simulations/medicine_shortage/rules.py` — scenario-specific event handlers

---

## 3. Simulation Loop (End-to-End Trace)

### 3.1 Per-Round Sequence

The simulation loop maps to the reference architecture's
**Perceive → Retrieve → Decide & Act → Compare → Reflect** pipeline:

```
                        Per-round Simulation Sequence
  ┌─────────┐   ┌──────────┐   ┌─────────────┐   ┌─────────┐   ┌─────────┐
  │ Perceive ├──→│ Retrieve ├──→│ Decide & Act├──→│ Compare ├──→│ Reflect │
  └─────────┘   └──────────┘   └─────────────┘   └─────────┘   └────┬────┘
       ▲                                                             │
       └─────────────────── Repeat x N ROUNDS ───────────────────────┘
```

| Step | Code Location | What Happens |
|------|---------------|--------------|
| **Perceive** | `Environment.generate_perception()` at `agent_flow/environment.py:275-344` | Build per-agent text: round/act context, scenario text (full on R1, condensed after), event messages, health dashboard, location + nearby agents, recent speech (last 2 rounds), depot stock, own status |
| **Retrieve** | `Agent.decide()` → `memory.format_memory_block()` + `memory.retrieve_commitments()` at `agent_flow/agent.py:113-127` | Embedding-based retrieval: cosine similarity × recency × importance, proximity boost, top-k, one-hop expansion (CONTRADICTS/EXTRACTED_FROM edges), score multipliers. Falls back to heuristic if no embeddings available. |
| **Decide & Act** | `Agent.decide()` → LLM call at `agent_flow/agent.py:160-179`, then `parse_action()` at `agent_flow/action_parser.py:10-82`, then `Environment.resolve_actions()` at `agent_flow/environment.py:348-427` | LLM receives system=persona, user=perception+memory+action_instruction. Response parsed to structured action dict. Actions resolved deterministically in order: MOVE → CLAIM → SHARE → SPEAK. |
| **Compare** | `ContradictionMixin._detect_contradictions()` (called automatically inside `NodesMixin.add_fact()` at `agent_flow/memory/nodes.py:102`) + `ContradictionMixin.update_commitments()` at `agent_flow/memory/contradiction.py:114-185` | New facts compared against same-subject priors via (1) keyword opposition, (2) numeric-share shortcut, (3) embedding dissimilarity < 0.30, (4) optional LLM check. Commitment statuses updated: broken if relevant contradictions exist, kept if survived N rounds without contradiction. |
| **Reflect** | `NodesMixin.add_episode()` at `agent_flow/memory/nodes.py:13-53` + `extract_facts_and_commitments()` at `agent_flow/fact_extractor.py:34-182` | Episode node created with perception text, outcomes, importance score, and embedding. Facts extracted from CLAIM/SHARE/SPEAK/MOVE outcomes. Commitments detected via regex patterns ("I will", "I promise", "let's agree", etc.). EXTRACTED_FROM edges link facts/commitments back to episodes. |

### 3.2 Concrete Call Graph

```
run_simulation.main(num_rounds, scenario_dir)
 ├── load_scenario(scenario_dir)                         # config/scenario_loader.py
 ├── get_embed_model()                                   # agent_flow/embedding.py (singleton)
 ├── db.load_profiles()                                  # config/db.py → MongoDB
 ├── for profile in profiles:
 │     ├── generate_persona_prompt(profile, scenario)     # agent_flow/persona_generator.py
 │     └── Agent(profile, persona, scenario)              # agent_flow/agent.py
 ├── Environment(agents, scenario)                        # agent_flow/environment.py
 ├── Logger()                                             # config/logger.py
 ├── Orchestrator(agents, env, logger, client, scenario)  # config/orchestrator.py
 └── orch.run_simulation(num_rounds)
      └── for r in range(num_rounds):
           └── run_round()
                ├── env.round_number += 1
                ├── rules.apply_round_events(env, rnd, scenario)  # simulations/.../rules.py
                │     └── env.update_health_statuses()             # periodic every 5 rounds
                ├── env.set_round_messages(messages)
                │
                ├── for agent in agents:                          # PERCEIVE
                │     └── env.generate_perception(agent)
                │
                ├── asyncio.gather(*[_agent_decide(a) ...])       # RETRIEVE + DECIDE
                │     ├── env.get_agents_at_location(loc)
                │     └── agent.decide(perception, client, rnd, nearby)
                │           ├── memory.format_memory_block(...)   # RETRIEVE
                │           │     ├── retrieve_relevant(...)       # embedding-based
                │           │     └── OR retrieve_memories(...)    # heuristic fallback
                │           ├── memory.retrieve_commitments(...)
                │           ├── build_memory_injection(...)
                │           └── client.chat.completions.create()  # LLM CALL
                │
                ├── for (name, response) in results:              # PARSE
                │     └── parse_action(response, name, loc, others, scenario)
                │
                ├── env.resolve_actions(actions)                  # ACT (MOVE→CLAIM→SHARE→SPEAK)
                │
                ├── metrics.update_round(rnd, outcomes, invs)     # METRICS
                │
                ├── for agent in agents:                          # REFLECT + COMPARE
                │     ├── agent.memory.add_episode(rnd, perception, outcomes)
                │     ├── extract_facts_and_commitments(memory, ep_id, rnd, outcomes, inv)
                │     │     ├── memory.add_fact(...)              # triggers _detect_contradictions()
                │     │     └── memory.add_commitment(...)
                │     └── agent.memory.update_commitments(rnd)    # COMPARE: broken/kept status
                │
                ├── logger.log_round(...)
                ├── logger.log_memory_graph(...)                  # MongoDB persistence
                └── _print_summary(rnd, actions, outcomes)
      │
      ├── _print_final_summary()
      └── logger.log_final_summary(...)
```

### 3.3 Time Advancement

- **Round-based discrete time.** `env.round_number` is incremented by 1 at the
  start of each `run_round()` call (`config/orchestrator.py:61`).
- **Fixed round count.** The loop runs exactly `num_rounds` times (default 15,
  set in `config/config.py:43`). No early termination based on victory
  conditions or agent deaths.
- **Act structure.** Rounds are grouped into narrative acts defined in
  `agent_flow/environment.py:25-30`:

  | Rounds | Act | Theme |
  |--------|-----|-------|
  | 1-4 | I | Discovery & Coordination |
  | 5-8 | II | Scarcity & Defection |
  | 9-12 | III | Crisis & Triage |
  | 13-15 | IV | Endgame & Resolution |

### 3.4 Agent Scheduling

- **Parallel within round.** All agents decide simultaneously via
  `asyncio.gather()` with a semaphore (`MAX_CONCURRENT_AGENTS = 5`) to
  rate-limit LLM calls (`config/orchestrator.py:78-98`).
- **Deterministic action resolution order.** `MOVE → CLAIM → SHARE → SPEAK`,
  ensuring movement completes before resource transfers
  (`agent_flow/environment.py:348-427`).

### 3.5 Scripted Events

Events are defined in `simulations/medicine_shortage/events.json` and
processed by `simulations/medicine_shortage/rules.py:apply_round_events()`:

| Round | Event Type | Effect |
|-------|-----------|--------|
| 5 | `announcement` | Weather alert: no more shipments after Round 12 |
| 8 | `resource_change` | Second shipment: +10 medicine to depot |
| 12 | `health_crisis` | 3 most generous agents become severely ill (+4 need) |
| 15 | `emergency_triage` | 3 random alive agents develop severe symptoms (need 5) |

Periodic health checks run every 5 rounds (`rules.py:23`), calling
`Environment.update_health_statuses()`.

---

## 4. Agent Architecture Deep Dive

### 4.1 Agent Class

Single concrete class `Agent` in `agent_flow/agent.py:62-362`. No base class,
protocol, or inheritance hierarchy. All agents are instances of the same class,
differentiated by their persona prompt and profile data.

**Internal state:**

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `str` | Identifier from profile |
| `profile` | `dict` | Full psychometric profile (Big Five, CRT, risk, dependents) |
| `persona_prompt` | `str` | System message for LLM (personality + scenario context) |
| `scenario` | `dict` | Scenario configuration |
| `location` | `str` | Current location (synced with Environment graph) |
| `resource` / `medicine` | `int` | Inventory count (aliased property, `agent.py:334-340`) |
| `memory` | `EpisodicMemoryGraph` | Per-agent memory graph (NetworkX DiGraph) |

### 4.2 Action Selection

Purely **LLM-based** — no rules engine, planning module, or behavior tree.

**Prompt structure:**

```
[System message]
  persona_prompt: personality traits + scenario context
    (generated by persona_generator.py)

[User message]
  1. Perception text (from Environment.generate_perception())
  2. Memory injection block:
     - YOUR RELEVANT MEMORIES (facts, episodes, commitments)
     - PROMISE TRACKER (broken, pending, your own promises)
     - HOW TO RESPOND (personality-calibrated accountability guidance)
  3. ACTION_INSTRUCTION_TEMPLATE:
     "You have exactly 4 actions. Pick ONE:
       SPEAK | [say something]
       MOVE | [go to: location]
       CLAIM [number] | [take resource]
       SHARE [number] [name] | [give resource]"
```

**Action parsing** (`agent_flow/action_parser.py:10-82`): Finds the last line
starting with `ACTION:`, splits on `|`, routes by command type (SPEAK, MOVE,
CLAIM, SHARE). Falls back to `WAIT` if no valid action line is found or the
action is invalid (e.g., CLAIM when not at the depot).

**Personality-calibrated accountability** (`agent_flow/agent.py:282-327`):
When broken commitments are detected, `_get_accountability_guidance()` tunes
the behavioral guidance injected into the prompt based on Big Five
agreeableness:

| Agreeableness | Tone | Guidance |
|---------------|------|----------|
| < 0.3 | Confrontational | "Call them out directly. Prioritize your own survival." |
| 0.3-0.6 | Cautious | "Mention their broken promise publicly. Protect your resources." |
| > 0.6 | Diplomatic | "Gently remind them. Give second chances, but ask for action first." |

### 4.3 Communication

There is **no direct messaging, event bus, or blackboard**. Communication is
entirely indirect through shared world state:

- **Speech log:** Location-scoped `(round, speaker, content)` tuples stored in
  `Environment.speech_log` (a `dict[str, list]`). Agents see recent speech
  (last `SPEECH_HISTORY_ROUNDS = 2` rounds) at their current location via
  perception (`environment.py:474-481`).
- **Info board:** Global `list` of `(round, author, message)` tuples. The last
  3 posts are included in every agent's perception (`environment.py:339-342`).
- **Shared world state:** Health dashboard, agent locations, depot stock — all
  visible through the perception text.

### 4.4 Agent Lifecycle

| Phase | Code Location | Description |
|-------|---------------|-------------|
| **Create** | `run_simulation.py:73-77` | Loop over profiles from MongoDB, generate persona prompt, instantiate `Agent` |
| **Init** | `Environment.__init__()` at `environment.py:42-91` | Place agents in world graph, assign random health needs (2-4), set starting location |
| **Update** | `Orchestrator.run_round()` at `orchestrator.py:59-210` | Per-round: perceive, decide, act, reflect (repeated N times) |
| **Destroy** | (none) | Agents persist for entire simulation; no explicit teardown |

### 4.5 Persona Generation

`agent_flow/persona_generator.py:generate_persona_prompt()` converts a profile
dict into a multi-paragraph system prompt:

1. **Name:** `"Your name is {name}."`
2. **Big Five traits** (5 sentences): Each trait mapped to high/mid/low
   descriptions via `_describe_trait()` with thresholds at 0.70 and 0.30.
   - `_extraversion()` — outgoing/participates/reserved
   - `_agreeableness()` — harmonious/cooperative/direct
   - `_conscientiousness()` — organized/flexible/spontaneous
   - `_neuroticism()` — sensitive/normal/calm
   - `_openness()` — curious/balanced/practical
3. **CRT score:** analytical/thoughtful/gut-instinct (thresholds at 0.9, 0.5)
4. **Risk preference:** cautious/weighed/comfortable (thresholds at 0.70, 0.30)
5. **Dependents:** "You have a family depending on you..." (if applicable)
6. **Role context:** Community size, resource shortage framing

---

## 5. Memory System Deep Dive

### 5.1 EpisodicMemoryGraph

Defined in `agent_flow/memory/graph.py:20-141`, composed from 5 mixins via
multiple inheritance:

```
EpisodicMemoryGraph
  ├── ScoringMixin ......... (scoring.py)   importance scoring
  ├── NodesMixin ........... (nodes.py)     node CRUD
  ├── ContradictionMixin ... (contradiction.py) conflict detection
  ├── RetrievalMixin ....... (retrieval.py) embedding search
  └── FormattingMixin ...... (formatting.py) prompt blocks
```

**Core attributes:**
- `agent_name: str` — owner agent
- `episode_counter`, `fact_counter`, `commitment_counter: int` — monotonic IDs
- `event_rounds: set[int]` — rounds with scripted events (importance = 1.0)
- `graph: nx.DiGraph` — the actual memory graph

**Serialization:** `to_dict()` / `from_dict()` using `nx.node_link_data()`.
Embeddings are stripped for JSON safety and recomputed via `re_embed_all()` on
deserialization.

### 5.2 Node and Edge Types

**Node types:**

| Type | ID Format | Fields | Purpose |
|------|-----------|--------|---------|
| `episode` | `ep_0`, `ep_1`, ... | `round`, `content` (full perception), `outcomes` (list of dicts), `importance` (0.3-1.0), `embedding` (384-dim) | One simulation round from the agent's perspective |
| `fact` | `fact_0`, `fact_1`, ... | `content` (short statement), `subject` (agent name), `round`, `confidence` (0-1), `embedding` | Factual statement extracted from outcomes |
| `commitment` | `commit_{agent}_{round}` | `agent`, `content`, `round_made`, `status` (pending/kept/broken), `embedding` | Detected promise or agreement |

**Edge types:**

| Type | Direction | Purpose |
|------|-----------|---------|
| `NEXT` | ep_N → ep_N+1 | Temporal ordering between consecutive episodes |
| `EXTRACTED_FROM` | fact/commit → episode | Provenance: which episode a fact/commitment came from |
| `CONTRADICTS` | fact ↔ fact (bidirectional) | Two facts about the same subject that contradict |

### 5.3 Importance Scoring

Rule-based, defined in `agent_flow/memory/scoring.py:13-54`. Highest
applicable score wins:

| Score | Condition | Example |
|-------|-----------|---------|
| 1.0 | Round is a scripted event round | Supply drop, health crisis |
| 0.9 | Agent received medicine via share | Another agent shared with you |
| 0.8 | Medicine changed hands (claim or share) | Resource transfer |
| 0.6 | Multiple agents spoke | Social coordination signal |
| 0.3 | Movement or idle only | Low-signal round |

### 5.4 Retrieval Pipeline

The primary retrieval path is `RetrievalMixin.retrieve_relevant()` at
`agent_flow/memory/retrieval.py:39-189`, a 6-step pipeline:

```
Step 1: Score all nodes
        score = cosine_similarity(query_vec, node_vec)
              × recency_score(current_round, node_round)
              × importance
        where recency_score = exp(-0.15 × rounds_ago)

Step 2: Proximity boost
        Commitments involving nearby agents × PROXIMITY_BOOST (1.8)

Step 3: Initial top-k candidates (k = RETRIEVAL_TOP_K = 7)

Step 4: One-hop graph expansion
        For each candidate, follow CONTRADICTS and EXTRACTED_FROM
        edges to pull in related nodes

Step 5: Score multipliers
        CONTRADICTION_BONUS = 1.5  (node has CONTRADICTS edge)
        BROKEN_COMMIT_BONUS = 1.3  (commitment with status "broken")
        EXPANSION_BONUS     = 1.1  (pulled in via expansion)

Step 6: Re-rank and truncate to k
```

**Heuristic fallback** (`retrieve_memories()` at `retrieval.py:276-351`): Used
when embeddings are unavailable. Buckets memories by type and scores:
- Facts: `confidence × 0.4 + recency × 0.3 + source_episode_importance × 0.3`
- Episodes: `importance × 0.6 + recency × 0.4`
- Commitments: `recency × status_weight × proximity` (via `retrieve_commitments()`)

### 5.5 Contradiction Detection

Four detection rules evaluated in order in
`ContradictionMixin._detect_contradictions()` at
`agent_flow/memory/contradiction.py:28-110`:

| Rule | Method | Example |
|------|--------|---------|
| 1 | Keyword opposition | "share"/"fair" vs "hoard"/"claim" |
| 2 | Numeric-share shortcut | Prior says "fair/equal" + new says "claimed >= 3" |
| 3 | Embedding dissimilarity | cosine_similarity < 0.30 (`COSINE_CONTRADICT_THRESHOLD`) |
| 4 | LLM check (optional) | Ollama prompt: "Do these facts contradict?" (`USE_LLM_CONTRADICTION = False` by default) |

When a contradiction is detected, **bidirectional** `CONTRADICTS` edges are
added between the two fact nodes.

### 5.6 Commitment Status Updates

`ContradictionMixin.update_commitments()` at `contradiction.py:114-185`,
called once per round per agent from the orchestrator:

- **"broken"**: A fact about the committing agent has a `CONTRADICTS` edge, and
  the contradicting pair is relevant to the commitment's content (keyword
  overlap check via `_contradiction_relevant_to_commitment()`). The commitment's
  importance is boosted to 1.0.
- **"kept"**: `(current_round - round_made) >= COMMITMENT_KEPT_ROUNDS` (2
  rounds) with no relevant contradictions.

### 5.7 Fact Extraction

`agent_flow/fact_extractor.py:extract_facts_and_commitments()` — rule-based,
no LLM call required:

| Action | Facts Extracted | Commitment Detection |
|--------|-----------------|---------------------|
| `CLAIM` | "{agent} claimed {n} units in Round {r}" + "{agent} now holds {total} units" | — |
| `SHARE` | "{agent} shared {n} units with {target}" + "{target} now holds {total} units" | — |
| `SPEAK` | "{agent} said: '{content}'" | 10 regex patterns: "I will", "I promise", "I'll share/give/help", "we should all", "let's agree to", "fair", "equal", "distribute" |
| `MOVE` | "{agent} moved to {location}" | — |
| `POST` | "{agent} posted: '{content}' on info board" | — |

---

## 6. Environment and World State

### 6.1 World Graph

`Environment` (`agent_flow/environment.py:41-523`) uses a **NetworkX DiGraph**
to represent the world:

```
  ┌─────────────────┐
  │ resource_depot   │ type="object", amount=50
  └────────┬────────┘
           │ (conceptual)
  ┌────────┴────────┐
  │   Town Hall     │ type="location"  (starting location)
  │   Supply Depot  │ type="location"  (resource location)
  │   Residential   │ type="location"
  └────────┬────────┘
           │ LOCATED_AT / CONTAINS
  ┌────────┴────────┐
  │   Alice         │ type="agent", resource=0, health_status="healthy",
  │   Bob           │   health_need=3, unmet_checks=0
  │   ...           │
  └─────────────────┘
```

**Graph edges:** Each agent has exactly one `LOCATED_AT` edge to their current
location, and the location has a reciprocal `CONTAINS` edge back. Movement
updates both edges atomically via `_set_location()`.

### 6.2 Action Resolution

`Environment.resolve_actions()` at `environment.py:348-427` processes actions
in a fixed order to avoid race conditions:

1. **MOVE** — update agent locations in graph
2. **CLAIM** — deduct from depot, add to agent (`min(requested, available)`)
3. **SHARE** — transfer between agents (must be at same location, must have
   sufficient resource)
4. **SPEAK** — append to location-scoped speech log (truncated to 200 chars)

### 6.3 Health System

A state machine defined in `Environment.update_health_statuses()` at
`environment.py:153-191`:

```
                     held >= need
  healthy ◄──────────────────────────── (reset unmet_checks=0, consume medicine)
    │
    │ held < need (unmet_checks=1)
    ▼
  symptomatic
    │
    │ held < need (unmet_checks=2)
    ▼
  severe
    │
    │ held < need (unmet_checks=3)
    ▼
  dead (irreversible)
```

Each agent has a random `health_need` (2-4 units per check). Health checks
run every `check_interval` rounds (default 5). If `held >= need`, medicine is
consumed and the agent resets to healthy.

### 6.4 Perception Generation

`Environment.generate_perception()` at `environment.py:275-344` builds a
text block per agent containing:

1. Round number and act context (e.g., "Act II: Scarcity & Defection")
2. Scenario text (full narrative on Round 1, condensed reminder after)
3. Event messages for this round (from `rules.apply_round_events()`)
4. Community Health Dashboard (bar chart, counts, Gini)
5. Current location + names of other agents present
6. Recent conversation at this location (last 2 rounds of speech)
7. Depot stock (only visible if agent is at the Supply Depot)
8. Agent's own status (health, need, inventory, depot stock)
9. Info board (last 3 posts)

---

## 7. Data Structures and Algorithms

### 7.1 Key Data Structures

| Structure | Type | Location | Purpose | Invariants |
|-----------|------|----------|---------|------------|
| World graph | `nx.DiGraph` | `Environment.graph` | Nodes = locations + agents + depot. Edges = LOCATED_AT, CONTAINS | Each agent has exactly one LOCATED_AT edge |
| Memory graph | `nx.DiGraph` | `EpisodicMemoryGraph.graph` | Nodes = episodes + facts + commitments. Edges = NEXT, EXTRACTED_FROM, CONTRADICTS | Episodes linearly ordered via NEXT; CONTRADICTS always bidirectional |
| Speech log | `dict[str, list[tuple]]` | `Environment.speech_log` | Per-location speech history | Append-only; tuples are (round, speaker, content) |
| Agent dict | `dict[str, Agent]` | `Environment.agents` | Name-indexed agent lookup | Keys match world graph node IDs |
| Action dict | plain `dict` | return of `parse_action()` | Structured action with keys: agent, type, content, target_location, amount, target_agent, reasoning, raw_response | `type` is one of: wait, speak, move, claim, share |
| Outcome dict | plain `dict` | return of `resolve_actions()` | Result with keys: agent, action, detail | One per resolved action |
| Metrics arrays | `list[float]`, `list[int]` | `MetricsCollector` | Per-round Gini and accountability event counts | Append one entry per round |

### 7.2 Key Algorithms

| Algorithm | Location | Purpose |
|-----------|----------|---------|
| **Gini coefficient** | `metrics/collector.py:28-46` and `agent_flow/environment.py:203-216` | Measures inequality of medicine distribution. O(n log n) sorted-values formulation: `G = Σ(2(i+1) - n - 1) × x_i / (n × Σx)` |
| **Cosine similarity** | `agent_flow/embedding.py:59-66` | Semantic similarity between memory embeddings. Clamped to [0, 1]. |
| **Exponential recency decay** | `agent_flow/embedding.py:69-72` | `exp(-0.15 × gap)` — recent memories score higher, older ones fade |
| **Rule-based importance scoring** | `agent_flow/memory/scoring.py:13-54` | 5-tier heuristic: event round (1.0) > received share (0.9) > resource transfer (0.8) > multi-agent speech (0.6) > idle (0.3) |
| **Contradiction detection (4 rules)** | `agent_flow/memory/contradiction.py:28-110` | (1) keyword opposition, (2) numeric-share shortcut, (3) cosine < 0.30, (4) optional LLM check |
| **Commitment pattern matching** | `agent_flow/fact_extractor.py:18-31` | 10 regex patterns detecting promise-like speech ("I will", "I promise", "let's agree", "fair", "equal", etc.) |
| **Accountability detection** | `metrics/collector.py:88-116` | Speech acts referencing another agent's name + accountability verb (promised, took, hoarded, etc.) |
| **Health state machine** | `agent_flow/environment.py:153-191` | healthy → symptomatic (1 unmet) → severe (2 unmet) → dead (3 unmet). Reset on sufficient medicine. |

---

## 8. Metrics, Logging, and Persistence

### 8.1 MetricsCollector

`metrics/collector.py:49-147` tracks two metrics per round:

1. **Gini coefficient** of medicine distribution across all agents
2. **Accountability events** — speech acts where an agent references another
   agent by name AND uses an accountability verb (promised, said, took, refused,
   shared, lied, stole, gave, claimed, hoarded, broke, kept, agreed, failed)

`finalize()` returns: `gini_over_time`, `accountability_over_time`,
`gini_final`, `accountability_events`, `total_speech_acts`,
`accountability_rate`.

### 8.2 Logger

`config/logger.py:13-44` persists to MongoDB via `config/db.py`:

| Method | MongoDB Operation | Collection |
|--------|-------------------|------------|
| `log_config(profiles, settings)` | `insert_one()` — creates simulation doc | `logs` |
| `log_round(round_data)` | `update_one($push)` — appends to rounds array | `logs` |
| `log_final_summary(summary)` | `update_one($set)` — marks completed | `logs` |
| `log_memory_graph(agent, graph, count)` | `update_one(upsert=True)` — persists memory | `agent_memories` |

### 8.3 Speech Log JSONL

The orchestrator also writes per-speech-act records to
`results/speech_log{tag}.jsonl` for post-hoc classification by
`scripts/classify_accountability.py`.

### 8.4 MongoDB Schema

**Database:** `thesis-architecture`

**Collections:**
- `profiles` — agent profile documents (Big Five, CRT, risk, dependents)
- `logs` — simulation runs (config, rounds array, final_summary)
- `agent_memories` — per-agent memory graphs (compound index on
  `simulation_id` + `agent_name`)

---

## 9. Configuration and Extensibility

### 9.1 Configuration Files

| File | Format | Purpose |
|------|--------|---------|
| `config/config.py` | Python constants | LLM settings (`MODEL_NAME`, `TEMPERATURE`, `MAX_TOKENS`), embedding model (`EMBEDDING_MODEL`, `EMBEDDING_DIM`), retrieval params (`RETRIEVAL_TOP_K`, `RECENCY_DECAY`), contradiction thresholds (`COSINE_CONTRADICT_THRESHOLD`), ablation toggle (`USE_LAYER2_MEMORY`), round count (`NUM_ROUNDS = 15`) |
| `.env` | dotenv | `ANTHROPIC_API_KEY`, `MONGODB_URI` |
| `simulations/medicine_shortage/config.yaml` | YAML | Scenario definition: 3 locations, 18 agents, health system (need 2-4, check every 5 rounds), resource (50 initial, 90 full coverage), events file, victory conditions (67% healthy), metrics to track |
| `simulations/medicine_shortage/events.json` | JSON | 4 scripted events: R5 announcement, R8 +10 supply, R12 health crisis, R15 emergency triage |
| `simulations/medicine_shortage/scenario.md` | Markdown (template) | Narrative scenario text rendered with config values via `_render_scenario_text()` |

### 9.2 How to Add a New Agent Type

Currently only one `Agent` class exists. To add a new type:

1. Create a new class in `agent_flow/` (e.g., `reactive_agent.py`) with the
   same interface:
   - `__init__(self, profile, persona_prompt, scenario)` — sets `.name`,
     `.location`, `.resource`, `.memory`
   - `async decide(self, perception, client, round_num, nearby_agents) -> str`
2. Update `run_simulation.py` to conditionally instantiate the new agent type
   based on a profile field or config flag.
3. No changes needed to `Orchestrator` — it only requires agents with `.name`,
   `.location`, `.resource`, `.memory`, and `.decide()`.

### 9.3 How to Add a New Scenario

1. Create a new directory under `simulations/` (e.g., `simulations/water_crisis/`).
2. Add `config.yaml` (locations, resource, health system, agents, events_file,
   victory_conditions), `events.json`, `scenario.md`, and optionally `rules.py`.
3. Run with `python run_simulation.py --scenario simulations/water_crisis`.
4. The `rules.py` module is dynamically loaded via `importlib`
   (`run_simulation.py:46-56`) and must expose:
   ```python
   def apply_round_events(environment, round_number: int, config: dict) -> list[dict]:
   ```

### 9.4 How to Add a New Action

1. Add the action to `ACTION_INSTRUCTION_TEMPLATE` in `agent_flow/agent.py:28-59`.
2. Add a parsing case to `parse_action()` in `agent_flow/action_parser.py:51-81`.
3. Add a resolution block in `Environment.resolve_actions()` in
   `agent_flow/environment.py:348-427`.
4. Add fact extraction rules in `agent_flow/fact_extractor.py:61-181`.

### 9.5 How to Add a New Sensor / Observation

Add content to `Environment.generate_perception()` at
`agent_flow/environment.py:275-344`. The method builds a list of text parts
that are joined with newlines. New observations can be appended at any point
in the sequence.

---

## 10. Three Traced Execution Paths

### Path A: Program Start → Run Loop

```
$ python run_simulation.py --rounds 15 --scenario simulations/medicine_shortage

  1. argparse parses --rounds=15, --scenario=simulations/medicine_shortage
  2. asyncio.run(main(15, "simulations/medicine_shortage"))
  3. load_scenario("simulations/medicine_shortage")
       → reads config.yaml, events.json, scenario.md
       → normalizes locations, renders scenario_text template
  4. get_embed_model()
       → lazy-loads SentenceTransformer("all-MiniLM-L6-v2")
       → prints "[Embedding] Loaded model: all-MiniLM-L6-v2"
  5. db.load_profiles()
       → MongoDB query: profiles.find().sort("pid", 1)
       → returns 18 profile dicts
  6. for each of 18 profiles:
       → generate_persona_prompt(profile, scenario)
           → Big Five → text, CRT → text, risk → text, dependents → text
           → concatenate with ROLE_CONTEXT_TEMPLATE
       → Agent(profile, persona, scenario)
           → sets .name, .location="Town Hall", .resource=0
           → creates EpisodicMemoryGraph(name, event_rounds={5,8,12,15})
  7. Environment(agents, scenario)
       → builds nx.DiGraph with 22 nodes: 1 depot + 3 locations + 18 agents
       → each agent gets LOCATED_AT → "Town Hall" edge
       → speech_log initialized: {"Town Hall": [], "Supply Depot": [], "Residential Area": []}
  8. Logger().log_config(profiles, settings)
       → creates MongoDB document in 'logs' collection
       → prints simulation ID
  9. client = AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
 10. Orchestrator(agents, env, logger, client, scenario)
       → creates MetricsCollector with 18 agent names
       → opens results/speech_log.jsonl for JSONL output
 11. orch.run_simulation(15)
       → prints "SIMULATION START — 18 agents, 15 rounds"
       → enters loop: for r in range(15): await self.run_round()
```

### Path B: One Agent Decision Cycle → Action Application

```
Orchestrator.run_round() [Round 5, agent "Alice"]:

  PERCEIVE:
    env.generate_perception(alice) produces:
      "=== ROUND 5 of 15 (Act II: Scarcity & Defection) ===
       REMINDER: Medicine is stored at the Supply Depot...
       WEATHER ALERT: Road to neighboring town will be blocked after Round 12...
       COMMUNITY HEALTH DASHBOARD:
         [████████████████████] 18/18 healthy (100%)
       Location: Supply Depot
       Others here: Bob, Charlie
       RECENT CONVERSATION:
         [Round 4] Bob: "Let's all take only 2 each"
       Medicine available at depot: 38 units
       YOUR STATUS:
         Health: OK (healthy) — you need 3 units per health check
         Medicine you hold: 2 units
         Medicine at depot: 38 units"

  RETRIEVE:
    agent.decide() calls:
      memory.format_memory_block(round=5, perception=above, nearby={"Bob","Charlie"})
        → retrieve_relevant(embed(perception), round=5, k=7, nearby={"Bob","Charlie"})
           → scores all 20 memory nodes: cosine × recency × importance
           → proximity-boosts Bob's commitment node (× 1.8)
           → picks top 7, expands via CONTRADICTS/EXTRACTED_FROM
           → applies CONTRADICTION_BONUS, BROKEN_COMMIT_BONUS, EXPANSION_BONUS
           → re-ranks and returns 7 nodes
        → formats into "YOUR RELEVANT MEMORIES:" block
      memory.retrieve_commitments(round=5, k=5, nearby={"Bob","Charlie"})
        → returns scored commitment dicts

  DECIDE:
    build_memory_injection(memory_block, commitments, round=5)
      → Section 1: general memories
      → Section 2: PROMISE TRACKER
           "WARNING BROKEN: Bob promised 'fair share' in Round 2 — did NOT follow through."
           "YOUR PROMISE: You said 'I will share' in Round 3 — status: PENDING."
      → Section 3: HOW TO RESPOND (agreeableness=0.25 → confrontational)
           "Bob broke promises. Call them out directly. Prioritize your own survival."
    Builds user_message = perception + memory_injection + ACTION_INSTRUCTION_TEMPLATE
    LLM call: system=persona_prompt, user=user_message
    Response: "Bob broke his promise about fair sharing. I need to look out for
              my family. ACTION: CLAIM 3 | For my family"

  PARSE:
    parse_action(response, "Alice", "Supply Depot", ["Bob","Charlie"], scenario)
      → finds "ACTION: CLAIM 3 | For my family"
      → confirms Alice is at Supply Depot (valid for CLAIM)
      → extracts amount=3
      → returns {"agent":"Alice", "type":"claim", "amount":3, "content":"For my family", ...}

  ACT:
    env.resolve_actions([...all 18 actions...])
      → MOVE phase: processes all MOVE actions
      → CLAIM phase: Alice claims 3 from depot (38→35), Alice.resource = 2+3 = 5
      → SHARE phase: processes all SHARE actions
      → SPEAK phase: processes all SPEAK actions
      → returns outcome list including:
        {"agent":"Alice", "action":"claim", "detail":"Claimed 3 units (requested 3)"}

  REFLECT + COMPARE:
    agent.memory.add_episode(round=5, perception=above, outcomes=relevant)
      → creates ep_4 node, importance=1.0 (event round), embeds perception
      → links ep_3 → ep_4 via NEXT edge
    extract_facts_and_commitments(memory, "ep_4", round=5, outcomes, inventories)
      → add_fact("Alice claimed 3 units in Round 5", subject="Alice", ...)
           → _detect_contradictions() checks against prior facts about Alice
           → if "fair"/"equal" fact exists + claimed≥3 → CONTRADICTS edge added
      → add_fact("Alice now holds 5 units", subject="Alice", ...)
    agent.memory.update_commitments(round=5)
      → scans pending commitments for Alice
      → if contradiction found relevant to Alice's promise → status = "broken"
```

### Path C: Reset / Init Path

There is **no mid-simulation reset**. Initialization happens once at startup:

```
Agent.__init__(profile, persona_prompt, scenario):
  .name = profile["name"]                          # e.g. "Alice"
  .location = scenario["start_location"]            # "Town Hall"
  .resource = 0                                     # no medicine
  .memory = EpisodicMemoryGraph(
      agent_name="Alice",
      event_rounds={5, 8, 12, 15}                   # from events.json
  )
  # memory.graph starts empty: 0 nodes, 0 edges

Environment.__init__(agents, scenario):
  .graph = nx.DiGraph()
  .round_number = 0
  .deaths = 0
  → add_node("resource_depot", type="object", amount=50)
  → for each of 3 locations:
      add_node(loc, type="location")
  → for each of 18 agents:
      health_need = random.randint(2, 4)
      add_node(name, type="agent", resource=0,
               health_status="healthy", health_need=health_need,
               unmet_checks=0)
      add_edge(name → "Town Hall", relation=LOCATED_AT)
      add_edge("Town Hall" → name, relation=CONTAINS)
      agent.location = "Town Hall"
  → speech_log = {"Town Hall": [], "Supply Depot": [], "Residential Area": []}
  → info_board = []
```

To re-run, restart `python run_simulation.py`. Each run gets a fresh
simulation ID in MongoDB.

---

## 11. Discrepancies Between Reference Image and Implementation

| Reference Image | Implementation | Notes |
|-----------------|----------------|-------|
| **"Compare" as a distinct step** | No explicit `compare()` method | The "Compare" functionality is **embedded within the Reflect phase**: contradiction detection runs automatically inside `add_fact()` (at `nodes.py:102`), and `update_commitments()` is called explicitly in the orchestrator loop (at `orchestrator.py:191`). The compare logic exists but is not a separate orchestration step. |
| **Arrow from Reflect back to Perceive** | Loop is `for r in range(num_rounds)` | Correct — the loop naturally returns to the top (perceive) on the next iteration. |
| **3-layer architecture (Persona → Memory → Action-Perception)** | Matches code exactly | Layer 1 = `persona_generator.py`, Layer 2 = `agent_flow/memory/`, Layer 3 = orchestrator loop + environment + agent.decide() |
| **No mention of "ablation" or "metrics"** | Code has a full ablation framework | `USE_LAYER2_MEMORY` toggle (`config.py:40`), `scripts/run_ablation.py`, `MetricsCollector`, `scripts/plot_ablation.py` are additional capabilities not shown in the diagram. |

---

## 12. Top 10 Files to Read First

| # | File | Why |
|---|------|-----|
| 1 | `config/orchestrator.py` | **The simulation loop.** All 8 steps of a round are here. Understand this file and you understand the system. |
| 2 | `agent_flow/agent.py` | **Agent decision logic.** Shows how persona + memory + perception are assembled into an LLM prompt and how the response is returned. |
| 3 | `agent_flow/environment.py` | **World state and action resolution.** The NetworkX graph, perception generation, action resolution order, health system. |
| 4 | `agent_flow/memory/graph.py` | **Memory system entrypoint.** Composition of all mixins, serialization, re-embedding. |
| 5 | `agent_flow/memory/retrieval.py` | **Memory retrieval pipeline.** The 6-step embedding-based retrieval with graph expansion — the "intelligence" of the memory system. |
| 6 | `config/config.py` | **All tunable parameters.** LLM settings, embedding model, retrieval params, contradiction thresholds, ablation toggle. |
| 7 | `agent_flow/fact_extractor.py` | **How raw outcomes become structured memories.** Rule-based extraction of facts and commitment detection via regex. |
| 8 | `agent_flow/memory/contradiction.py` | **Contradiction detection and commitment updates.** The 4-rule detection pipeline and the broken/kept status machine. |
| 9 | `agent_flow/persona_generator.py` | **Layer 1: personality grounding.** How Big Five traits become natural-language system prompts. |
| 10 | `simulations/medicine_shortage/config.yaml` | **Scenario definition.** Understand the domain: locations, health system, resource constraints, events, victory conditions. |

---

## 13. Component Summary Table

| Component | Main Files/Classes | Purpose | Called By |
|-----------|--------------------|---------|-----------|
| **Entrypoint** | `run_simulation.py :: main()` | CLI parsing, wiring, launch | User (CLI) |
| **Orchestrator** | `config/orchestrator.py :: Orchestrator` | Simulation loop (8 steps per round) | `main()` |
| **Agent** | `agent_flow/agent.py :: Agent` | LLM-based decision making with memory | `Orchestrator.run_round()` |
| **Environment** | `agent_flow/environment.py :: Environment` | World graph, perception, action resolution, health | `Orchestrator`, `Agent` (via perception) |
| **Memory Graph** | `agent_flow/memory/graph.py :: EpisodicMemoryGraph` | Per-agent episodic/semantic/commitment memory | `Agent.decide()`, `Orchestrator` |
| **Retrieval** | `agent_flow/memory/retrieval.py :: RetrievalMixin` | Embedding-based memory retrieval with graph expansion | `FormattingMixin.format_memory_block()` |
| **Contradiction** | `agent_flow/memory/contradiction.py :: ContradictionMixin` | Detect fact contradictions, update commitment status | `NodesMixin.add_fact()`, `Orchestrator` |
| **Fact Extractor** | `agent_flow/fact_extractor.py :: extract_facts_and_commitments()` | Rule-based extraction of facts and commitments from outcomes | `Orchestrator.run_round()` |
| **Persona** | `agent_flow/persona_generator.py :: generate_persona_prompt()` | Convert psychometric profile to LLM system prompt | `main()` |
| **Action Parser** | `agent_flow/action_parser.py :: parse_action()` | Parse LLM text response into structured action dict | `Orchestrator.run_round()` |
| **Embedding** | `agent_flow/embedding.py :: embed_text(), cosine_similarity()` | Sentence embeddings (384-dim), similarity, recency | Memory subsystem |
| **Metrics** | `metrics/collector.py :: MetricsCollector` | Gini coefficient and accountability tracking per round | `Orchestrator.run_round()` |
| **Logger** | `config/logger.py :: Logger` | MongoDB persistence of simulation logs and memory graphs | `Orchestrator` |
| **Scenario Loader** | `config/scenario_loader.py :: load_scenario()` | YAML/JSON/MD loading and normalization | `main()` |
| **Rules** | `simulations/medicine_shortage/rules.py :: apply_round_events()` | Scenario-specific event handlers (health crises, supply drops) | `Orchestrator.run_round()` |
| **DB** | `config/db.py` | MongoDB CRUD for profiles, simulations, memory graphs | `Logger`, `main()` |
| **Ablation Runner** | `scripts/run_ablation.py` | Runs N simulation pairs (memory ON vs OFF) | User (CLI) |
| **Ablation Plotter** | `scripts/plot_ablation.py` | Plots Gini and accountability over rounds | User (CLI) |
| **Accountability Classifier** | `scripts/classify_accountability.py` | Post-hoc LLM classification of speech acts | User (CLI) |
| **Graph Analysis** | `results/graph_analysis.py` | Post-hoc social and medicine flow graph analysis | User (CLI) |
