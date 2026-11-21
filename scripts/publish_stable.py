#!/usr/bin/env python3
"""Publish reviewed Stable candidate to MemoryBioRAG-Stable.

Ported directly from thought-stream's release pipeline (scripts/lib/publish.js & identity.js).
Guarantees:
  1. The public repository has EXACTLY ONE AUTHOR: Dennys José Márquez Reyes <dennysjmarquez@gmail.com>.
  2. Zero private git history: commits from DEV, Arena, or testing branches are NEVER pushed.
  3. Every commit message and tag annotation is sanitized (no Co-authored-by, arena.ai, or helper tools).
  4. Strict history verification: audits all commits and tags in the public repo before any push.
  5. The public repository contains clean source code; NO .zip archives are created or pushed.
  6. Atomic push of branch and tag.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

PUBLIC_AUTHOR_NAME = "Dennys José Márquez Reyes"
PUBLIC_AUTHOR_EMAIL = "dennysjmarquez@gmail.com"
CANONICAL_PUBLIC_REPO_URL = "https://github.com/dennysjmarquez/MemoryBioRAG-Stable.git"

HELPER_PATTERNS = [
    re.compile(r"^\s*Co-authored-by:", re.IGNORECASE),
    re.compile(r"^\s*Signed-off-by:", re.IGNORECASE),
    re.compile(r"^\s*Generated (?:with|by)\b", re.IGNORECASE),
    re.compile(r"^\s*Made with\b.*(?:AI|Claude|ChatGPT|Copilot|Gemini|Cursor|Arena)", re.IGNORECASE),
    re.compile(r"\U0001F916"),  # Robot emoji
    re.compile(r"arena\.ai", re.IGNORECASE),
    re.compile(r"\bAgent Mode\b", re.IGNORECASE),
]


class PublishError(RuntimeError):
    """Raised when publication preflight or verification fails."""


def git_env(date: datetime | None = None) -> dict[str, str]:
    """Environment ensuring git records ONLY the canonical public author."""
    when = date or datetime.now(timezone.utc)
    iso = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = PUBLIC_AUTHOR_NAME
    env["GIT_AUTHOR_EMAIL"] = PUBLIC_AUTHOR_EMAIL
    env["GIT_AUTHOR_DATE"] = iso
    env["GIT_COMMITTER_NAME"] = PUBLIC_AUTHOR_NAME
    env["GIT_COMMITTER_EMAIL"] = PUBLIC_AUTHOR_EMAIL
    env["GIT_COMMITTER_DATE"] = iso
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = "NUL" if sys.platform == "win32" else "/dev/null"
    return env


def run_git(cwd: Path | str, args: list[str], env: dict[str, str] | None = None) -> str:
    """Run a git command in cwd and return stripped stdout."""
    res = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env or os.environ,
    )
    if res.returncode != 0:
        raise PublishError(f"git {' '.join(args)} failed in {cwd}:\n{res.stderr.strip() or res.stdout.strip()}")
    return res.stdout.strip()


def sanitize_message(raw: str) -> tuple[str, list[str]]:
    """Clean trailing spaces, line endings, and strip any helper tool signature."""
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    kept: list[str] = []
    removed: list[str] = []
    for line in lines:
        stripped = line.rstrip()
        if any(pat.search(stripped) for pat in HELPER_PATTERNS):
            removed.append(stripped.strip())
            continue
        kept.append(stripped)
    while kept and not kept[0].strip():
        kept.pop(0)
    while kept and not kept[-1].strip():
        kept.pop()
    text = "\n".join(kept)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text, removed


def verify_history(repo_dir: Path) -> list[str]:
    """Audit all commits and tags in the repo to guarantee single-author purity."""
    errors: list[str] = []
    expected_identity = f"{PUBLIC_AUTHOR_NAME} <{PUBLIC_AUTHOR_EMAIL}>"

    # Verify commits
    try:
        log_out = run_git(repo_dir, ["log", "--all", "--format=%H%x1f%an <%ae>%x1f%cn <%ce>%x1f%B%x1e"])
    except PublishError:
        return []  # Empty repository (e.g. root release)

    entries = [s.lstrip("\n") for s in log_out.split("\x1e") if s.strip()]
    for entry in entries:
        parts = entry.split("\x1f")
        if len(parts) < 4:
            continue
        sha = parts[0][:12]
        author = parts[1].strip()
        committer = parts[2].strip()
        body = "\x1f".join(parts[3:])

        if author != expected_identity:
            errors.append(f"Commit {sha} has non-public author: {author!r}")
        if committer != expected_identity:
            errors.append(f"Commit {sha} has non-public committer: {committer!r}")
        for pat in HELPER_PATTERNS:
            if pat.search(body):
                errors.append(f"Commit {sha} body contains helper tool signature matching {pat.pattern}")

    # Verify tags
    try:
        tag_out = run_git(repo_dir, ["for-each-ref", "--format=%(refname:short)%1f%(objecttype)%1f%(taggername) %(taggeremail)", "refs/tags"])
    except PublishError:
        tag_out = ""

    for line in tag_out.split("\n"):
        if not line.strip():
            continue
        parts = line.split("\x1f")
        tag_name = parts[0]
        obj_type = parts[1] if len(parts) > 1 else ""
        tagger = parts[2].strip() if len(parts) > 2 else ""

        if obj_type != "tag":
            errors.append(f"Tag {tag_name} is lightweight; public releases MUST be annotated tags.")
        elif tagger != expected_identity:
            errors.append(f"Tag {tag_name} was tagged by non-public identity: {tagger!r}")

    return errors


def sync_tree(src: Path, dst: Path) -> None:
    """Copy all files from src into dst, removing obsolete files in dst but preserving .git."""
    for item in dst.iterdir():
        if item.name == ".git":
            continue
        if item.is_dir() and not item.is_symlink():
            shutil.rmtree(item)
        else:
            item.unlink()

    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        target_dir = dst / rel
        target_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy2(Path(root) / f, target_dir / f)


def publish(
    version: str,
    stage_dir: Path,
    target_repo: str,
    message: str,
    dry_run: bool = False,
    branch: str = "main",
) -> dict[str, Any]:
    """Assemble and push the public release, mirroring thought-stream publish.js."""
    tag = f"v{version.lstrip('v')}"
    clean_msg, removed = sanitize_message(message)
    if not clean_msg.strip():
        raise PublishError("Release message cannot be empty after sanitization.")

    candidate_tree = stage_dir / "tree"
    if not candidate_tree.is_dir():
        raise PublishError(f"Candidate tree not found at {candidate_tree}")

    sha_file = stage_dir / "TREE_SHA256"
    if not sha_file.is_file():
        raise PublishError(f"TREE_SHA256 file missing in stage dir: {stage_dir}")

    print(f"\n🚀 MemoryBioRAG-Stable · Public Release Pipeline ({tag})")
    print(f"  • Author identity: {PUBLIC_AUTHOR_NAME} <{PUBLIC_AUTHOR_EMAIL}>")
    print(f"  • Candidate source: {candidate_tree}")
    if removed:
        print(f"  • Sanitizer stripped {len(removed)} helper tool signatures from release notes.")

    with tempfile.TemporaryDirectory(prefix="biorag-publish-") as work_str:
        work = Path(work_str)
        pub_dir = work / "repo"

        # 1. Clone or initialize target repository
        print(f"  • Initializing target repository workspace for: {target_repo}...")
        try:
            run_git(work, ["clone", "--quiet", target_repo, str(pub_dir)])
            has_head = True
        except PublishError:
            pub_dir.mkdir(parents=True, exist_ok=True)
            run_git(pub_dir, ["init", "--initial-branch", branch, "--quiet"])
            run_git(pub_dir, ["remote", "add", "origin", target_repo])
            has_head = False

        if has_head:
            try:
                run_git(pub_dir, ["rev-parse", "--verify", "-q", "HEAD"])
            except PublishError:
                has_head = False

        if has_head:
            existing_tags = [t.strip().lstrip("v") for t in run_git(pub_dir, ["tag", "--list", "v*"]).split("\n") if t.strip()]
            if version.lstrip("v") in existing_tags:
                raise PublishError(f"Version {tag} already exists in the public repository! Tags are immutable.")

            pre_errors = verify_history(pub_dir)
            if pre_errors:
                raise PublishError("The public repository already contains unauthorized history:\n" + "\n".join(f"  ✗ {e}" for e in pre_errors))

        # 2. Sync clean candidate tree into public repo (ZERO .ZIP FILES)
        print(f"  • Synchronizing clean source tree into {pub_dir} (no archives, pure source)...")
        sync_tree(candidate_tree, pub_dir)

        # 3. Commit and tag with locked identity
        env = git_env()
        run_git(pub_dir, ["add", "-A"])

        status = run_git(pub_dir, ["status", "--porcelain"])
        if has_head and not status:
            raise PublishError("Nothing changed compared with the last public commit.")

        full_commit_msg = f"{tag}\n\n{clean_msg}\n"
        msg_file = work / "commit_msg.txt"
        msg_file.write_text(full_commit_msg, encoding="utf-8")

        base_git = ["-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", "-c", "core.autocrlf=false"]
        run_git(pub_dir, base_git + ["commit", "-q", "--no-verify", "-F", str(msg_file)], env=env)
        run_git(pub_dir, base_git + ["tag", "-a", tag, "-F", str(msg_file)], env=env)

        commit_sha = run_git(pub_dir, ["rev-parse", "HEAD"])

        # 4. Rigorous post-commit verification
        post_errors = verify_history(pub_dir)
        if post_errors:
            raise PublishError("Identity guard failed after commit (aborting, nothing was pushed):\n" + "\n".join(f"  ✗ {e}" for e in post_errors))

        # 5. Push or Dry Run
        if dry_run:
            print(f"\n  ✓ [DRY RUN OK] Commit {commit_sha[:10]} and tag {tag} verified.")
            print(f"  ✓ Only author present: {PUBLIC_AUTHOR_NAME} <{PUBLIC_AUTHOR_EMAIL}>")
            print(f"  ✓ ZERO private git history attached.")
            print(f"  ✓ Pure source code staged (no .zip archives).")
            pushed = False
            gh_release_url = None
        else:
            print(f"  • Performing atomic push of branch '{branch}' and tag '{tag}'...")
            run_git(pub_dir, ["push", "--atomic", "origin", f"refs/heads/{branch}:refs/heads/{branch}", f"refs/tags/{tag}:refs/tags/{tag}"])
            print(f"\n  ✓ PUBLISHED {tag} successfully! Commit: {commit_sha[:10]}")
            pushed = True

            # 6. Create GitHub Release (same flow, not optional — a tag without a Release is incomplete)
            gh_release_url = None
            repo_slug = CANONICAL_PUBLIC_REPO_URL.rstrip(".git").split("github.com/")[-1]
            msg_tmp = work / "release_notes.md"
            msg_tmp.write_text(clean_msg, encoding="utf-8")
            gh_cmd = ["gh", "release", "create", tag,
                      "-R", repo_slug,
                      "--title", f"MemoryBioRAG-Stable {tag}",
                      "--notes-file", str(msg_tmp)]
            print(f"  • Creating GitHub Release for {tag} in {repo_slug}...")
            gh_result = subprocess.run(gh_cmd, capture_output=True, text=True)
            if gh_result.returncode == 0:
                gh_release_url = gh_result.stdout.strip().split("\n")[-1]
                print(f"  ✓ GitHub Release created: {gh_release_url}")
            else:
                # Non-fatal: push succeeded; warn and show manual command
                print(f"  ⚠ GitHub Release could not be created automatically:", file=sys.stderr)
                print(f"    {(gh_result.stderr or gh_result.stdout).splitlines()[0]}", file=sys.stderr)
                print(f"  → Run manually: gh release create {tag} -R {repo_slug} --title 'MemoryBioRAG-Stable {tag}' --notes-file <message-file>", file=sys.stderr)

        return {
            "version": version,
            "tag": tag,
            "commit": commit_sha,
            "target": target_repo,
            "pushed": pushed,
            "author": f"{PUBLIC_AUTHOR_NAME} <{PUBLIC_AUTHOR_EMAIL}>",
            "gh_release_url": gh_release_url,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish reviewed Stable candidate to MemoryBioRAG-Stable with single-author guarantee."
    )
    parser.add_argument("--version", required=True, help="Release version (e.g. v36.0)")
    parser.add_argument("--stage-dir", default=".staging/stable/preview", help="Path to staged candidate preview")
    parser.add_argument("--target", default=CANONICAL_PUBLIC_REPO_URL, help="Target git URL or local path for MemoryBioRAG-Stable")
    parser.add_argument("--message-file", help="Path to release notes Markdown file")
    parser.add_argument("--message", help="Raw release notes text")
    parser.add_argument("--dry-run", action="store_true", help="Perform full build and audit without pushing to remote")
    parser.add_argument("--branch", default="main", help="Target branch (default: main)")

    args = parser.parse_args()

    message = ""
    if args.message_file:
        message = Path(args.message_file).read_text(encoding="utf-8")
    elif args.message:
        message = args.message
    else:
        message = f"MemoryBioRAG {args.version} — Clean production release."

    try:
        stage_path = Path(args.stage_dir).resolve()
        publish(
            version=args.version,
            stage_dir=stage_path,
            target_repo=args.target,
            message=message,
            dry_run=args.dry_run,
            branch=args.branch,
        )
        return 0
    except PublishError as exc:
        print(f"\n❌ PUBLICATION BLOCKED:\n{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
