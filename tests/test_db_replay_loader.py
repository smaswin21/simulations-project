import unittest
from unittest.mock import patch

import config.db as db


class ReplayLoaderTests(unittest.TestCase):
    def test_get_simulation_rounds_returns_rounds(self):
        fake_collection = type(
            "FakeCollection",
            (),
            {
                "find_one": lambda self, query, projection: {
                    "rounds": [{"round": 1}, {"round": 2}]
                }
            },
        )()

        with patch("config.db.get_logs_collection", return_value=fake_collection):
            rounds = db.get_simulation_rounds("507f1f77bcf86cd799439011")

        self.assertEqual([round_doc["round"] for round_doc in rounds], [1, 2])

    def test_get_simulation_rounds_rejects_unknown_simulation(self):
        fake_collection = type(
            "FakeCollection",
            (),
            {"find_one": lambda self, query, projection: None},
        )()

        with patch("config.db.get_logs_collection", return_value=fake_collection):
            with self.assertRaisesRegex(ValueError, "was not found"):
                db.get_simulation_rounds("507f1f77bcf86cd799439011")

    def test_get_simulation_rounds_rejects_missing_rounds(self):
        fake_collection = type(
            "FakeCollection",
            (),
            {"find_one": lambda self, query, projection: {"rounds": []}},
        )()

        with patch("config.db.get_logs_collection", return_value=fake_collection):
            with self.assertRaisesRegex(ValueError, "has no rounds"):
                db.get_simulation_rounds("507f1f77bcf86cd799439011")


if __name__ == "__main__":
    unittest.main()
