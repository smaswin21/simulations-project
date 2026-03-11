"""
orchestrator.py — The simulation loop.

Each round:
  1. Apply events (resource changes, etc.)
  2. Generate perception for every agent
  3. All agents decide in PARALLEL (async LLM calls) with rate limiting
  4. Parse LLM responses into structured actions
  5. Environment resolves all actions
  6. Store episodic memories for each agent (Layer 2)
  7. Log everything (including memory graphs to MongoDB)
  8. Print a round summary with commons status
"""

import asyncio
import json
from pathlib import Path

from agent_flow.action_parser import parse_action
from agent_flow.fact_extractor import extract_facts_and_commitments
from agent_flow.environment import _get_act
from config.config import MAX_CONCURRENT_AGENTS
from metrics.collector import MetricsCollector

# Directory for per-speech-act JSONL logs (post-hoc classifier input)
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


class Orchestrator:
    def __init__(self, agents, environment, logger, client, scenario: dict,
                 condition: str = "", seed: int = 0):
        """
        Args:
            agents: list of Agent objects
            environment: Environment instance
            logger: Logger instance
            client: anthropic.AsyncAnthropic() instance
            condition: ablation condition label ("A" or "B")
            seed: random seed for this run
        """
        self.agents = agents
        self.env = environment
        self.logger = logger
        self.client = client
        self.scenario = scenario
        self.rules = scenario.get("rules")

        # Phase 5: Metrics collector for ablation study
        self.metrics = MetricsCollector(
            agent_names=[a.name for a in agents],
        )

        # Per-speech-act JSONL log for post-hoc LLM classification
        # Each run gets its own file to avoid cross-run contamination
        RESULTS_DIR.mkdir(exist_ok=True)
        tag = f"_{condition}_{seed}" if condition else ""
        self._speech_log_path = RESULTS_DIR / f"speech_log{tag}.jsonl"

    async def run_round(self):
        """Execute one full simulation round."""
        self.env.round_number += 1
        rnd = self.env.round_number

        # Handle event-triggered state changes
        if self.rules:
            messages = self.rules.apply_round_events(self.env, rnd, self.scenario)
        else:
            messages = []
        self.env.set_round_messages(messages)

        # ── Step 1: Generate perceptions ─────────────────────
        perceptions = {}
        for agent in self.agents:
            perceptions[agent.name] = self.env.generate_perception(agent)
            
        # ── Step 2: All agents decide in parallel (with rate limiting) ────────────
        # Create semaphore to limit concurrent LLM calls
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_AGENTS)
        
        async def _agent_decide(agent):
            async with semaphore:  # Only allow MAX_CONCURRENT_AGENTS at once
                try:
                    # Compute nearby agents for proximity-aware retrieval
                    nearby = self.env.get_agents_at_location(
                        agent.location, exclude=agent.name,
                    )
                    response = await agent.decide(
                        perceptions[agent.name], self.client,
                        round_num=rnd, nearby_agents=nearby,
                    )
                    return agent.name, response
                except Exception as e:
                    print(f"Agent {agent.name} LLM call failed: {e}")
                    return agent.name, "ACTION: WAIT | Error occurred."

        results = await asyncio.gather(
            *[_agent_decide(a) for a in self.agents]
        )

        # ── Step 3: Parse responses into actions ─────────────
        actions = []
        agent_logs = []

        for agent_name, raw_response in results:
            agent = self.env.agents[agent_name]
            others_here = [
                a.name for a in self.env.agents.values()
                if a.location == agent.location and a.name != agent.name
            ]

            parsed = parse_action(
                raw_response,
                agent_name,
                agent.location,
                others_here,
                self.scenario,
            )
            actions.append(parsed)

            agent_logs.append({
                "agent": agent_name,
                "location": agent.location,
                "perception_snippet": perceptions[agent_name][:200] + "...",
                "reasoning": parsed["reasoning"][:300],
                "action_type": parsed["type"],
                "action_content": parsed.get("content", "")[:200],
                "raw_response": raw_response[:500],
            })

        # ── Step 4: Resolve actions in the environment ───────
        outcomes = self.env.resolve_actions(actions)

        # ── Phase 5: Update metrics (Gini + accountability) ──
        agent_inventories = {
            agent.name: agent.resource for agent in self.agents
        }
        self.metrics.update_round(rnd, outcomes, agent_inventories)

        # ── Commons-specific metrics ─────────────────────────
        commons_config = self.scenario.get("commons", {})
        if commons_config.get("enabled"):
            sustainable_quota = commons_config.get("default_sustainable_quota", 1)
            self.metrics.update_cooperation_rate(
                rnd,
                self.env.round_harvest_actions,
                sustainable_quota,
            )
            self.metrics.update_resource_stock(self.env._get_depot_resource())

        # ── Per-speech-act JSONL logging (for post-hoc classifier) ──
        speech_records = []
        for outcome in outcomes:
            if outcome.get("action") == "speak":
                speech_records.append({
                    "round": rnd,
                    "speaker": outcome.get("agent", ""),
                    "detail": outcome.get("detail", ""),
                    "location": self.env.agents[outcome["agent"]].location
                        if outcome.get("agent") in self.env.agents else "",
                })
        if speech_records:
            with open(self._speech_log_path, "a") as f:
                for record in speech_records:
                    f.write(json.dumps(record) + "\n")

        # ── Step 5: Store episodic memories + extract facts (Layer 2) ──
        # Build current inventory snapshot for fact extraction
        agent_inventories = {
            agent.name: agent.resource for agent in self.agents
        }

        # Derive extraction verb for fact text
        _VERB_MAP = {"CLAIM": "claimed", "GRAZE": "grazed"}
        _raw_verb = self.scenario.get("resource", {}).get(
            "resource_extraction_action", "CLAIM"
        ).upper()
        _extraction_verb = _VERB_MAP.get(_raw_verb, _raw_verb.lower() + "d")

        for agent in self.agents:
            # Filter outcomes relevant to this agent:
            # - actions this agent took
            # - actions that targeted this agent (e.g. someone shared with them)
            # - speech/actions by agents at the same location
            agent_location = agent.location
            relevant_outcomes = [
                o for o in outcomes
                if (
                    o.get("agent") == agent.name
                    or agent.name in o.get("detail", "")
                    or self._agent_was_at_location(o.get("agent"), agent_location)
                )
            ]
            episode_id = agent.memory.add_episode(
                round_num=rnd,
                perception_text=perceptions[agent.name],
                outcomes=relevant_outcomes,
            )

            # Phase 2: Extract facts and commitments from this episode
            extract_facts_and_commitments(
                memory=agent.memory,
                episode_id=episode_id,
                round_num=rnd,
                outcomes=relevant_outcomes,
                agent_inventories=agent_inventories,
                extraction_verb=_extraction_verb,
            )

            # Phase 4: Update commitment statuses based on contradiction edges
            agent.memory.update_commitments(rnd)

        # ── Step 6: Log everything ───────────────────────────
        self.logger.log_round({
            "round": rnd,
            "world_state": self.env.get_world_state(),
            "agent_actions": agent_logs,
            "outcomes": outcomes,
        })

        # ── Step 7: Persist memory graphs to MongoDB ─────────
        for agent in self.agents:
            self.logger.log_memory_graph(
                agent.name,
                agent.memory.to_dict(),
                agent.memory.episode_count,
            )

        # ── Step 8: Print round summary ──────────────────────
        self._print_summary(rnd, actions, outcomes)

    def _agent_was_at_location(self, agent_name: str, location: str) -> bool:
        """Check if a given agent is at the specified location."""
        if agent_name is None:
            return False
        agent = self.env.agents.get(agent_name)
        if agent is None:
            return False
        return agent.location == location

    async def run_simulation(self, num_rounds: int):
        """Run the full simulation."""
        # Build act timeline from config or defaults
        acts_config = self.scenario.get("acts")
        if acts_config:
            act_parts = []
            for act in acts_config:
                label = act.get("label", "?")
                start = act.get("start_round", "?")
                end = act.get("end_round", "?")
                act_parts.append(f"Act {label} ({start}-{end})")
            act_line = " → ".join(act_parts)
        else:
            act_line = f"{num_rounds} rounds (no act structure)"

        sim_name = self.scenario.get("simulation", {}).get("name", "Simulation")
        print(f"\n{'━'*60}")
        print(f"  {sim_name.upper()} — {len(self.agents)} agents, {num_rounds} rounds")
        print(f"  {act_line}")
        print(f"{'━'*60}\n")

        for r in range(num_rounds):
            await self.run_round()

        # Final memory graph persistence (ensure last round is saved)
        for agent in self.agents:
            self.logger.log_memory_graph(
                agent.name,
                agent.memory.to_dict(),
                agent.memory.episode_count,
            )

        self._print_final_summary()

    def get_metrics_summary(self) -> dict:
        """Return the finalized metrics dict (call after run_simulation)."""
        return self.metrics.finalize()

    # ── Display helpers ──────────────────────────────────────

    def _print_summary(self, rnd: int, actions: list, outcomes: list):
        """Print a concise round summary to console."""
        act_label, act_desc = _get_act(rnd, self.scenario)

        print(f"\n{'━'*50}")
        print(f"  ROUND {rnd}/{self.env.max_rounds}  (Act {act_label}: {act_desc})")
        print(f"{'━'*50}")

        # Show event if any
        for message in self.env.round_messages:
            print(f"  📢 {message}")

        # Scenario-appropriate status display
        commons_config = self.scenario.get("commons", {})
        print()
        current_stock = self.env._get_depot_resource()
        initial_stock = self.env.resource_supply
        regen_rate = getattr(self.env, "_commons_regeneration_override", None)
        if regen_rate is None:
            regen_rate = commons_config.get("regeneration_per_round", 12)
        collapse_threshold = commons_config.get("collapse_threshold", 20)
        last_total = sum(h["amount"] for h in self.env.round_harvest_actions)
        print(f"  COMMONS STATUS:")
        print(f"    Pasture stock: {current_stock}/{initial_stock} units")
        print(f"    Regeneration:  {regen_rate} units/round")
        if self.env.round_number > 1:
            marker = " (OVER)" if last_total > regen_rate else ""
            print(f"    Last round grazing: {last_total} units{marker}")
        if current_stock < collapse_threshold:
            print(f"    !! ECOSYSTEM COLLAPSED !!")
        elif current_stock < collapse_threshold * 2:
            print(f"    WARNING: Pasture dangerously low")
        print(f"    Gini: {self.env.calculate_gini():.2f}")

        # Group actions by location
        for loc in self.scenario.get("locations", []):
            loc_name = loc.get("name")
            if not loc_name:
                continue
            agents_here = [
                a for a in self.agents if a.location == loc_name
            ]
            if not agents_here:
                continue

            action_strs = []
            for a in agents_here:
                # Find this agent's action
                act = next((x for x in actions if x["agent"] == a.name), None)
                if act:
                    label = act["type"].upper()
                    if act["type"] == "speak":
                        label = f'SPOKE: "{act["content"][:55]}..."'
                    elif act["type"] == "graze":
                        label = f"GRAZED {act.get('amount', '?')}"
                    elif act["type"] == "move":
                        label = f"→ {act['target_location']}"
                    elif act["type"] == "share":
                        target = act.get("target_agent", "?")
                        amt = act.get("amount", "?")
                        label = f"SHARED {amt} → {target}"
                    action_strs.append(f"    {a.name}: {label}")

            print(f"\n  📍 {loc_name} ({len(agents_here)} agents)")
            for s in action_strs:
                print(s)

        resource_name = self.scenario.get("resource", {}).get("name", "resource")
        print(f"\n  📦 {resource_name.title()} at depot: {self.env.resource_depot}")
        print(f"{'━'*50}")

    def _print_final_summary(self):
        """Print end-of-simulation summary with full dashboard."""
        print(f"\n{'═'*60}")
        print(f"  SIMULATION COMPLETE")
        print(f"{'═'*60}")

        commons_config = self.scenario.get("commons", {})
        total_held = sum(a.resource for a in self.agents)
        resource_name = self.scenario.get("resource", {}).get("name", "resource")
        resource_unit = self.scenario.get("resource", {}).get("unit", "units")

        # ── Commons final summary ────────────────────────
        current_stock = self.env._get_depot_resource()
        initial_stock = self.env.resource_supply
        collapse_threshold = commons_config.get("collapse_threshold", 20)
        collapsed = current_stock < collapse_threshold

        print()
        print(f"  COMMONS OUTCOME:")
        print(f"    Final pasture stock: {current_stock}/{initial_stock} units")
        if collapsed:
            print(f"    !! ECOSYSTEM COLLAPSED (below {collapse_threshold} threshold) !!")
        else:
            print(f"    Pasture survived (above {collapse_threshold} collapse threshold)")
        print(f"    Total {resource_name} held by herders: {total_held} {resource_unit}")
        print(f"    Gini coefficient:   {self.env.calculate_gini():.2f}")

        print(f"\n  HERDER INVENTORIES:")
        for a in sorted(self.agents, key=lambda x: x.resource, reverse=True):
            bar = "█" * a.resource
            print(f"    {a.name:10s} | {a.resource:2d} {resource_unit} {bar}")

        # Layer 2: Print memory graph summary (episodes + facts + commitments)
        print(f"\n  MEMORY GRAPHS:")
        for a in self.agents:
            ep_count = a.memory.episode_count
            fact_count = a.memory.fact_count
            commit_count = a.memory.commitment_count
            high_importance = sum(
                1 for _, d in a.memory.get_all_episodes()
                if d.get("importance", 0) >= 0.8
            )
            pending_commits = sum(
                1 for _, d in a.memory.get_all_commitments()
                if d.get("status") == "pending"
            )
            print(
                f"    {a.name:10s} | {ep_count} episodes, "
                f"{fact_count} facts, "
                f"{commit_count} commitments ({pending_commits} pending), "
                f"{high_importance} high-importance"
            )

        print(f"\n  (Check the log file for full per-round details)")

        # Phase 5: Print ablation metrics summary
        metrics = self.metrics.finalize()
        print(f"\n  ABLATION METRICS:")
        print(f"    Final Gini:          {metrics['gini_final']:.3f}")
        print(f"    Accountability:      {metrics['accountability_events']} events / {metrics['total_speech_acts']} speech acts")
        print(f"    Accountability rate: {metrics['accountability_rate']:.3f}")
        print(f"    Cooperation rate:    {metrics.get('cooperation_rate_final', 0):.3f}")
        print(f"    Final resource stock: {metrics.get('resource_stock_final', 0)}")
        collapsed = metrics.get('resource_stock_final', 0) < commons_config.get('collapse_threshold', 20)
        print(f"    Commons collapsed:   {'YES' if collapsed else 'NO'}")

        print(f"{'═'*60}\n")

        # Log final summary
        self.logger.log_final_summary({
            "total_distributed": total_held,
            "depot_remaining": self.env.resource_depot,
            "inventories": {a.name: a.resource for a in self.agents},
            "final_locations": {a.name: a.location for a in self.agents},
            "gini": self.env.calculate_gini(),
            "resource_name": resource_name,
            "ablation_metrics": metrics,
        })
