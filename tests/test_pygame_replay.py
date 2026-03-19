import importlib.util
import os
import unittest
from collections import deque
from unittest.mock import patch

from ui.pygame_app import (
    AgentSpriteState,
    ReplayController,
    apply_round_state,
    draw_frame,
    generate_map_data,
    handle_events,
    init_agent_states,
    load_replay_rounds,
    update_agent_positions,
)
from ui.render import load_role_icons
from ui.replay import load_replay_rounds


class ReplayModelTests(unittest.TestCase):
    def test_loader_extracts_messages_from_round_docs(self):
        round_docs = [
            {
                "round": 1,
                "visualization_state": {
                    "round": 1,
                    "stock": 120,
                    "total_grazed": 2,
                    "cooperation_rate": 0.5,
                    "agents": [
                        {
                            "id": 0,
                            "name": "Ava",
                            "role": "Herder",
                            "location": "Pasture",
                            "inventory": 2,
                            "grazed": 2,
                            "speaking": False,
                        }
                    ],
                },
                "outcomes": [
                    {"agent": "Ava", "action": "message", "detail": "We should slow down."},
                    {"agent": "Ava", "action": "graze", "detail": "Grazed 2 units"},
                ],
            }
        ]

        with patch("ui.replay.db.get_simulation_rounds", return_value=round_docs):
            rounds = load_replay_rounds("507f1f77bcf86cd799439011")

        self.assertEqual(rounds[0]["round"], 1)
        self.assertEqual(rounds[0]["coop_rate"], 0.5)
        self.assertEqual(rounds[0]["messages"][0]["agent_id"], 0)
        self.assertEqual(len(rounds[0]["messages"]), 1)

    def test_controller_controls_and_message_history(self):
        rounds = [
            {"round": 1, "messages": [{"speaker": "Ava", "text": "One"}]},
            {"round": 2, "messages": [{"speaker": "Ben", "text": "Two"}]},
            {"round": 3, "messages": [{"speaker": "Cy", "text": "Three"}]},
        ]
        controller = ReplayController(rounds=rounds, round_duration_ms=100)

        controller.update(100)
        self.assertEqual(controller.current_index, 1)
        self.assertEqual(len(controller.get_recent_messages()), 2)

        controller.prev_round(120)
        self.assertTrue(controller.paused)
        self.assertEqual(controller.current_index, 0)
        self.assertEqual([msg["text"] for msg in controller.get_recent_messages()], ["One"])

        controller.next_round(130)
        controller.restart(140)
        self.assertEqual(controller.current_index, 0)
        controller.toggle_trails()
        self.assertFalse(controller.show_trails)

    def test_map_generation_is_deterministic(self):
        first = generate_map_data("sim-123")
        second = generate_map_data("sim-123")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 40)
        self.assertEqual(len(first[0]), 60)

    def test_agent_motion_stays_bounded_and_trails_cap(self):
        first_round = {
            "agents": [
                {"id": 0, "role": "Herder", "grazed": 1, "speaking": False},
            ]
        }
        agent_states = init_agent_states(first_round, 900, 600, "sim-123")
        apply_round_state(
            agent_states,
            {
                "agents": [
                    {"id": 0, "role": "Scout", "grazed": 2, "speaking": True},
                ]
            },
            10,
        )
        state = agent_states[0]
        self.assertEqual(state.role, "Scout")
        self.assertEqual(state.grazed, 2)
        self.assertGreater(state.speaking_until_ms, 10)

        for _ in range(150):
            update_agent_positions(agent_states, 0.016, 900, 600, "sim-123")

        self.assertLessEqual(len(state.trail), 100)
        self.assertGreaterEqual(state.x, 0)
        self.assertGreaterEqual(state.y, 84)


@unittest.skipIf(importlib.util.find_spec("pygame") is None, "pygame is not installed")
class PygameReplayTests(unittest.TestCase):
    def test_draw_frame_with_role_icons_and_key_controls(self):
        with patch.dict(os.environ, {"SDL_VIDEODRIVER": "dummy"}, clear=False):
            import pygame

            pygame.init()
            try:
                screen = pygame.display.set_mode((900, 600))
                background = pygame.Surface((900, 600))
                background.fill((0, 0, 0))
                controller = ReplayController(
                    rounds=[
                        {
                            "round": 1,
                            "stock": 120,
                            "total_grazed": 0,
                            "coop_rate": 1.0,
                            "agents": [],
                            "messages": [],
                        },
                        {
                            "round": 2,
                            "stock": 118,
                            "total_grazed": 2,
                            "coop_rate": 0.5,
                            "agents": [],
                            "messages": [{"speaker": "Ava", "text": "Hello"}],
                        },
                    ],
                    round_duration_ms=100,
                )
                agent_state = AgentSpriteState(
                    agent_id=0,
                    x=100,
                    y=120,
                    target_x=120,
                    target_y=140,
                    speed=60.0,
                    role="Herder",
                    trail=deque([(100, 120), (103, 123)], maxlen=100),
                )
                agent_state.speaking_until_ms = 500
                role_icons = {
                    "Herder": pygame.Surface((20, 20), pygame.SRCALPHA),
                    "Regulator": None,
                    "Scout": None,
                }
                role_icons["Herder"].fill((255, 255, 255, 255))
                draw_frame(
                    screen,
                    background,
                    controller.current_round,
                    {0: agent_state},
                    [{"speaker": "Ava", "text": "Hello"}],
                    900,
                    600,
                    role_icons=role_icons,
                    paused=False,
                    show_trails=True,
                    current_ticks=100,
                )

                draw_frame(
                    screen,
                    background,
                    controller.current_round,
                    {0: agent_state},
                    [{"speaker": "Ava", "text": "Hello"}],
                    900,
                    600,
                    role_icons={"Herder": None, "Regulator": None, "Scout": None},
                    paused=False,
                    show_trails=True,
                    current_ticks=100,
                )

                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
                self.assertTrue(handle_events(controller, 100))
                self.assertTrue(controller.paused)

                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
                self.assertTrue(handle_events(controller, 120))
                self.assertEqual(controller.current_index, 1)

                pygame.event.post(pygame.event.Event(pygame.QUIT))
                self.assertFalse(handle_events(controller, 140))
            finally:
                pygame.quit()

    def test_load_role_icons_tolerates_missing_assets(self):
        with patch.dict(os.environ, {"SDL_VIDEODRIVER": "dummy"}, clear=False):
            import pygame

            pygame.init()
            try:
                pygame.display.set_mode((1, 1))
                icons = load_role_icons()
                self.assertIn("Herder", icons)
                self.assertIn("Regulator", icons)
                self.assertIn("Scout", icons)
                self.assertTrue(any(surface is not None for surface in icons.values()))
            finally:
                pygame.quit()


if __name__ == "__main__":
    unittest.main()
