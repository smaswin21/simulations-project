"""
orchestrator.py — Main simulation loop for heterogeneous MASTOC runs.
"""

import asyncio
import json
from pathlib import Path

from agent_flow.action_parser import parse_action
from agent_flow.fact_extractor import extract_beliefs
from agent_flow.environment import _get_act
from config.config import MAX_CONCURRENT_AGENTS
from metrics.collector import MetricsCollector

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


class Orchestrator:
    def __init__(
        self,
        agents,
        environment,
        logger,
        llm_provider,
        scenario: dict,
        condition: str = "",
        seed: int = 0,
    ):
        self.agents = agents
        self.env = environment
        self.logger = logger
        self.llm_provider = llm_provider
        self.scenario = scenario
        self.rules = scenario.get("rules")
        self.metrics = MetricsCollector(agent_names=[agent.name for agent in agents])

        RESULTS_DIR.mkdir(exist_ok=True)
        tag = f"_{condition}_{seed}" if condition else ""
        self._speech_log_path = RESULTS_DIR / f"speech_log{tag}.jsonl"

    async def run_round(self):
        self.env.round_number += 1
        round_num = self.env.round_number

        sanction_messages = self.env.apply_pending_sanctions()
        rule_messages = self.rules.apply_round_events(self.env, round_num, self.scenario) if self.rules else []
        self.env.set_round_messages(sanction_messages + rule_messages)

        perceptions = {
            agent.name: self.env.generate_perception(agent)
            for agent in self.agents
        }

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_AGENTS)

        async def _agent_decide(agent):
            async with semaphore:
                try:
                    nearby = self.env.get_agents_at_location(agent.location, exclude=agent.name)
                    decision = await agent.decide(
                        perception=perceptions[agent.name],
                        round_num=round_num,
                        nearby_agents=nearby,
                    )
                    return agent.name, decision
                except Exception as exc:
                    return agent.name, {
                        "agent": agent.name,
                        "role": agent.role,
                        "reflection": f"Decision failed: {exc}",
                        "message": "NONE",
                        "action_text": "WAIT",
                        "reflection_raw": "",
                        "response_raw": "",
                        "retrieved_labels": [],
                    }

        results = await asyncio.gather(*[_agent_decide(agent) for agent in self.agents])

        actions = []
        agent_logs = []
        decision_map = {}

        for agent_name, decision in results:
            agent = self.env.agents[agent_name]
            decision_map[agent_name] = decision
            others_here = [
                other.name
                for other in self.env.agents.values()
                if other.location == agent.location and other.name != agent.name
            ]
            parsed = parse_action(
                action_text=decision["action_text"],
                agent_name=agent_name,
                agent_role=agent.role,
                agent_location=agent.location,
                agents_at_location=others_here,
            )
            parsed["message"] = decision["message"]
            parsed["reflection"] = decision["reflection"]
            actions.append(parsed)

            agent_logs.append(
                {
                    "agent": agent_name,
                    "role": agent.role,
                    "location": agent.location,
                    "perception_snippet": perceptions[agent_name][:200] + "...",
                    "reflection": decision["reflection"][:300],
                    "message": decision["message"][:200],
                    "action_type": parsed["type"],
                    "action_text": decision["action_text"],
                    "invalid_reason": parsed.get("invalid_reason", ""),
                    "retrieved_labels": decision.get("retrieved_labels", []),
                    "raw_response": decision["response_raw"][:500],
                }
            )

        outcomes = self.env.resolve_actions(actions)

        inventories = {agent.name: agent.resource for agent in self.agents}
        self.metrics.update_round(round_num, outcomes, inventories)
        sustainable_quota = self.scenario.get("commons", {}).get("suggested_quota_per_agent", 1)
        self.metrics.update_cooperation_rate(self.env.round_harvest_actions, sustainable_quota)
        self.metrics.update_resource_stock(self.env._get_depot_resource())
        cooperation_rate = (
            self.metrics.cooperation_rate_over_time[-1]
            if self.metrics.cooperation_rate_over_time
            else 1.0
        )

        speech_records = []
        for outcome in outcomes:
            if outcome.get("action") not in {"message", "report"}:
                continue
            speech_records.append(
                {
                    "round": round_num,
                    "speaker": outcome.get("agent", ""),
                    "detail": outcome.get("detail", ""),
                    "location": self.env.agents[outcome["agent"]].location
                    if outcome.get("agent") in self.env.agents
                    else "",
                }
            )
        if speech_records:
            with open(self._speech_log_path, "a", encoding="utf-8") as handle:
                for record in speech_records:
                    handle.write(json.dumps(record) + "\n")

        for agent in self.agents:
            agent_location = agent.location
            relevant_outcomes = [
                outcome
                for outcome in outcomes
                if (
                    outcome.get("agent") == agent.name
                    or agent.name in outcome.get("detail", "")
                    or self._agent_was_at_location(outcome.get("agent"), agent_location)
                )
            ]

            decision = decision_map[agent.name]
            episode_text = "\n".join(
                [
                    perceptions[agent.name],
                    "",
                    f"REFLECTION:: {decision['reflection']}",
                    f"MESSAGE:: {decision['message']}",
                    f"ACTION:: {decision['action_text']}",
                ]
            )
            episode_id = agent.memory.add_episode(
                round_num=round_num,
                perception_text=episode_text,
                outcomes=relevant_outcomes,
            )

            await extract_beliefs(
                memory=agent.memory,
                episode_id=episode_id,
                round_num=round_num,
                outcomes=relevant_outcomes,
                agent_inventories=inventories,
                llm_provider=self.llm_provider,
            )

        self.logger.log_round(
            {
                "round": round_num,
                "world_state": self.env.get_world_state(),
                "visualization_state": self.env.get_visualization_state(
                    cooperation_rate=cooperation_rate,
                    outcomes=outcomes,
                ),
                "agent_actions": agent_logs,
                "outcomes": outcomes,
            }
        )

        for agent in self.agents:
            self.logger.log_memory_graph(
                agent.name,
                agent.memory.to_dict(),
                agent.memory.episode_count,
            )

        self._print_summary(round_num, actions, outcomes)

    def _agent_was_at_location(self, agent_name: str, location: str) -> bool:
        if agent_name is None:
            return False
        agent = self.env.agents.get(agent_name)
        return agent is not None and agent.location == location

    async def run_simulation(self, num_rounds: int):
        sim_name = self.scenario.get("simulation", {}).get("name", "Simulation")
        print(f"\n{'━' * 60}")
        print(f"  {sim_name.upper()} — {len(self.agents)} agents, {num_rounds} rounds")
        print(f"{'━' * 60}\n")

        for _ in range(num_rounds):
            await self.run_round()

        for agent in self.agents:
            self.logger.log_memory_graph(
                agent.name,
                agent.memory.to_dict(),
                agent.memory.episode_count,
            )
        self._print_final_summary()

    def get_metrics_summary(self) -> dict:
        return self.metrics.finalize()

    def _print_summary(self, round_num: int, actions: list[dict], outcomes: list[dict]):
        act_label, act_desc = _get_act(round_num, self.scenario)
        print(f"\n{'━' * 50}")
        print(f"  ROUND {round_num}/{self.env.max_rounds} (Act {act_label}: {act_desc})")
        print(f"{'━' * 50}")

        for message in self.env.round_messages:
            print(f"  {message}")

        print("\n  COMMONS STATUS:")
        print(f"    Stock: {self.env._get_depot_resource()}/{self.env.resource_supply}")
        print(f"    Regeneration: {self.env.current_regeneration_rate} units/round")
        print(f"    Last round grazed: {self.env._last_round_total_grazed}")
        print(f"    Gini: {self.env.calculate_gini():.2f}")

        for location in self.scenario.get("locations", []):
            location_name = location.get("name")
            agents_here = [agent for agent in self.agents if agent.location == location_name]
            if not agents_here:
                continue
            print(f"\n  {location_name} ({len(agents_here)} agents)")
            for agent in agents_here:
                action = next((item for item in actions if item["agent"] == agent.name), None)
                if not action:
                    continue
                label = action["type"].upper()
                if action["type"] == "graze":
                    label = f"GRAZE {action.get('amount', '?')}"
                elif action["type"] == "move":
                    label = f"MOVE -> {action.get('target_location')}"
                elif action["type"] == "sanction":
                    label = f"SANCTION {action.get('target_agent')}"
                elif action["type"] == "report":
                    label = "REPORT_DATA"
                print(f"    {agent.name} ({agent.role}): {label}")

        print(f"\n  Resource depot: {self.env.resource_depot}")
        print(f"{'━' * 50}")

    def _print_final_summary(self):
        print(f"\n{'═' * 60}")
        print("  SIMULATION COMPLETE")
        print(f"{'═' * 60}")

        current_stock = self.env._get_depot_resource()
        total_held = sum(agent.resource for agent in self.agents)
        metrics = self.metrics.finalize()

        print("\n  COMMONS OUTCOME:")
        print(f"    Final stock: {current_stock}/{self.env.resource_supply}")
        print(f"    Total held by agents: {total_held}")
        print(f"    Gini coefficient: {self.env.calculate_gini():.2f}")

        print("\n  AGENT INVENTORIES:")
        for agent in sorted(self.agents, key=lambda item: item.resource, reverse=True):
            print(f"    {agent.name:10s} ({agent.role:9s}) | {agent.resource:2d}")

        print("\n  MEMORY GRAPHS:")
        for agent in self.agents:
            high_importance = sum(
                1
                for _, data in agent.memory.get_all_episodes()
                if data.get("importance", 0) >= 0.8
            )
            print(
                f"    {agent.name:10s} | {agent.memory.episode_count} episodes, "
                f"{agent.memory.fact_count} beliefs, {high_importance} high-importance"
            )

        self.logger.log_final_summary(
            {
                "total_distributed": total_held,
                "depot_remaining": self.env.resource_depot,
                "inventories": {agent.name: agent.resource for agent in self.agents},
                "final_locations": {agent.name: agent.location for agent in self.agents},
                "roles": {agent.name: agent.role for agent in self.agents},
                "gini": self.env.calculate_gini(),
                "ablation_metrics": metrics,
            }
        )
