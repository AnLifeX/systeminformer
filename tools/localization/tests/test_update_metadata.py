import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools" / "localization" / "New-UpdateMetadata.ps1"
POWERSHELL = shutil.which("pwsh")
OPENSSL = shutil.which("openssl")


@unittest.skipUnless(
    POWERSHELL and OPENSSL,
    "PowerShell and OpenSSL are required for update metadata tests",
)
class UpdateMetadataTests(unittest.TestCase):
    def test_metadata_contains_parseable_commit_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            setup_path = temporary_path / "setup.exe"
            output_path = temporary_path / "systeminformer-update.json"
            key_path = temporary_path / "update-key.pem"
            setup_path.write_bytes(b"localized setup payload")

            subprocess.run(
                [
                    OPENSSL,
                    "genpkey",
                    "-algorithm",
                    "EC",
                    "-pkeyopt",
                    "ec_paramgen_curve:P-256",
                    "-out",
                    str(key_path),
                ],
                check=True,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                check=True,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.strip()

            subprocess.run(
                [
                    POWERSHELL,
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-File",
                    str(SCRIPT),
                    "-SetupPath",
                    str(setup_path),
                    "-OutputPath",
                    str(output_path),
                    "-Version",
                    "4.0.1.2",
                    "-Commit",
                    commit,
                    "-SetupUrl",
                    "https://example.invalid/setup.exe",
                    "-PrivateKeyPath",
                    str(key_path),
                ],
                check=True,
                cwd=ROOT,
            )

            metadata = json.loads(output_path.read_text(encoding="utf-8"))
            first_entry = metadata["changelog"][0]

            self.assertEqual(metadata["commit"], commit)
            self.assertEqual(len(metadata["setup_sig"]), 128)
            self.assertGreater(len(metadata["changelog"]), 0)
            self.assertLessEqual(len(metadata["changelog"]), 30)
            self.assertEqual(first_entry["sha"], commit)
            self.assertEqual(
                first_entry["html_url"],
                f"https://github.com/AnLifeX/systeminformer/commit/{commit}",
            )
            self.assertTrue(first_entry["commit"]["message"])
            self.assertTrue(first_entry["commit"]["author"]["name"])
            self.assertRegex(
                first_entry["commit"]["author"]["date"],
                re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"),
            )


if __name__ == "__main__":
    unittest.main()
