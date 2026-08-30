#!/usr/bin/env python3
"""Validate and apply deterministic System Informer translations."""

from __future__ import annotations

import argparse
import codecs
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


TEXT_MARKER = "{text}"
PRINTF_PATTERN = re.compile(
    r"(?<![0-9%])%(?:%|(?:\d+\$)?[-+ #0']*(?:\*|\d+)?(?:\.(?:\*|\d+))?"
    r"(?:hh|h|ll|l|j|z|t|L|I32|I64|w)?[diuoxXfFeEgGaAcCsSpnZ])"
)
BRACE_PATTERN = re.compile(
    r"\{(?:\d+|[A-Za-z_]\w*)(?:![^{}]+)?(?::[^{}]+)?\}"
)
ESCAPE_PATTERN = re.compile(
    r"\\(?:[abfnrtv\\'\"?]|x[0-9A-Fa-f]+|u[0-9A-Fa-f]{4}|"
    r"U[0-9A-Fa-f]{8}|[0-7]{1,3})"
)

SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".rc"}
DEFAULT_AUDIT_PATHS = ("SystemInformer", "plugins", "phlib", "tools/CustomSetupTool")
INTENTIONALLY_UNTRANSLATED_UI_TEXT = {
    "<section placeholder>",
    "ACPI",
    "ANSI",
    "ASLR",
    "Alt",
    "CET",
    "CPU",
    "Ctrl",
    "DEP",
    "DPI",
    "DRAM",
    "FPS",
    "GPU",
    "I/O",
    "MVID",
    "NTVDM",
    "NPU",
    "PID",
    "PID (LXSS)",
    "Ping",
    "PingGraphLayout",
    "RAPL",
    "Shift",
    "SID",
    "SDDL",
    "SMBIOS",
    "SMART",
    "Static",
    "System Informer",
    "TID",
    "TID (LXSS)",
    "TTL",
    "UIAccess",
    "Unicode",
    "VirusTotal",
    "Hybrid-Analysis",
    "WMI",
    "WOW64",
    "&filescan.io",
    "&hybrid-analysis.com",
    "&virustotal.com",
    "virusscan.&jotti.org",
}
FORMAT_ONLY_UNITS = {"B", "KB", "MB", "GB", "TB", "ms", "s"}
C_STRING_PATTERN = re.compile(r'(?<![A-Za-z0-9_])(?:u8|u|U|L)?"((?:\\.|[^"\\])*)"')
RC_TEXT_PATTERN = re.compile(
    r'^\s*(?P<kind>CAPTION|LTEXT|CTEXT|RTEXT|PUSHBUTTON|DEFPUSHBUTTON|'
    r'GROUPBOX|CONTROL|MENUITEM)\s+"(?P<text>(?:""|[^"])*)"',
    re.IGNORECASE,
)
RC_STRINGTABLE_PATTERN = re.compile(
    r'^\s*(?P<identifier>IDS?_[A-Za-z0-9_]+)\s+"(?P<text>(?:""|[^"])*)"'
)
UI_CALL_PATTERNS = (
    (
        "column",
        re.compile(r"\b(?:PhAddTreeNewColumn[A-Za-z0-9_]*|PhAddListViewColumn)\s*\("),
    ),
    (
        "menu",
        re.compile(
            r"\b(?:Ph(?:Plugin)?CreateEMenuItem|PhSetEMenuItemText)\s*\("
        ),
    ),
    (
        "message",
        re.compile(
            r"\bPhShow(?:Status|Error[A-Za-z0-9_]*|Information[A-Za-z0-9_]*|"
            r"Warning[A-Za-z0-9_]*|Message[A-Za-z0-9_]*|TaskDialog|"
            r"KsiMessage[A-Za-z0-9_]*|ContinueStatus|ConfirmMessage)\s*\("
        ),
    ),
    (
        "window-text",
        re.compile(
            r"\b(?:PhSetWindowText|SetWindowTextW?|PhSetDialogItemText|"
            r"SetDlgItemTextW?|SetupSetProgressText|SetupSetWizardButtonText)\s*\("
        ),
    ),
    (
        "task-dialog-text",
        re.compile(
            r"\bpsz(?:WindowTitle|MainInstruction|Content|ButtonText|"
            r"VerificationText|ExpandedInformation|ExpandedControlText|"
            r"CollapsedControlText|Footer)\s*="
        ),
    ),
    (
        "task-dialog-button",
        re.compile(
            r"(?:\bTASKDIALOG_BUTTON\s+[A-Za-z_]\w*\s*\[[^\]]*\]\s*="
            r"|\(TASKDIALOG_BUTTON\)\s*\{)"
        ),
    ),
    (
        "page",
        re.compile(
            r"\b(?:PhMwpCreateInternalPage|optionsEntry->CreateSection)\s*\("
        ),
    ),
)


class LocalizationError(Exception):
    """Raised when the catalog or source tree is unsafe to translate."""


@dataclass(frozen=True)
class Translation:
    identifier: str
    path: str
    context: str
    source: str
    translation: str
    expected: int

    @property
    def source_snippet(self) -> str:
        return self.context.replace(TEXT_MARKER, self.source)

    @property
    def translated_snippet(self) -> str:
        return self.context.replace(TEXT_MARKER, self.translation)


@dataclass(frozen=True)
class AuditCandidate:
    path: str
    line: int
    kind: str
    text: str
    start: int
    end: int


@dataclass
class TextFile:
    path: Path
    text: str
    has_utf8_bom: bool

    @classmethod
    def read(cls, path: Path) -> "TextFile":
        raw = path.read_bytes()
        has_utf8_bom = raw.startswith(codecs.BOM_UTF8)
        payload = raw[len(codecs.BOM_UTF8) :] if has_utf8_bom else raw

        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LocalizationError(f"{path}: file is not valid UTF-8: {exc}") from exc

        if "\x00" in text:
            raise LocalizationError(f"{path}: refusing to process a binary file")

        return cls(path=path, text=text, has_utf8_bom=has_utf8_bom)

    def write(self) -> None:
        payload = self.text.encode("utf-8")
        if self.has_utf8_bom:
            payload = codecs.BOM_UTF8 + payload
        self.path.write_bytes(payload)


def count_accelerators(value: str) -> int:
    """Count Win32 accelerator markers while treating && as a literal ampersand."""
    count = 0
    index = 0
    while index < len(value):
        if value[index] != "&":
            index += 1
            continue
        if index + 1 < len(value) and value[index + 1] == "&":
            index += 2
            continue
        count += 1
        index += 1
    return count


def token_counter(pattern: re.Pattern[str], value: str) -> Counter[str]:
    return Counter(pattern.findall(value))


def contains_unescaped_quote(value: str) -> bool:
    """Return whether a C string payload contains an unescaped double quote."""
    for index, character in enumerate(value):
        if character != '"':
            continue

        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and value[cursor] == "\\":
            backslashes += 1
            cursor -= 1

        if backslashes % 2 == 0:
            return True

    return False


def contains_unescaped_rc_quote(value: str) -> bool:
    """Return whether an RC string payload contains a quote not doubled as ""."""
    index = 0
    while index < len(value):
        if value[index] != '"':
            index += 1
            continue
        if index + 1 >= len(value) or value[index + 1] != '"':
            return True
        index += 2
    return False


def validate_tokens(entry: Translation) -> None:
    checks = (
        ("printf placeholders", token_counter(PRINTF_PATTERN, entry.source), token_counter(PRINTF_PATTERN, entry.translation)),
        ("brace placeholders", token_counter(BRACE_PATTERN, entry.source), token_counter(BRACE_PATTERN, entry.translation)),
        ("escape sequences", token_counter(ESCAPE_PATTERN, entry.source), token_counter(ESCAPE_PATTERN, entry.translation)),
    )

    for label, source_tokens, translated_tokens in checks:
        if source_tokens != translated_tokens:
            raise LocalizationError(
                f"{entry.identifier}: {label} changed: "
                f"{dict(source_tokens)} != {dict(translated_tokens)}"
            )

    if count_accelerators(entry.source) != count_accelerators(entry.translation):
        raise LocalizationError(
            f"{entry.identifier}: Win32 accelerator marker count changed"
        )

    if (
        Path(entry.path).suffix.lower() in {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"}
        and contains_unescaped_quote(entry.translation)
    ):
        raise LocalizationError(
            f"{entry.identifier}: translation contains an unescaped C string quote"
        )

    if (
        Path(entry.path).suffix.lower() == ".rc"
        and contains_unescaped_rc_quote(entry.translation)
    ):
        raise LocalizationError(
            f"{entry.identifier}: translation contains an unescaped RC string quote"
        )


def parse_translation(raw: object, index: int) -> Translation:
    if not isinstance(raw, dict):
        raise LocalizationError(f"translations[{index}] must be an object")

    required = ("id", "path", "context", "source", "translation")
    missing = [key for key in required if key not in raw]
    if missing:
        raise LocalizationError(
            f"translations[{index}] is missing: {', '.join(missing)}"
        )

    for key in required:
        if not isinstance(raw[key], str) or not raw[key]:
            raise LocalizationError(f"translations[{index}].{key} must be a non-empty string")

    expected = raw.get("expected", 1)
    if not isinstance(expected, int) or isinstance(expected, bool) or expected < 1:
        raise LocalizationError(f"translations[{index}].expected must be a positive integer")

    entry = Translation(
        identifier=raw["id"],
        path=raw["path"],
        context=raw["context"],
        source=raw["source"],
        translation=raw["translation"],
        expected=expected,
    )

    if entry.context.count(TEXT_MARKER) != 1:
        raise LocalizationError(
            f"{entry.identifier}: context must contain {TEXT_MARKER!r} exactly once"
        )
    if entry.source == entry.translation:
        raise LocalizationError(f"{entry.identifier}: source and translation are identical")
    if Path(entry.path).is_absolute() or ".." in Path(entry.path).parts:
        raise LocalizationError(f"{entry.identifier}: path must stay inside the repository")

    validate_tokens(entry)
    return entry


def parse_group(raw: object, index: int) -> list[Translation]:
    if not isinstance(raw, dict):
        raise LocalizationError(f"groups[{index}] must be an object")

    required = ("id", "path", "context", "items")
    missing = [key for key in required if key not in raw]
    if missing:
        raise LocalizationError(f"groups[{index}] is missing: {', '.join(missing)}")

    for key in ("id", "path", "context"):
        if not isinstance(raw[key], str) or not raw[key]:
            raise LocalizationError(f"groups[{index}].{key} must be a non-empty string")

    if not isinstance(raw["items"], list) or not raw["items"]:
        raise LocalizationError(f"groups[{index}].items must be a non-empty array")

    entries = []
    for item_index, item in enumerate(raw["items"]):
        if not isinstance(item, dict):
            raise LocalizationError(f"groups[{index}].items[{item_index}] must be an object")

        entry_raw = dict(item)
        item_id = entry_raw.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise LocalizationError(
                f"groups[{index}].items[{item_index}].id must be a non-empty string"
            )

        entry_raw["id"] = f"{raw['id']}.{item_id}"
        entry_raw["path"] = raw["path"]
        entry_raw["context"] = raw["context"]
        entries.append(parse_translation(entry_raw, item_index))

    return entries


def load_catalog(path: Path) -> list[Translation]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LocalizationError(f"Unable to read catalog {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise LocalizationError("Catalog root must be an object")
    if data.get("schema") != 1:
        raise LocalizationError("Catalog schema must be 1")
    if data.get("locale") != "zh-CN":
        raise LocalizationError("Catalog locale must be zh-CN")

    raw_translations = data.get("translations")
    if not isinstance(raw_translations, list):
        raise LocalizationError("Catalog translations must be an array")

    raw_groups = data.get("groups", [])
    if not isinstance(raw_groups, list):
        raise LocalizationError("Catalog groups must be an array")
    if not raw_translations and not raw_groups:
        raise LocalizationError("Catalog must contain translations or groups")

    translations = [
        parse_translation(raw, index) for index, raw in enumerate(raw_translations)
    ]

    for index, raw_group in enumerate(raw_groups):
        translations.extend(parse_group(raw_group, index))

    identifiers = [entry.identifier for entry in translations]
    duplicate_ids = sorted(
        identifier for identifier, count in Counter(identifiers).items() if count > 1
    )
    if duplicate_ids:
        raise LocalizationError(f"Duplicate translation ids: {', '.join(duplicate_ids)}")

    for label, snippet_getter in (
        ("source", lambda entry: entry.source_snippet),
        ("translated", lambda entry: entry.translated_snippet),
    ):
        entries_by_snippet: dict[tuple[str, str], list[str]] = {}
        for entry in translations:
            key = (entry.path, snippet_getter(entry))
            entries_by_snippet.setdefault(key, []).append(entry.identifier)

        duplicate_entries = [
            identifiers for identifiers in entries_by_snippet.values()
            if len(identifiers) > 1
        ]
        if duplicate_entries:
            details = "; ".join(", ".join(identifiers) for identifiers in duplicate_entries)
            raise LocalizationError(
                f"Duplicate {label} snippets found in the catalog: {details}"
            )

    return translations


def resolve_source_path(root: Path, entry: Translation) -> Path:
    root = root.resolve()
    source_path = (root / Path(entry.path)).resolve()
    if not source_path.is_relative_to(root):
        raise LocalizationError(f"{entry.identifier}: resolved path escapes repository")
    if not source_path.is_file():
        raise LocalizationError(f"{entry.identifier}: source file does not exist: {entry.path}")
    return source_path


def classify(entry: Translation, text: str) -> str:
    source_count = text.count(entry.source_snippet)
    translated_count = text.count(entry.translated_snippet)

    if source_count == entry.expected and translated_count == 0:
        return "source"
    if source_count == 0 and translated_count == entry.expected:
        return "translated"

    raise LocalizationError(
        f"{entry.identifier}: source drift detected in {entry.path}; "
        f"expected source={entry.expected}, translated=0 (or the reverse), "
        f"found source={source_count}, translated={translated_count}"
    )


def load_files(root: Path, entries: Iterable[Translation]) -> dict[Path, TextFile]:
    files: dict[Path, TextFile] = {}
    for entry in entries:
        source_path = resolve_source_path(root, entry)
        if source_path not in files:
            files[source_path] = TextFile.read(source_path)
    return files


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def is_probably_user_text(value: str) -> bool:
    if len(value.strip()) < 2 or not re.search(r"[A-Za-z]", value):
        return False

    stripped = value.strip()
    if stripped in INTENTIONALLY_UNTRANSLATED_UI_TEXT:
        return False
    if re.fullmatch(r"CPU \d+", stripped):
        return False
    if re.fullmatch(r"0x[0-9A-Fa-f]+\s+-\s+[A-Z][A-Z0-9_]+(?:\\r\\n)?", stripped):
        return False
    if not ESCAPE_PATTERN.sub("", stripped):
        return False
    if stripped in {"%s", "%ls", "%u", "%lu", "%d", "%I64u", "%I64x"}:
        return False
    without_placeholders = PRINTF_PATTERN.sub("", stripped)
    if without_placeholders != stripped:
        without_placeholders = ESCAPE_PATTERN.sub("", without_placeholders)
        remaining_words = re.findall(r"[A-Za-z]+", without_placeholders)
        if not remaining_words or all(word in FORMAT_ONLY_UNITS for word in remaining_words):
            return False
    if stripped.startswith(("http://", "https://")):
        return False
    if stripped.startswith('<a href=\\"http'):
        if (
            re.search(r"</a>\s+-\s+.+(?:\\n)?$", stripped)
            or re.search(r">[^<]*\.[^<]*</a>(?:\\n)?$", stripped)
        ):
            return False
    if re.match(r"^-[A-Za-z][A-Za-z0-9_-]*(?:\s|\\n|$)", stripped):
        return False

    return True


def mask_c_comments(text: str) -> str:
    """Mask C/C++ comments while preserving string contents and offsets."""
    characters = list(text)
    index = 0
    state = "code"
    quote = ""

    while index < len(characters):
        character = characters[index]
        following = characters[index + 1] if index + 1 < len(characters) else ""

        if state == "code":
            if character == "/" and following == "/":
                characters[index] = characters[index + 1] = " "
                index += 2
                state = "line-comment"
                continue
            if character == "/" and following == "*":
                characters[index] = characters[index + 1] = " "
                index += 2
                state = "block-comment"
                continue
            if character in {'"', "'"}:
                quote = character
                state = "string"
        elif state == "string":
            if character == "\\":
                index += 2
                continue
            if character == quote:
                state = "code"
        elif state == "line-comment":
            if character == "\n":
                state = "code"
            else:
                characters[index] = " "
        else:
            if character == "*" and following == "/":
                characters[index] = characters[index + 1] = " "
                index += 2
                state = "code"
                continue
            if character not in {"\r", "\n"}:
                characters[index] = " "

        index += 1

    return "".join(characters)


def find_ui_call_kind(text: str, literal_start: int) -> str | None:
    prefix_start = max(0, literal_start - 1200)
    prefix = text[prefix_start:literal_start]
    latest: tuple[int, int, str] | None = None

    for kind, pattern in UI_CALL_PATTERNS:
        matches = list(pattern.finditer(prefix))
        if not matches:
            continue
        match = matches[-1]
        if latest is None or match.start() > latest[0]:
            latest = (match.start(), match.end(), kind)

    if latest is None:
        return None

    _start, end, kind = latest
    if ";" in prefix[end:]:
        return None

    return kind


def extract_c_candidates(path: str, text: str) -> list[AuditCandidate]:
    candidates = []
    searchable_text = mask_c_comments(text)

    for match in C_STRING_PATTERN.finditer(searchable_text):
        value = match.group(1)
        if not is_probably_user_text(value):
            continue

        kind = find_ui_call_kind(searchable_text, match.start())
        if kind is None:
            continue

        candidates.append(
            AuditCandidate(
                path=path,
                line=line_number(text, match.start()),
                kind=kind,
                text=value,
                start=match.start(),
                end=match.end(),
            )
        )

    return candidates


def extract_rc_candidates(path: str, text: str) -> list[AuditCandidate]:
    candidates = []
    offset = 0

    for line_index, line in enumerate(text.splitlines(keepends=True), start=1):
        stripped = line.lstrip()
        if stripped.startswith("//"):
            offset += len(line)
            continue

        match = RC_TEXT_PATTERN.match(line) or RC_STRINGTABLE_PATTERN.match(line)
        if match and is_probably_user_text(match.group("text")):
            candidates.append(
                AuditCandidate(
                    path=path,
                    line=line_index,
                    kind=match.groupdict().get("kind") or "stringtable",
                    text=match.group("text"),
                    start=offset + match.start("text") - 1,
                    end=offset + match.end("text") + 1,
                )
            )

        offset += len(line)

    return candidates


def find_covered_spans(text: str, entries: Iterable[Translation]) -> list[tuple[int, int]]:
    spans = []

    for entry in entries:
        for snippet in (entry.source_snippet, entry.translated_snippet):
            offset = 0
            while True:
                index = text.find(snippet, offset)
                if index < 0:
                    break
                spans.append((index, index + len(snippet)))
                offset = index + len(snippet)

    return spans


def is_covered(candidate: AuditCandidate, spans: Iterable[tuple[int, int]]) -> bool:
    return any(
        start <= candidate.start and candidate.end <= end
        for start, end in spans
    )


def resolve_audit_paths(root: Path, requested_paths: list[Path] | None) -> list[Path]:
    resolved = []

    for requested_path in requested_paths or [Path(path) for path in DEFAULT_AUDIT_PATHS]:
        path = (root / requested_path).resolve() if not requested_path.is_absolute() else requested_path.resolve()
        if not path.is_relative_to(root):
            raise LocalizationError(f"audit path escapes repository: {requested_path}")
        if not path.exists():
            raise LocalizationError(f"audit path does not exist: {requested_path}")
        resolved.append(path)

    return resolved


def audit(
    root: Path,
    entries: list[Translation],
    requested_paths: list[Path] | None,
) -> None:
    entries_by_path: dict[str, list[Translation]] = {}
    for entry in entries:
        entries_by_path.setdefault(Path(entry.path).as_posix(), []).append(entry)

    source_files: set[Path] = set()
    for audit_path in resolve_audit_paths(root, requested_paths):
        if audit_path.is_file():
            if audit_path.suffix.lower() in SOURCE_SUFFIXES:
                source_files.add(audit_path)
            continue
        source_files.update(
            path for path in audit_path.rglob("*")
            if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES
        )

    uncovered = []
    candidate_count = 0

    for source_path in sorted(source_files):
        relative_path = source_path.relative_to(root).as_posix()
        text = TextFile.read(source_path).text
        if source_path.suffix.lower() == ".rc":
            candidates = extract_rc_candidates(relative_path, text)
        else:
            candidates = extract_c_candidates(relative_path, text)

        candidate_count += len(candidates)
        covered_spans = find_covered_spans(
            text,
            entries_by_path.get(relative_path, ()),
        )
        uncovered.extend(
            candidate for candidate in candidates
            if not is_covered(candidate, covered_spans)
        )

    for candidate in uncovered:
        print(f"{candidate.path}:{candidate.line}: [{candidate.kind}] {candidate.text}")

    print(
        f"Audited {len(source_files)} files and {candidate_count} high-confidence UI strings: "
        f"covered={candidate_count - len(uncovered)}, uncovered={len(uncovered)}"
    )


def check(root: Path, entries: list[Translation], required_state: str) -> None:
    files = load_files(root, entries)
    counts: Counter[str] = Counter()

    for entry in entries:
        source_path = resolve_source_path(root, entry)
        state = classify(entry, files[source_path].text)
        counts[state] += 1
        if required_state != "either" and state != required_state:
            raise LocalizationError(
                f"{entry.identifier}: expected state {required_state}, found {state}"
            )

    print(
        f"Checked {len(entries)} translations: "
        f"source={counts['source']}, translated={counts['translated']}"
    )


def transform(root: Path, entries: list[Translation], direction: str) -> None:
    files = load_files(root, entries)
    changed_files: set[Path] = set()
    changed_entries = 0

    for entry in entries:
        source_path = resolve_source_path(root, entry)
        text_file = files[source_path]
        state = classify(entry, text_file.text)

        if direction == "apply":
            if state == "translated":
                continue
            old, new = entry.source_snippet, entry.translated_snippet
        else:
            if state == "source":
                continue
            old, new = entry.translated_snippet, entry.source_snippet

        text_file.text = text_file.text.replace(old, new, entry.expected)
        changed_files.add(source_path)
        changed_entries += 1

    for path in sorted(changed_files):
        files[path].write()

    action = "Applied" if direction == "apply" else "Reverted"
    print(f"{action} {changed_entries} translations in {len(changed_files)} files")


def default_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "apply", "revert", "audit"))
    parser.add_argument(
        "--root",
        type=Path,
        default=default_root(),
        help="repository root (default: inferred from this script)",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help="catalog path (default: tools/localization/zh-CN.json)",
    )
    parser.add_argument(
        "--state",
        choices=("source", "translated", "either"),
        default="either",
        help="required state for the check command",
    )
    parser.add_argument(
        "--path",
        action="append",
        type=Path,
        dest="audit_paths",
        help=(
            "file or directory to scan with the audit command; may be repeated "
            "(default: SystemInformer, plugins, and phlib)"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)
    root = args.root.resolve()
    catalog_path = (
        args.catalog.resolve()
        if args.catalog is not None
        else root / "tools" / "localization" / "zh-CN.json"
    )

    try:
        entries = load_catalog(catalog_path)
        if args.command == "check":
            check(root, entries, args.state)
        elif args.command == "audit":
            audit(root, entries, args.audit_paths)
        else:
            transform(root, entries, args.command)
    except LocalizationError as exc:
        print(f"localization error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
