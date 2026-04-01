import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import run_simulation
from config.simulation_setup import prepare_scenario
from scripts import run_ablation


class RoundCountSyncTests(unittest.TestCase):
    def test_prepare_scenario_overrides_max_rounds(self):
        scenario = prepare_scenario(
            "simulations/tragedy_of_commons",
            seed=42,
            num_rounds=15,
        )

        self.assertEqual(scenario["simulation"]["max_rounds"], 15)

    @patch("run_simulation._auto_save_memory_plot")
    @patch("run_simulation.Orchestrator")
    @patch("run_simulation.build_simulation_setup")
    @patch("run_simulation.get_embed_model")
    def test_run_simulation_main_passes_num_rounds_to_setup(
        self,
        _embed_model,
        build_setup,
        orchestrator_cls,
        _auto_save_plot,
    ):
        provider = SimpleNamespace(settings=SimpleNamespace(provider="anthropic", model="claude-sonnet-4-6"))
        logger = SimpleNamespace(log_config=Mock(), simulation_id="abc123")
        build_setup.return_value = SimpleNamespace(
            scenario={"simulation": {"name": "Commons Test", "max_rounds": 15}},
            provider=provider,
            agents=[SimpleNamespace(name="Ava"), SimpleNamespace(name="Ben")],
            environment=object(),
            logger=logger,
            role_assignments=[({"name": "Ava"}, "Herder"), ({"name": "Ben"}, "Regulator")],
            cohort_meta={"cohort_label": "diverse_traits", "cohort_type": "diverse"},
        )
        orchestrator = SimpleNamespace(run_simulation=AsyncMock())
        orchestrator_cls.return_value = orchestrator

        asyncio.run(
            run_simulation.main(
                15,
                "simulations/tragedy_of_commons",
                42,
                llm_settings="sentinel-settings",
            )
        )

        build_setup.assert_called_once_with(
            seed=42,
            scenario_dir="simulations/tragedy_of_commons",
            llm_settings="sentinel-settings",
            num_rounds=15,
            cohort_file=None,
            cohort_source=None,
        )
        orchestrator.run_simulation.assert_awaited_once_with(15)

    @patch("scripts.run_ablation.Orchestrator")
    @patch("scripts.run_ablation.build_simulation_setup")
    def test_run_ablation_passes_num_rounds_to_setup(
        self,
        build_setup,
        orchestrator_cls,
    ):
        provider = SimpleNamespace(settings=SimpleNamespace(provider="anthropic", model="claude-sonnet-4-6"))
        logger = SimpleNamespace()
        build_setup.return_value = SimpleNamespace(
            scenario={"simulation": {"name": "Commons Test", "max_rounds": 20}},
            provider=provider,
            agents=[SimpleNamespace(name="Ava"), SimpleNamespace(name="Ben")],
            environment=object(),
            logger=logger,
            cohort_meta={"cohort_label": "diverse_traits", "cohort_type": "diverse"},
        )
        orchestrator = SimpleNamespace(
            run_simulation=AsyncMock(),
            get_metrics_summary=Mock(return_value={"resource_stock_over_time": [120]}),
        )
        orchestrator_cls.return_value = orchestrator

        asyncio.run(
            run_ablation.run_single(
                seed=42,
                condition="B",
                num_rounds=20,
                scenario_dir="simulations/tragedy_of_commons",
                llm_settings="sentinel-settings",
            )
        )

        build_setup.assert_called_once_with(
            seed=42,
            scenario_dir="simulations/tragedy_of_commons",
            llm_settings="sentinel-settings",
            num_rounds=20,
            cohort_file=None,
            cohort_source=None,
            seed_context={"condition": "B"},
        )
        orchestrator.run_simulation.assert_awaited_once_with(20)


if __name__ == "__main__":
    unittest.main()
