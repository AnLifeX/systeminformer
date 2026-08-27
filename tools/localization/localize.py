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
    r"%(?:%|(?:\d+\$)?[-+ #0']*(?:\*|\d+)?(?:\.(?:\*|\d+))?"
    r"(?:hh|h|ll|l|j|z|t|L|I32|I64|w)?[diuoxXfFeEgGaAcCsSpnZ])"
)
BRACE_PATTERN = re.compile(
    r"\{(?:\d+|[A-Za-z_]\w*)(?:![^{}]+)?(?::[^{}]+)?\}"
)
ESCAPE_PATTERN = re.compile(
    r"\\(?:[abfnrtv\\'\"?]|x[0-9A-Fa-f]+|u[0-9A-Fa-f]{4}|"
    r"U[0-9A-Fa-f]{8}|[0-7]{1,3})"
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

    snippets = [(entry.path, entry.source_snippet) for entry in translations]
    duplicate_snippets = [
        path for path, count in Counter(snippets).items() if count > 1
    ]
    if duplicate_snippets:
        raise LocalizationError("Duplicate source snippets found in the catalog")

    translated_snippets = [(entry.path, entry.translated_snippet) for entry in translations]
    duplicate_translated_snippets = [
        path for path, count in Counter(translated_snippets).items() if count > 1
    ]
    if duplicate_translated_snippets:
        raise LocalizationError("Duplicate translated snippets found in the catalog")

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
    parser.add_argument("command", choices=("check", "apply", "revert"))
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
        else:
            transform(root, entries, args.command)
    except LocalizationError as exc:
        print(f"localization error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
