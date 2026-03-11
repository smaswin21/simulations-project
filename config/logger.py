"""
logger.py — Saves structured simulation logs to MongoDB.

Each simulation run is stored as a single document in the 'logs' collection
with config, agent profiles, per-round data, and a final summary.
Agent memory graphs are stored in the separate 'agent_memories' collection.
"""

from datetime import datetime
import config.db as db


class Logger:
    def __init__(self):
        self.simulation_id = None

    def log_config(self, profiles: list[dict], settings: dict):
        """Create the simulation document in MongoDB."""
        self.simulation_id = db.create_simulation(settings, profiles)
        print(f"Simulation ID: {self.simulation_id}")

    def log_round(self, round_data: dict):
        """Append one round's data to the simulation document."""
        if self.simulation_id:
            db.append_round(self.simulation_id, round_data)

    def log_final_summary(self, summary: dict):
        """Mark the simulation as completed and save the final summary."""
        if self.simulation_id:
            db.complete_simulation(self.simulation_id, summary)

    def log_memory_graph(
        self, agent_name: str, graph_data: dict, episode_count: int
    ):
        """
        Persist an agent's memory graph to MongoDB.

        Called after each round by the orchestrator. Uses upsert, so the
        first call creates the document and subsequent calls update it.
        """
        if self.simulation_id:
            db.save_memory_graph(
                self.simulation_id, agent_name, graph_data, episode_count
            )
