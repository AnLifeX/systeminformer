import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


class UpdaterChangelogTests(unittest.TestCase):
    def test_changelog_reuses_metadata_from_the_version_check(self):
        header = (ROOT / "plugins" / "Updater" / "updater.h").read_text(
            encoding="utf-8"
        )
        updater = (ROOT / "plugins" / "Updater" / "updater.c").read_text(
            encoding="utf-8"
        )
        options = (ROOT / "plugins" / "Updater" / "options.c").read_text(
            encoding="utf-8"
        )

        self.assertIn("PPH_BYTES UpdateData;", header)
        self.assertGreaterEqual(
            updater.count("PhMoveReference(&context->UpdateData, jsonString);"), 1
        )
        self.assertIn("PhMoveReference(&Context->UpdateData, jsonString);", updater)
        self.assertIn(
            "PhpUpdaterQueryCommitHistory(\n    _In_ PPH_BYTES JsonString", options
        )
        self.assertIn(
            "PhpUpdaterQueryCommitHistory(updater->UpdateData)", options
        )
        self.assertNotIn(
            "/AnLifeX/systeminformer/releases/latest/download/systeminformer-update.json",
            options,
        )
        self.assertNotIn("PhHttpInitialize", options)


if __name__ == "__main__":
    unittest.main()
