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

    def test_percent_wrapped_argument_is_not_a_printf_placeholder(self):
        temporary, root, _source_file, catalog = self.make_repository(
            "Append /fail=%1% to pass the count", "附加 /fail=%1% 可传递计数"
        )
        self.addCleanup(temporary.cleanup)

        result = self.run_cli(root, catalog, "check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("source drift detected", result.stderr)
        self.assertNotIn("printf placeholders changed", result.stderr)

    def test_rejects_source_drift(self):
        temporary, root, _source_file, catalog = self.make_repository(
            r"CPU: %u\n", r"处理器：%u\n", expected=2
        )
        self.addCleanup(temporary.cleanup)

        result = self.run_cli(root, catalog, "check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("source drift detected", result.stderr)

    def test_rejects_unescaped_quote_in_c_string_translation(self):
        temporary, root, _source_file, catalog = self.make_repository(
            "Enable the 'start as admin' option",
            '启用"以管理员身份启动"选项',
        )
        self.addCleanup(temporary.cleanup)

        result = self.run_cli(root, catalog, "check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unescaped C string quote", result.stderr)

    def test_rejects_unescaped_quote_in_rc_translation(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        source_dir = root / "src"
        source_dir.mkdir()
        (source_dir / "demo.rc").write_text(
            'LTEXT "Open file",IDC_STATIC\n', encoding="utf-8"
        )
        catalog = root / "catalog.json"
        catalog.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "locale": "zh-CN",
                    "translations": [
                        {
                            "id": "dialog.open",
                            "path": "src/demo.rc",
                            "context": 'LTEXT "{text}",IDC_STATIC',
                            "source": "Open file",
                            "translation": '打开"文件"',
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = self.run_cli(root, catalog, "check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unescaped RC string quote", result.stderr)

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

    def test_audit_reports_uncovered_ui_sinks_and_ignores_covered_text(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        source_dir = root / "src"
        source_dir.mkdir()
        source_file = source_dir / "demo.c"
        source_file.write_text(
            "\n".join(
                (
                    'PhCreateEMenuItem(0, 1, L"&Copy", NULL, NULL);',
                    'PhCreateEMenuItem(0, 2, L"<section placeholder>", NULL, NULL);',
                    'PhSetDialogItemText(hwndDlg, IDC_LAYOUT, L"PingGraphLayout");',
                    'PhSetDialogItemText(hwndDlg, IDC_INFO, L"0x01 - PAGE_NOACCESS\\r\\n");',
                    'PhSetDialogItemText(hwndDlg, IDC_BREAK, L"\\r\\n");',
                    'PhSetDialogItemText(hwndDlg, IDC_PERCENT, L"%.0f%%");',
                    'PhSetDialogItemText(hwndDlg, IDC_LATENCY, L"%.1f ms");',
                    'PhSetDialogItemText(hwndDlg, IDC_RATE, L"%s/s");',
                    'PhSetDialogItemText(hwndDlg, IDC_COUNTS, L"%lu | %lu");',
                    'PhSetDialogItemText(hwndDlg, IDC_FORMATTED, L"%s\\n%s");',
                    'PhSetDialogItemText(hwndDlg, IDC_DEP, L"DEP");',
                    'PhSetDialogItemText(hwndDlg, IDC_LXSS, L"PID (LXSS)");',
                    'PhSetDialogItemText(hwndDlg, IDC_INFINITY, L"\\u221E");',
                    'PhSetDialogItemText(hwndDlg, IDC_DOMAIN, L"<a href=\\\"https://example.com/\\\">example.com</a>");',
                    'PhSetDialogItemText(hwndDlg, IDC_CREDIT, L"<a href=\\\"https://example.com/user\\\">user</a> - Example Name\\n");',
                    "PhShowError2(",
                    "    hwndDlg,",
                    '    L"Unable to save the file.",',
                    '    L"%s",',
                    '    L"The destination is read-only.");',
                    'registryPath = L"Software\\\\Demo";',
                    '// PhShowStatus(hwndDlg, L"Commented-out error.", status, 0);',
                    '/* PhShowStatus(hwndDlg, L"Disabled error.", status, 0); */',
                )
            ),
            encoding="utf-8",
        )
        resource_file = source_dir / "demo.rc"
        resource_file.write_text(
            'CAPTION "Advanced options"\nPUSHBUTTON "Close",IDOK\n',
            encoding="utf-8",
        )
        catalog = root / "catalog.json"
        catalog.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "locale": "zh-CN",
                    "translations": [
                        {
                            "id": "menu.copy",
                            "path": "src/demo.c",
                            "context": 'PhCreateEMenuItem(0, 1, L"{text}", NULL, NULL);',
                            "source": "&Copy",
                            "translation": "复制(&C)",
                        },
                        {
                            "id": "resource.close",
                            "path": "src/demo.rc",
                            "context": 'PUSHBUTTON "{text}",IDOK',
                            "source": "Close",
                            "translation": "关闭",
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = self.run_cli(root, catalog, "audit", "--path", "src")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Unable to save the file.", result.stdout)
        self.assertIn("The destination is read-only.", result.stdout)
        self.assertIn("Advanced options", result.stdout)
        self.assertNotIn("&Copy", result.stdout)
        self.assertNotIn("section placeholder", result.stdout)
        self.assertNotIn("PingGraphLayout", result.stdout)
        self.assertNotIn("PAGE_NOACCESS", result.stdout)
        self.assertNotIn("%.0f%%", result.stdout)
        self.assertNotIn("%.1f ms", result.stdout)
        self.assertNotIn("%s/s", result.stdout)
        self.assertNotIn("%lu | %lu", result.stdout)
        self.assertNotIn("%s\\n%s", result.stdout)
        self.assertNotIn("[window-text] DEP", result.stdout)
        self.assertNotIn("PID (LXSS)", result.stdout)
        self.assertNotIn("u221E", result.stdout)
        self.assertNotIn("example.com", result.stdout)
        self.assertNotIn("Example Name", result.stdout)
        self.assertNotIn("Software", result.stdout)
        self.assertNotIn("Commented-out error", result.stdout)
        self.assertNotIn("Disabled error", result.stdout)
        self.assertNotIn("[PUSHBUTTON] Close", result.stdout)
        self.assertIn("uncovered=3", result.stdout)


if __name__ == "__main__":
    unittest.main()
