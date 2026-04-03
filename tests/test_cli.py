from __future__ import annotations

import unittest

from cryoet_agent.cli import infer_dataset_path


class CliTests(unittest.TestCase):
    def test_infer_dataset_path_from_message(self) -> None:
        self.assertEqual(
            infer_dataset_path("I have dataset at ./data and want to do STA."),
            "./data",
        )


if __name__ == "__main__":
    unittest.main()
