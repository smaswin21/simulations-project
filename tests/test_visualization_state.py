import unittest
from types import SimpleNamespace

from agent_flow.environment import Environment


class VisualizationStateTests(unittest.TestCase):
    def setUp(self):
        config = {
            "simulation": {"max_rounds": 5},
            "locations": [
                {"name": "Village Council", "starting_location": True},
                {"name": "Pasture"},
            ],
            "resource": {
                "name": "grazing_units",
                "unit": "units",
                "location": "Pasture",
                "initial_supply": 120,
            },
            "commons": {
                "regeneration_per_round": 12,
                "collapse_threshold": 20,
                "max_stock": 120,
            },
        }
        agents = [
            SimpleNamespace(name="Ava", role="Herder", location="", resource=0),
            SimpleNamespace(name="Ben", role="Regulator", location="", resource=0),
            SimpleNamespace(name="Cy", role="Scout", location="", resource=0),
        ]
        self.env = Environment(agents, config)
        self.env.round_number = 3
        self.env._set_location("Ava", "Pasture")
        self.env._set_resource("Ava", 2)
        self.env._set_resource("Ben", 1)
        self.env._set_resource("Cy", 0)
        self.env.round_harvest_actions = [{"agent": "Ava", "amount": 2}]
        self.env._last_round_total_grazed = 2

    def test_visualization_state_contains_expected_fields(self):
        outcomes = [
            {"agent": "Ben", "action": "message", "detail": "Slow down."},
            {"agent": "Cy", "action": "report", "detail": "stock=118"},
        ]

        state = self.env.get_visualization_state(0.5, outcomes)

        self.assertEqual(state["round"], 3)
        self.assertEqual(state["stock"], 120)
        self.assertEqual(state["total_grazed"], 2)
        self.assertEqual(state["cooperation_rate"], 0.5)
        self.assertEqual([agent["id"] for agent in state["agents"]], [0, 1, 2])

        ava, ben, cy = state["agents"]
        self.assertEqual(ava["location"], "Pasture")
        self.assertEqual(ava["inventory"], 2)
        self.assertEqual(ava["grazed"], 2)
        self.assertFalse(ava["speaking"])

        self.assertEqual(ben["role"], "Regulator")
        self.assertEqual(ben["grazed"], 0)
        self.assertTrue(ben["speaking"])

        self.assertEqual(cy["role"], "Scout")
        self.assertTrue(cy["speaking"])


if __name__ == "__main__":
    unittest.main()
