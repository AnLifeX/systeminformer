# Simplified Chinese localization

This directory contains the deterministic localization layer used by the
`zh-CN` branch. Generated edits to upstream C and resource files are not
committed. CI applies the catalog immediately before compiling the program.

The first catalog is intentionally a small pilot covering the main tabs,
important process columns, and the misleading `System Idle Process` label.
It is not yet a complete translation.

## Commands

Run these commands from the repository root:

```powershell
python tools/localization/localize.py check --state source
python tools/localization/localize.py apply
python tools/localization/localize.py check --state translated
python tools/localization/localize.py revert
python -m unittest discover -s tools/localization/tests -v
```

`apply` and `revert` are idempotent. Files retain their UTF-8 BOM setting and
line endings.

## Catalog rules

Each entry in `zh-CN.json` contains:

- a stable, unique `id`;
- a repository-relative `path`;
- an exact `context` containing one `{text}` marker;
- the upstream `source` string;
- the Simplified Chinese `translation`;
- optionally, the expected number of matches (default: one).

The tool stops when upstream changes an expected context. It also rejects
changes to printf placeholders, brace placeholders, escape sequences, and
Win32 accelerator marker counts. This is deliberate: an upstream update must
never cause a best-effort replacement in an unrelated code location.

When adding a translation, keep the context as narrow as possible while still
making the match unique. Do not translate API names, protocol values, command
line switches, file paths, registry names, or other machine-readable strings.
