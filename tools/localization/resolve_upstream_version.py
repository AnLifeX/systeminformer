#!/usr/bin/env python3
"""Resolve System Informer's major/minor version from reachable upstream tags."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


VERSION_TAG_PATTERN = re.compile(r"^v(?P<version>\d+(?:\.\d+)+)$")


class VersionResolutionError(Exception):
    """Raised when an upstream version cannot be resolved safely."""


@dataclass(frozen=True)
class UpstreamVersion:
    tag: str
    components: tuple[int, ...]
    commit: str

    @property
    def major(self) -> int:
        return self.components[0]

    @property
    def minor(self) -> int:
        return self.components[1]


def run_git(root: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def parse_version_tag(refname: str, prefix: str) -> tuple[str, tuple[int, ...]] | None:
    if not refname.startswith(prefix):
        return None

    tag = refname[len(prefix) :]
    match = VERSION_TAG_PATTERN.fullmatch(tag)
    if not match:
        return None

    components = tuple(int(component) for component in match.group("version").split("."))
    if len(components) < 2:
        return None

    return tag, components


def resolve_upstream_version(root: Path, target: str, prefix: str) -> UpstreamVersion:
    target_commit = run_git(root, "rev-parse", "--verify", f"{target}^{{commit}}").stdout.strip()
    refs = run_git(
        root,
        "for-each-ref",
        "--format=%(refname)%09%(objectname)%09%(*objectname)",
        prefix,
    ).stdout.splitlines()

    reachable: list[UpstreamVersion] = []

    for line in refs:
        refname, objectname, peeled = (line.split("\t") + ["", ""])[:3]
        parsed = parse_version_tag(refname, prefix)
        if parsed is None:
            continue

        commit = peeled or objectname
        ancestry = run_git(
            root,
            "merge-base",
            "--is-ancestor",
            commit,
            target_commit,
            check=False,
        )
        if ancestry.returncode == 0:
            tag, components = parsed
            reachable.append(UpstreamVersion(tag=tag, components=components, commit=commit))
        elif ancestry.returncode != 1:
            raise VersionResolutionError(ancestry.stderr.strip() or "git merge-base failed")

    if not reachable:
        raise VersionResolutionError(
            f"no version tag under {prefix!r} is reachable from {target_commit}"
        )

    return max(reachable, key=lambda version: version.components)


def append_github_environment(path: Path, version: UpstreamVersion) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"BUILD_MAJORVERSION={version.major}\n")
        stream.write(f"BUILD_MINORVERSION={version.minor}\n")
        stream.write(f"UPSTREAM_VERSION_TAG={version.tag}\n")


def append_github_output(path: Path, version: UpstreamVersion) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"upstream_version_tag={version.tag}\n")
        stream.write(f"build_majorversion={version.major}\n")
        stream.write(f"build_minorversion={version.minor}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--target", default="HEAD")
    parser.add_argument("--tag-ref-prefix", default="refs/tags/upstream/")
    parser.add_argument(
        "--github-env",
        type=Path,
        help="append BUILD_MAJORVERSION and BUILD_MINORVERSION to this GitHub environment file",
    )
    parser.add_argument(
        "--github-output",
        type=Path,
        help="append resolved version fields to this GitHub output file",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        version = resolve_upstream_version(args.root.resolve(), args.target, args.tag_ref_prefix)
    except (OSError, subprocess.CalledProcessError, VersionResolutionError) as exc:
        print(f"upstream version resolution failed: {exc}", file=os.sys.stderr)
        return 1

    print(
        f"Resolved upstream version {version.tag} at {version.commit}: "
        f"BUILD_MAJORVERSION={version.major}, BUILD_MINORVERSION={version.minor}"
    )

    if args.github_env:
        append_github_environment(args.github_env, version)
    if args.github_output:
        append_github_output(args.github_output, version)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
