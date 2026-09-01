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
GIT = shutil.which("git")
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def normalize_powershell_error(error):
    """Return PowerShell error output without terminal-only formatting."""
    error = ANSI_ESCAPE_PATTERN.sub("", error)
    error = re.sub(r"\r?\n\s*[|│]\s*", " ", error)
    return " ".join(error.split())


class PowerShellErrorNormalizationTests(unittest.TestCase):
    def test_joins_wrapped_error_details_from_noninteractive_runners(self):
        rendered_error = (
            "\x1b[31;1mPrevious release commit abc is not\x1b[0m\n"
            "\x1b[36;1m     | \x1b[31;1man ancestor of def.\x1b[0m\n"
        )

        self.assertIn(
            "Previous release commit abc is not an ancestor of def.",
            normalize_powershell_error(rendered_error),
        )


@unittest.skipUnless(
    POWERSHELL and OPENSSL and GIT,
    "PowerShell, OpenSSL, and Git are required for update metadata tests",
)
class UpdateMetadataTests(unittest.TestCase):
    def git(self, repository, *arguments, capture_output=False):
        return subprocess.run(
            [GIT, "-C", str(repository), *arguments],
            check=True,
            text=True,
            stdout=subprocess.PIPE if capture_output else subprocess.DEVNULL,
            stderr=subprocess.PIPE if capture_output else subprocess.DEVNULL,
        )

    def create_repository(self, directory, additional_commits=0):
        repository = directory / "repository"
        repository.mkdir()
        self.git(repository, "init", "--initial-branch=main")
        self.git(repository, "config", "user.name", "Localization Test")
        self.git(repository, "config", "user.email", "localization@example.invalid")
        self.git(repository, "commit", "--allow-empty", "-m", "initial release")
        initial = self.git(
            repository, "rev-parse", "HEAD", capture_output=True
        ).stdout.strip()

        for index in range(additional_commits):
            self.git(
                repository,
                "commit",
                "--allow-empty",
                "-m",
                f"change {index + 1:02d}",
            )

        current = self.git(
            repository, "rev-parse", "HEAD", capture_output=True
        ).stdout.strip()
        return repository, initial, current

    def create_signing_inputs(self, directory):
        setup_path = directory / "setup.exe"
        output_path = directory / "systeminformer-update.json"
        key_path = directory / "update-key.pem"
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
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return setup_path, output_path, key_path

    def run_metadata_script(
        self,
        directory,
        repository,
        commit,
        previous_commit=None,
        upstream_tag=None,
        check=True,
    ):
        setup_path, output_path, key_path = self.create_signing_inputs(directory)
        command = [
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
            "-RepositoryRoot",
            str(repository),
            "-PrivateKeyPath",
            str(key_path),
        ]
        if previous_commit is not None:
            command.extend(["-PreviousCommit", previous_commit])
        if upstream_tag is not None:
            command.extend(["-UpstreamTag", upstream_tag])

        result = subprocess.run(
            command,
            check=check,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result, output_path

    def test_metadata_contains_every_commit_since_previous_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            repository, previous, current = self.create_repository(
                temporary_path, additional_commits=35
            )

            _, output_path = self.run_metadata_script(
                temporary_path, repository, current, previous
            )
            metadata = json.loads(output_path.read_text(encoding="utf-8"))
            expected_shas = self.git(
                repository,
                "log",
                "--format=%H",
                f"{previous}..{current}",
                capture_output=True,
            ).stdout.splitlines()

            self.assertEqual(metadata["commit"], current)
            self.assertEqual(metadata["previous_commit"], previous)
            self.assertEqual(len(metadata["setup_sig"]), 128)
            self.assertGreater(len(expected_shas), 30)
            self.assertEqual(
                [entry["sha"] for entry in metadata["changelog"]], expected_shas
            )
            self.assertEqual(metadata["changelog"][0]["sha"], current)

            for entry in metadata["changelog"]:
                self.assertEqual(
                    entry["html_url"],
                    f"https://github.com/AnLifeX/systeminformer/commit/{entry['sha']}",
                )
                self.assertTrue(entry["commit"]["message"])
                self.assertTrue(entry["commit"]["author"]["name"])
                self.assertRegex(
                    entry["commit"]["author"]["date"],
                    re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"),
                )

    def test_first_release_contains_only_its_release_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            repository, _, current = self.create_repository(
                temporary_path, additional_commits=3
            )

            _, output_path = self.run_metadata_script(
                temporary_path, repository, current
            )
            metadata = json.loads(output_path.read_text(encoding="utf-8"))

            self.assertEqual(metadata["previous_commit"], "")
            self.assertEqual(
                [entry["sha"] for entry in metadata["changelog"]], [current]
            )

    def test_metadata_records_upstream_release_tag(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            repository, _, current = self.create_repository(temporary_path)

            _, output_path = self.run_metadata_script(
                temporary_path,
                repository,
                current,
                upstream_tag="v4.0.26242.1646",
            )
            metadata = json.loads(output_path.read_text(encoding="utf-8"))

            self.assertEqual(metadata["upstream_tag"], "v4.0.26242.1646")

    def test_metadata_includes_commits_from_merged_branches(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            repository, previous, _ = self.create_repository(temporary_path)

            self.git(repository, "switch", "-c", "upstream-change")
            self.git(
                repository,
                "commit",
                "--allow-empty",
                "-m",
                "upstream branch change",
            )
            branch_commit = self.git(
                repository, "rev-parse", "HEAD", capture_output=True
            ).stdout.strip()

            self.git(repository, "switch", "main")
            self.git(repository, "commit", "--allow-empty", "-m", "localized change")
            self.git(repository, "merge", "--no-ff", "upstream-change", "-m", "merge upstream")
            current = self.git(
                repository, "rev-parse", "HEAD", capture_output=True
            ).stdout.strip()

            _, output_path = self.run_metadata_script(
                temporary_path, repository, current, previous
            )
            metadata = json.loads(output_path.read_text(encoding="utf-8"))
            actual_shas = [entry["sha"] for entry in metadata["changelog"]]

            self.assertIn(current, actual_shas)
            self.assertIn(branch_commit, actual_shas)
            self.assertNotIn(previous, actual_shas)

    def test_rejects_empty_or_unrelated_release_ranges(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            repository, _, current = self.create_repository(
                temporary_path, additional_commits=1
            )

            same_result, _ = self.run_metadata_script(
                temporary_path, repository, current, current, check=False
            )
            self.assertNotEqual(same_result.returncode, 0)
            self.assertIn(
                "must be different",
                normalize_powershell_error(same_result.stderr),
            )

            self.git(repository, "switch", "--orphan", "unrelated")
            self.git(repository, "commit", "--allow-empty", "-m", "unrelated release")
            unrelated = self.git(
                repository, "rev-parse", "HEAD", capture_output=True
            ).stdout.strip()
            self.git(repository, "switch", "main")

            unrelated_result, _ = self.run_metadata_script(
                temporary_path, repository, current, unrelated, check=False
            )
            self.assertNotEqual(unrelated_result.returncode, 0)
            self.assertIn(
                "is not an ancestor",
                normalize_powershell_error(unrelated_result.stderr),
            )


if __name__ == "__main__":
    unittest.main()
