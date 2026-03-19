"""
pygame_app.py — Replay stored visualization snapshots with Pygame.
"""

from __future__ import annotations

import argparse

from ui.render import draw_frame, handle_events, load_role_icons
from ui.replay import DEFAULT_ROUND_DURATION_MS, ReplayController, load_replay_rounds
from ui.world import (
    AgentSpriteState,
    apply_round_state,
    generate_map_data,
    init_agent_states,
    render_background_surface,
    update_agent_positions,
)

DEFAULT_WIDTH = 900
DEFAULT_HEIGHT = 600


def run_viewer(
    simulation_id: str,
    rounds: list[dict],
    *,
    round_duration_ms: int = DEFAULT_ROUND_DURATION_MS,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> None:
    import pygame

    pygame.init()
    try:
        screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Village Commons Replay Viewer")
        clock = pygame.time.Clock()
        role_icons = load_role_icons()
        controller = ReplayController(rounds=rounds, round_duration_ms=round_duration_ms)
        tile_map = generate_map_data(simulation_id)
        background_surface = render_background_surface(tile_map, width, height)
        agent_states = init_agent_states(rounds[0], width, height, simulation_id)
        apply_round_state(agent_states, rounds[0], 0)
        running = True

        while running:
            current_ticks = pygame.time.get_ticks()
            previous_index = controller.current_index
            running = handle_events(controller, current_ticks)
            advanced = controller.update(current_ticks)
            if advanced or controller.current_index != previous_index:
                apply_round_state(agent_states, controller.current_round, current_ticks)

            dt_seconds = clock.tick(60) / 1000.0
            update_agent_positions(agent_states, dt_seconds, width, height, simulation_id)
            draw_frame(
                screen,
                background_surface,
                controller.current_round,
                agent_states,
                controller.get_recent_messages(),
                width,
                height,
                role_icons=role_icons,
                paused=controller.paused,
                show_trails=controller.show_trails,
                current_ticks=current_ticks,
            )
            pygame.display.flip()
    finally:
        pygame.quit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulation-id", required=True, help="MongoDB simulation id to replay")
    parser.add_argument(
        "--round-duration-ms",
        type=int,
        default=DEFAULT_ROUND_DURATION_MS,
        help="Milliseconds to show each round",
    )
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help="Window width")
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT, help="Window height")
    args = parser.parse_args()

    rounds = load_replay_rounds(args.simulation_id)
    run_viewer(
        args.simulation_id,
        rounds,
        round_duration_ms=args.round_duration_ms,
        width=args.width,
        height=args.height,
    )


if __name__ == "__main__":
    main()
