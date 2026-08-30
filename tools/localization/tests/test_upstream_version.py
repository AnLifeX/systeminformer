import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "resolve_upstream_version.py"
SPEC = importlib.util.spec_from_file_location("resolve_upstream_version", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class UpstreamVersionTests(unittest.TestCase):
    def git(self, root, *arguments):
        return subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()

    def test_resolves_highest_reachable_version_tag(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)

        self.git(root, "init")
        self.git(root, "config", "user.name", "Localization Test")
        self.git(root, "config", "user.email", "localization@example.invalid")

        source = root / "source.txt"
        source.write_text("one\n", encoding="utf-8")
        self.git(root, "add", "source.txt")
        self.git(root, "commit", "-m", "version 3")
        version3_commit = self.git(root, "rev-parse", "HEAD")
        self.git(root, "tag", "upstream/v3.2.25011.2103")

        source.write_text("two\n", encoding="utf-8")
        self.git(root, "commit", "-am", "version 4")
        self.git(root, "tag", "-a", "upstream/v4.0.26241.138", "-m", "version 4")

        at_version3 = MODULE.resolve_upstream_version(
            root,
            version3_commit,
            "refs/tags/upstream/",
        )
        at_head = MODULE.resolve_upstream_version(root, "HEAD", "refs/tags/upstream/")

        self.assertEqual((at_version3.major, at_version3.minor), (3, 2))
        self.assertEqual(at_head.tag, "v4.0.26241.138")
        self.assertEqual((at_head.major, at_head.minor), (4, 0))


if __name__ == "__main__":
    unittest.main()
