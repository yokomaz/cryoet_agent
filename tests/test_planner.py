from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryoet_agent.agent.planner import CryoETPlanner
from cryoet_agent.agent.schemas import PlanningRequest


class PlannerTests(unittest.TestCase):
    def test_planner_generates_reconstruction_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            (data / "frames_001.eer").write_text("x")
            (data / "tilts.mdoc").write_text("x")
            with patch("cryoet_agent.config.workspace_root", return_value=root), patch(
                "cryoet_agent.introspection.scanner.workspace_root", return_value=root
            ):
                planner = CryoETPlanner(model_provider="none")
                result = planner.plan(
                    PlanningRequest(
                        user_message="I want to reconstruct tomograms from the dataset at ./data.",
                        dataset_path="data",
                    )
                )

        self.assertIn("reconstruct_tomogram", result.plan.normalized_goals)
        self.assertTrue(any("reconstruct" in step.title.lower() or "align" in step.title.lower() for step in result.plan.steps))


if __name__ == "__main__":
    unittest.main()

