#!/usr/bin/env python3
"""Promote a reviewed Stable preview into local artifacts only."""
from __future__ import annotations

import argparse
import sys

from stable_packaging import PackagingError, REPOSITORY_ROOT, create_release


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build local Stable release artifacts from an unchanged, reviewed preview. This command never publishes.",
        epilog=(
            "Run this only after reviewing the current preview. Example (Bash, macOS, or Linux):\n"
            "  python scripts/release_stable.py \\\n"
            "    --version v36.1 \\\n"
            "    --stage-dir .staging/stable/preview \\\n"
            '    --confirm-tree-sha256 "$(cat .staging/stable/preview/TREE_SHA256)"\n\n'
            "The command accepts only .staging/stable/preview and rejects a changed tree or SHA.\n"
            "Artifacts are written under .stable-release/stable/releases/; nothing is published.\n"
            "A preparation error exits with status 2."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Explicit Stable tag in vX.X form; it must match VERSION and pyproject.toml.",
    )
    parser.add_argument(
        "--stage-dir",
        required=True,
        help="Stage directory printed by stage_stable.py; the worktree is not recopied.",
    )
    parser.add_argument(
        "--confirm-tree-sha256",
        required=True,
        help="Exact candidate tree SHA-256 from the stage report, confirming which tree is being promoted.",
    )
    args = parser.parse_args(argv)
    try:
        result = create_release(
            REPOSITORY_ROOT,
            args.version,
            args.stage_dir,
            args.confirm_tree_sha256,
        )
    except PackagingError as exc:
        print(f"RELEASE PREPARATION FAILED: {exc}", file=sys.stderr)
        return 2
    print("Local release candidate prepared.")
    print(f"Version: {result['version']}")
    print(f"Output: {result['release_directory']}")
    print(f"Artifacts: {', '.join(item['path'] for item in result['artifacts'])}")
    print("No commit, tag, push, merge, upload, or publication was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
