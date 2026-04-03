from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryoet_agent.introspection.scanner import scan_workspace


class ScannerTests(unittest.TestCase):
    def test_scan_detects_raw_movies_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            (data / "tilt_001.eer").write_text("x")
            (data / "series.mdoc").write_text("x")
            with patch("cryoet_agent.config.workspace_root", return_value=root), patch(
                "cryoet_agent.introspection.scanner.workspace_root", return_value=root
            ):
                state = scan_workspace("data")

        self.assertEqual(state.inferred_stage, "raw_tilt_movies")
        self.assertIn("raw_movie", state.detected_modalities)
        self.assertIn("metadata", state.detected_modalities)
        self.assertFalse(state.missing_requirements)


if __name__ == "__main__":
    unittest.main()

