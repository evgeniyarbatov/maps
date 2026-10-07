import importlib
import unittest
from pathlib import Path
from unittest import mock

import scripts.config as config


class ConfigDefaultsTests(unittest.TestCase):
    def tearDown(self) -> None:
        importlib.reload(config)

    def test_defaults_when_env_unset(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            importlib.reload(config)

        self.assertEqual(config.BUFFER_KM, 0.25)
        self.assertEqual(config.OLLAMA_URL, "http://localhost:11434")
        self.assertEqual(config.OLLAMA_MODEL, "mistral-nemo")
        self.assertEqual(config.MAP_DPI, 300)
        self.assertEqual(config.OSM_DIR, config.REPO_ROOT / "osm")
        self.assertEqual(config.DATA_DIR, config.REPO_ROOT / "data")
        self.assertEqual(config.OSM_EXTRACT, config.OSM_DIR / "extract.osm")
        self.assertEqual(config.COUNTRY_OSM_FILE.name, "vietnam-latest.osm.pbf")

    def test_env_vars_override_defaults(self) -> None:
        overrides = {
            "BUFFER_KM": "1.5",
            "OLLAMA_URL": "http://example.test:1234",
            "OLLAMA_MODEL": "llama3",
            "MAP_DPI": "150",
            "DATA_DIR": "/tmp/run-42",
            "OSM_DIR": "/tmp/run-42/osm",
        }
        with mock.patch.dict("os.environ", overrides, clear=False):
            importlib.reload(config)

        self.assertEqual(config.BUFFER_KM, 1.5)
        self.assertEqual(config.OLLAMA_URL, "http://example.test:1234")
        self.assertEqual(config.OLLAMA_MODEL, "llama3")
        self.assertEqual(config.MAP_DPI, 150)
        self.assertEqual(config.DATA_DIR, Path("/tmp/run-42"))
        self.assertEqual(config.OSM_DIR, Path("/tmp/run-42/osm"))
        self.assertEqual(config.OSM_EXTRACT, config.OSM_DIR / "extract.osm")


if __name__ == "__main__":
    unittest.main()
