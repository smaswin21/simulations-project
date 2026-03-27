"""
Replay loading and playback state for the Pygame viewer.
"""

from __future__ import annotations

from dataclasses import dataclass

import config.db as db

DEFAULT_ROUND_DURATION_MS = 1500
MESSAGE_LIMIT = 10


@dataclass
class ReplayController:
    rounds: list[dict]
    round_duration_ms: int = DEFAULT_ROUND_DURATION_MS
    current_index: int = 0
    last_advance_ms: int = 0
    paused: bool = False
    show_trails: bool = True
    message_scroll_offset: int = 0
    selected_agent_id: int | None = None

    def __post_init__(self) -> None:
        if not self.rounds:
            raise ValueError("Replay viewer requires at least one round.")

    @property
    def current_round(self) -> dict:
        return self.rounds[self.current_index]

    def update(self, current_ticks: int) -> bool:
        if self.paused or self.current_index >= len(self.rounds) - 1:
            return False
        if current_ticks - self.last_advance_ms >= self.round_duration_ms:
            self.current_index += 1
            self.last_advance_ms = current_ticks
            self.message_scroll_offset = 0
            return True
        return False

    def next_round(self, current_ticks: int) -> bool:
        self.paused = True
        if self.current_index >= len(self.rounds) - 1:
            return False
        self.current_index += 1
        self.last_advance_ms = current_ticks
        self.message_scroll_offset = 0
        return True

    def prev_round(self, current_ticks: int) -> bool:
        self.paused = True
        if self.current_index == 0:
            return False
        self.current_index -= 1
        self.last_advance_ms = current_ticks
        self.message_scroll_offset = 0
        return True

    def restart(self, current_ticks: int) -> bool:
        self.paused = True
        changed = self.current_index != 0
        self.current_index = 0
        self.last_advance_ms = current_ticks
        self.message_scroll_offset = 0
        return changed

    def toggle_pause(self, current_ticks: int) -> None:
        self.paused = not self.paused
        self.last_advance_ms = current_ticks

    def toggle_trails(self) -> None:
        self.show_trails = not self.show_trails

    def get_agent_total_grazed(self, agent_id: int) -> int:
        total = 0
        for round_data in self.rounds[: self.current_index + 1]:
            for agent in round_data.get("agents", []):
                if agent["id"] == agent_id:
                    total += agent.get("grazed", 0)
        return total

    def get_agent_last_message(self, agent_id: int) -> str | None:
        for round_data in reversed(self.rounds[: self.current_index + 1]):
            for msg in reversed(round_data.get("messages", [])):
                if msg.get("agent_id") is not None and msg["agent_id"] == agent_id:
                    return msg["text"]
        return None

    def get_recent_messages(self, limit: int = MESSAGE_LIMIT) -> list[dict]:
        messages: list[dict] = []
        for round_data in self.rounds[: self.current_index + 1]:
            messages.extend(round_data.get("messages", []))
        return messages[-limit:]


def load_replay_rounds(simulation_id: str) -> list[dict]:
    rounds = db.get_simulation_rounds(simulation_id)
    viewer_rounds = []
    for round_doc in rounds:
        snapshot = round_doc.get("visualization_state")
        round_num = round_doc.get("round", "?")
        if snapshot is None:
            raise ValueError(
                f"Simulation '{simulation_id}' is missing visualization_state for round {round_num}."
            )

        name_to_id = {
            agent["name"]: agent["id"]
            for agent in snapshot.get("agents", [])
        }
        messages = []
        for outcome in round_doc.get("outcomes", []):
            if outcome.get("action") not in {"message", "report"}:
                continue
            messages.append(
                {
                    "agent_id": name_to_id.get(outcome.get("agent", "")),
                    "speaker": outcome.get("agent", ""),
                    "text": outcome.get("detail", ""),
                }
            )

        viewer_rounds.append(
            {
                "round": snapshot["round"],
                "stock": snapshot["stock"],
                "total_grazed": snapshot["total_grazed"],
                "coop_rate": snapshot.get("cooperation_rate", 1.0),
                "agents": list(snapshot.get("agents", [])),
                "messages": messages,
            }
        )
    return viewer_rounds
