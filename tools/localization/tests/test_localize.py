import codecs
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "localize.py"


class LocalizationCliTests(unittest.TestCase):
    def make_repository(self, source: str, translation: str, expected: int = 1):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        source_dir = root / "src"
        source_dir.mkdir()
        source_file = source_dir / "demo.c"
        source_file.write_bytes(
            codecs.BOM_UTF8 + b'void demo(void) {\r\n    SetTitle(L"CPU: %u\\n");\r\n}\r\n'
        )

        catalog = {
            "schema": 1,
            "locale": "zh-CN",
            "translations": [
                {
                    "id": "demo.title",
                    "path": "src/demo.c",
                    "context": 'SetTitle(L"{text}");',
                    "source": source,
                    "translation": translation,
                    "expected": expected,
                }
            ],
        }
        catalog_path = root / "catalog.json"
        catalog_path.write_text(
            json.dumps(catalog, ensure_ascii=False), encoding="utf-8"
        )
        return temporary, root, source_file, catalog_path

    def run_cli(self, root: Path, catalog: Path, *arguments: str):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                *arguments,
                "--root",
                str(root),
                "--catalog",
                str(catalog),
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_apply_is_idempotent_and_revert_preserves_encoding_and_newlines(self):
        temporary, root, source_file, catalog = self.make_repository(
            r"CPU: %u\n", r"处理器：%u\n"
        )
        self.addCleanup(temporary.cleanup)
        original = source_file.read_bytes()

        result = self.run_cli(root, catalog, "check", "--state", "source")
        self.assertEqual(result.returncode, 0, result.stderr)

        result = self.run_cli(root, catalog, "apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        translated = source_file.read_bytes()
        self.assertTrue(translated.startswith(codecs.BOM_UTF8))
        self.assertIn(b"\r\n", translated)
        self.assertIn("处理器".encode("utf-8"), translated)

        result = self.run_cli(root, catalog, "apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(source_file.read_bytes(), translated)

        result = self.run_cli(root, catalog, "check", "--state", "translated")
        self.assertEqual(result.returncode, 0, result.stderr)

        result = self.run_cli(root, catalog, "revert")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(source_file.read_bytes(), original)

    def test_rejects_placeholder_loss(self):
        temporary, root, _source_file, catalog = self.make_repository(
            r"CPU: %u\n", "处理器"
        )
        self.addCleanup(temporary.cleanup)

        result = self.run_cli(root, catalog, "check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("printf placeholders changed", result.stderr)

    def test_rejects_source_drift(self):
        temporary, root, _source_file, catalog = self.make_repository(
            r"CPU: %u\n", r"处理器：%u\n", expected=2
        )
        self.addCleanup(temporary.cleanup)

        result = self.run_cli(root, catalog, "check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("source drift detected", result.stderr)

    def test_grouped_translations_use_shared_path_and_context(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        source_dir = root / "src"
        source_dir.mkdir()
        source_file = source_dir / "demo.rc"
        source_file.write_text(
            'CAPTION "General"\nPUSHBUTTON "Close",IDOK\n', encoding="utf-8"
        )
        catalog = root / "catalog.json"
        catalog.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "locale": "zh-CN",
                    "translations": [],
                    "groups": [
                        {
                            "id": "dialog",
                            "path": "src/demo.rc",
                            "context": '"{text}"',
                            "items": [
                                {"id": "general", "source": "General", "translation": "常规"},
                                {"id": "close", "source": "Close", "translation": "关闭"},
                            ],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = self.run_cli(root, catalog, "apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            source_file.read_text(encoding="utf-8"),
            'CAPTION "常规"\nPUSHBUTTON "关闭",IDOK\n',
        )


if __name__ == "__main__":
    unittest.main()
