#!/usr/bin/env python3
"""Create an ignored local preview of the MemoryBioRAG-Stable candidate."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from stable_packaging import PackagingError, REPOSITORY_ROOT, create_stage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build and audit a local Stable preview without changing Git's index or publishing anything.",
        epilog=(
            "Example:\n"
            "  python scripts/stage_stable.py --version v36.1\n\n"
            "Review .staging/stable/preview/report.md, manifest.json, TREE_SHA256, and tree/ before\n"
            "running release_stable.py. A completed run replaces the one current preview.\n"
            "READY exits with status 0; BLOCKED or a packaging error exits with status 2."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Explicit Stable tag in vX.X form; it must match VERSION and pyproject.toml. No version is inferred or incremented.",
    )
    args = parser.parse_args(argv)
    try:
        result = create_stage(REPOSITORY_ROOT, args.version)
    except PackagingError as exc:
        print(f"STAGE FAILED: {exc}", file=sys.stderr)
        return 2
    print(f"Stage status: {result['status'].upper()}")
    print(f"Version: {result['version']}")
    print(f"Preview: {result['stage_directory']}")
    print(f"Tree SHA-256: {result['tree_sha256']}")
    print(f"Included/generated files: {sum(item['decision'] in {'included', 'generated'} for item in result['files'])}")
    print(f"Excluded/deleted paths: {sum(item['decision'] in {'excluded', 'deleted'} for item in result['files'])}")
    print(f"Blockers: {len(result['blockers'])}; warnings: {len(result['warnings'])}")
    print("Review report: " + str(Path(result["stage_directory"]) / "report.md"))
    print("No commit, tag, push, merge, upload, or publication was performed.")
    return 0 if result["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
