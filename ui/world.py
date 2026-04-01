"""
World generation and agent simulation state for the Pygame viewer.
"""

from __future__ import annotations

import hashlib
import random
from collections import deque
from dataclasses import dataclass, field

HUD_HEIGHT = 84
WORLD_W = 60
WORLD_H = 40
TRAIL_LENGTH = 100
SPEECH_BUBBLE_MS = 1500
AGENT_RADIUS = 9
AGENT_SPEED_MIN = 44.0
AGENT_SPEED_MAX = 76.0
BACKGROUND_COLOR = (204, 193, 164)
GRASS_VARIANTS = [(93, 148, 67), (111, 164, 82), (120, 170, 88)]
TAN_VARIANTS = [(184, 156, 108), (195, 168, 119), (169, 142, 98)]


def _stable_seed(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


@dataclass
class AgentSpriteState:
    agent_id: int
    x: float
    y: float
    target_x: float
    target_y: float
    speed: float
    role: str
    name: str = ""
    grazed: int = 0
    speaking_until_ms: int = 0
    trail: deque[tuple[float, float]] = field(
        default_factory=lambda: deque(maxlen=TRAIL_LENGTH)
    )


def get_world_rect(width: int, height: int) -> tuple[int, int, int, int]:
    return (0, HUD_HEIGHT, width, max(0, height - HUD_HEIGHT))


def generate_map_data(
    simulation_id: str,
    world_w: int = WORLD_W,
    world_h: int = WORLD_H,
) -> list[list[str]]:
    rng = random.Random(_stable_seed(simulation_id))
    tile_map = [["grass" for _ in range(world_w)] for _ in range(world_h)]

    patch_count = max(8, (world_w * world_h) // 110)
    for _ in range(patch_count):
        patch_w = rng.randint(3, 9)
        patch_h = rng.randint(2, 7)
        start_x = rng.randint(0, max(0, world_w - patch_w))
        start_y = rng.randint(0, max(0, world_h - patch_h))
        for y in range(start_y, start_y + patch_h):
            for x in range(start_x, start_x + patch_w):
                if 0 <= x < world_w and 0 <= y < world_h:
                    tile_map[y][x] = "tan"
    return tile_map


def render_background_surface(tile_map: list[list[str]], width: int, height: int):
    import pygame

    _, world_y, world_width, world_height = get_world_rect(width, height)
    tile_width = max(1, world_width // max(1, len(tile_map[0])))
    tile_height = max(1, world_height // max(1, len(tile_map)))
    background = pygame.Surface((width, height))
    background.fill(BACKGROUND_COLOR)

    grass_rng = random.Random(len(tile_map) * 1000 + len(tile_map[0]))
    for row_index, row in enumerate(tile_map):
        for col_index, tile in enumerate(row):
            palette = TAN_VARIANTS if tile == "tan" else GRASS_VARIANTS
            color = palette[grass_rng.randrange(len(palette))]
            background.fill(
                color,
                (
                    col_index * tile_width,
                    world_y + (row_index * tile_height),
                    tile_width,
                    tile_height,
                ),
            )

    return background


def _random_point_in_world(
    rng: random.Random,
    width: int,
    height: int,
) -> tuple[float, float]:
    world_x, world_y, world_width, world_height = get_world_rect(width, height)
    min_x = world_x + AGENT_RADIUS + 4
    max_x = world_x + world_width - AGENT_RADIUS - 4
    min_y = world_y + AGENT_RADIUS + 4
    max_y = world_y + world_height - AGENT_RADIUS - 4
    return (
        rng.uniform(min_x, max(min_x, max_x)),
        rng.uniform(min_y, max(min_y, max_y)),
    )


def init_agent_states(
    first_round: dict,
    width: int,
    height: int,
    simulation_id: str,
) -> dict[int, AgentSpriteState]:
    rng = random.Random(_stable_seed(f"{simulation_id}:agents"))
    agent_states: dict[int, AgentSpriteState] = {}
    for agent in first_round.get("agents", []):
        x, y = _random_point_in_world(rng, width, height)
        target_x, target_y = _random_point_in_world(rng, width, height)
        state = AgentSpriteState(
            agent_id=agent["id"],
            x=x,
            y=y,
            target_x=target_x,
            target_y=target_y,
            speed=rng.uniform(AGENT_SPEED_MIN, AGENT_SPEED_MAX),
            role=agent.get("role", "Herder"),
            name=agent.get("name", f"Agent {agent['id']}"),
        )
        state.trail.append((x, y))
        agent_states[agent["id"]] = state
    return agent_states


def apply_round_state(
    agent_states: dict[int, AgentSpriteState],
    round_data: dict,
    current_ticks: int,
) -> None:
    round_agent_ids = {agent["id"] for agent in round_data.get("agents", [])}
    for agent_id in list(agent_states):
        if agent_id not in round_agent_ids:
            del agent_states[agent_id]

    for agent in round_data.get("agents", []):
        state = agent_states.get(agent["id"])
        if state is None:
            continue
        state.role = agent.get("role", state.role)
        state.name = agent.get("name", state.name)
        state.grazed = agent.get("grazed", 0)
        if agent.get("speaking"):
            state.speaking_until_ms = current_ticks + SPEECH_BUBBLE_MS


def update_agent_positions(
    agent_states: dict[int, AgentSpriteState],
    dt_seconds: float,
    width: int,
    height: int,
    simulation_id: str,
) -> None:
    rng = random.Random(_stable_seed(f"{simulation_id}:motion"))
    for agent_id in sorted(agent_states):
        state = agent_states[agent_id]
        dx = state.target_x - state.x
        dy = state.target_y - state.y
        distance = (dx * dx + dy * dy) ** 0.5
        if distance < 4.0:
            state.target_x, state.target_y = _random_point_in_world(rng, width, height)
            dx = state.target_x - state.x
            dy = state.target_y - state.y
            distance = (dx * dx + dy * dy) ** 0.5

        if distance > 0:
            step = min(state.speed * dt_seconds, distance)
            state.x += (dx / distance) * step
            state.y += (dy / distance) * step

        state.trail.append((state.x, state.y))
