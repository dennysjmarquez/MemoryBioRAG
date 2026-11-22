#!/usr/bin/env python3
"""Build reviewed, local-only candidates for the MemoryBioRAG-Stable repository.

The source checkout is treated as untrusted input: only manifest-selected files
are copied, security exclusions win over includes, and unknown files in runtime
roots block the candidate. This module never creates tags, commits, pushes, merges,
or performs network publication.
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tokenize
import tomllib
import uuid
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import lru_cache
from importlib import metadata as importlib_metadata
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_NAME = "release_manifest.toml"
MAX_MANIFEST_BYTES = 256 * 1024
STABLE_TAG_PATTERN = re.compile(r"^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$")

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("openai-style-key", re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b")),
    ("npm-token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    (
        "credential-assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|passwd)"
            r"\s*[:=]\s*['\"](?!your[-_]|replace[-_]|example|placeholder|changeme|change[-_]me|dummy|insert|test[-_])"
            r"[^'\"]{16,}['\"]"
        ),
    ),
)
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PRIVATE_PATH_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])/(?:home|Users)/[A-Za-z0-9._-]+(?:/|$)"),
    re.compile(r'''(?i)\b[A-Z]:\\Users\\[^\\\s"']+'''),
)

IMPORT_TO_DISTRIBUTION = {
    "dotenv": "python-dotenv",
    "deep_translator": "deep-translator",
}


class PackagingError(RuntimeError):
    """Raised when the release configuration is invalid or unsafe."""


@dataclass
class PathRecord:
    path: str
    decision: str
    reason: str
    rule_id: str | None = None
    source_status: str | None = None
    size_bytes: int | None = None
    source_sha256: str | None = None
    staged_sha256: str | None = None
    generated: bool = False


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_relative(path: str | Path) -> str:
    value = str(path).replace("\\", "/").replace(os.sep, "/")
    pure = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        pure.is_absolute() or windows.is_absolute() or windows.drive
        or not pure.parts or ".." in pure.parts or "\n" in value or "\r" in value
    ):
        raise PackagingError(f"Unsafe repository path: {value!r}")
    return pure.as_posix()


@lru_cache(maxsize=1024)
def _glob_regex(pattern: str) -> re.Pattern[str]:
    """Compile a small, slash-aware glob dialect (supports *, ?, and **)."""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def path_matches(path: str, pattern: str) -> bool:
    return bool(_glob_regex(pattern).fullmatch(path))


def validate_stable_tag(value: str) -> str:
    """Accept only canonical vX.X Stable tags; never infer or bump a version."""
    if not STABLE_TAG_PATTERN.fullmatch(value):
        raise PackagingError(
            f"Invalid Stable version {value!r}; supply an explicit tag in vX.X form (no prereleases)."
        )
    return value


def pep440_version(tag: str) -> str:
    major, minor = validate_stable_tag(tag)[1:].split(".")
    return f"{major}.{minor}.0"


def _load_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST_NAME
    if path.is_symlink():
        raise PackagingError(f"Release manifest must not be a symbolic link: {MANIFEST_NAME}")
    if not path.is_file():
        raise PackagingError(f"Release manifest not found: {MANIFEST_NAME}")
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_MANIFEST_BYTES + 1)
        if len(raw) > MAX_MANIFEST_BYTES:
            raise PackagingError(f"{MANIFEST_NAME} exceeds the {MAX_MANIFEST_BYTES}-byte safety limit.")
        data = tomllib.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise PackagingError(f"Could not read {MANIFEST_NAME}: {exc}") from exc
    if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        raise PackagingError("Unsupported release manifest schema_version.")
    if data.get("stable_tag_pattern") != STABLE_TAG_PATTERN.pattern:
        raise PackagingError("Manifest Stable tag pattern differs from the canonical vX.X policy.")
    if not isinstance(data.get("project_name"), str) or not data["project_name"].strip():
        raise PackagingError("Manifest project_name must be a non-empty string.")
    includes = data.get("include")
    excludes = data.get("exclude")
    if not isinstance(includes, list) or not includes or not isinstance(excludes, list):
        raise PackagingError("Manifest include/exclude rules are missing or invalid.")
    rule_ids: set[str] = set()
    for group in (includes, excludes):
        for rule in group:
            if not isinstance(rule, dict):
                raise PackagingError("Every manifest rule must be a table.")
            rule_id = rule.get("id")
            patterns = rule.get("patterns")
            reason = rule.get("reason")
            if not isinstance(rule_id, str) or not rule_id.strip() or rule_id in rule_ids:
                raise PackagingError("Manifest rule IDs must be unique non-empty strings.")
            rule_ids.add(rule_id)
            if not isinstance(reason, str) or not reason.strip() or not isinstance(patterns, list) or not patterns:
                raise PackagingError(f"Manifest rule {rule_id!r} needs a reason and at least one path pattern.")
            for pattern in patterns:
                if not isinstance(pattern, str) or not pattern or "\\" in pattern:
                    raise PackagingError(f"Manifest rule {rule_id!r} contains an invalid path pattern.")
                pure_pattern = PurePosixPath(pattern)
                windows_pattern = PureWindowsPath(pattern)
                if (
                    pure_pattern.is_absolute()
                    or windows_pattern.is_absolute()
                    or windows_pattern.drive
                    or ".." in pure_pattern.parts
                    or pure_pattern.as_posix() != pattern
                ):
                    raise PackagingError(f"Manifest rule {rule_id!r} contains an unsafe path pattern.")
                _glob_regex(pattern)
    if not any(rule_id.startswith("security-") for rule_id in (str(item["id"]) for item in excludes)):
        raise PackagingError("At least one security exclusion rule is required.")
    strict_dirs = data.get("strict_directories")
    strict_root_patterns = data.get("strict_root_file_patterns")
    required_paths = data.get("required_source_paths")
    if not isinstance(strict_dirs, list) or not isinstance(strict_root_patterns, list) or not isinstance(required_paths, list):
        raise PackagingError("Strict-path and required-source manifest settings must be lists.")
    if any(not isinstance(item, str) for item in strict_dirs + required_paths):
        raise PackagingError("Strict directories and required source paths must be strings.")
    for source_key in ("source_version_file", "source_project_file"):
        source_path = data.get(source_key)
        if not isinstance(source_path, str) or _normalized_relative(source_path) != source_path:
            raise PackagingError(f"Manifest {source_key} must be a canonical relative repository path.")
    for relative_path in strict_dirs + required_paths:
        if _normalized_relative(relative_path) != relative_path:
            raise PackagingError("Strict directories and required source paths must be canonical relative paths.")
    for pattern in strict_root_patterns:
        if not isinstance(pattern, str) or not pattern or "/" in pattern or "\\" in pattern:
            raise PackagingError("Strict root file patterns must be non-empty basename-only globs.")
        _glob_regex(pattern)
    output = data.get("output")
    if not isinstance(output, dict):
        raise PackagingError("Manifest output settings are missing.")
    stage_value = output.get("staging_directory")
    release_value = output.get("release_directory")
    if not isinstance(stage_value, str) or not isinstance(release_value, str):
        raise PackagingError("Stage and release output directories must be relative path strings.")
    normalized_stage = _normalized_relative(stage_value)
    normalized_release = _normalized_relative(release_value)
    if normalized_stage != stage_value or normalized_release != release_value:
        raise PackagingError("Stage and release output directories must be canonical relative paths.")
    stage_output = PurePosixPath(normalized_stage)
    release_output = PurePosixPath(normalized_release)
    if stage_output == release_output or stage_output in release_output.parents or release_output in stage_output.parents:
        raise PackagingError("Stage and release output directories must be separate and non-nested.")
    if (
        not isinstance(output.get("source_archive_prefix"), str)
        or not output["source_archive_prefix"].strip()
        or "/" in output["source_archive_prefix"]
        or "\\" in output["source_archive_prefix"]
    ):
        raise PackagingError("Manifest source_archive_prefix must be a non-empty filename prefix.")
    maximum = data.get("max_source_file_bytes")
    if type(maximum) is not int or maximum <= 0:
        raise PackagingError("Manifest max_source_file_bytes must be a positive integer.")
    return data


def _read_source_version(root: Path, manifest: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    version_path = root / manifest["source_version_file"]
    project_path = root / manifest["source_project_file"]
    try:
        tag = validate_stable_tag(version_path.read_text(encoding="utf-8").strip())
        project = tomllib.loads(project_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, PackagingError) as exc:
        raise PackagingError(f"Could not validate the canonical project version: {exc}") from exc
    expected = pep440_version(tag)
    found = str(project.get("project", {}).get("version", ""))
    if found != expected:
        raise PackagingError(
            f"Version mismatch: VERSION is {tag}, but pyproject.toml declares {found!r}; "
            f"the expected package version is {expected}. No version is changed automatically."
        )
    return tag, project


def _git_output(root: Path, *args: str) -> set[str]:
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return set()
    if result.returncode != 0:
        return set()
    return {
        os.fsdecode(item).replace("\\", "/")
        for item in result.stdout.split(b"\0")
        if item
    }


def _git_state(root: Path) -> dict[str, set[str]]:
    tracked = _git_output(root, "ls-files", "-z")
    modified = _git_output(root, "diff", "--name-only", "-z")
    staged = _git_output(root, "diff", "--cached", "--name-only", "-z")
    untracked = _git_output(root, "ls-files", "--others", "--exclude-standard", "-z")
    deleted = _git_output(root, "diff", "HEAD", "--name-only", "--diff-filter=D", "-z")
    ignored = _git_output(root, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z")
    return {
        "tracked": tracked,
        "modified": modified,
        "staged": staged,
        "untracked": untracked,
        "deleted": deleted,
        "ignored": ignored,
    }


def _source_status(path: str, state: dict[str, set[str]]) -> str:
    if path in state["deleted"]:
        return "deleted"
    if path in state["modified"]:
        return "modified"
    if path in state["staged"]:
        return "staged"
    if path in state["tracked"]:
        return "tracked"
    if path in state["untracked"]:
        return "untracked"
    if any(path == item.rstrip("/") or path.startswith(item.rstrip("/") + "/") for item in state.get("ignored", set())):
        return "ignored"
    return "unknown"


def _compiled_rules(rules: Iterable[dict[str, Any]]) -> list[tuple[dict[str, Any], str]]:
    compiled: list[tuple[dict[str, Any], str]] = []
    for rule in rules:
        for pattern in rule.get("patterns", []):
            compiled.append((rule, pattern))
    return compiled


def _matching_rule(path: str, rules: list[tuple[dict[str, Any], str]]) -> tuple[dict[str, Any], str] | None:
    for rule, pattern in rules:
        if path_matches(path, pattern):
            return rule, pattern
    return None


def _is_strict_path(path: str, manifest: dict[str, Any]) -> bool:
    for directory in manifest.get("strict_directories", []):
        if path == directory or path.startswith(directory.rstrip("/") + "/"):
            return True
    return any(
        "/" not in path and path_matches(path, pattern)
        for pattern in manifest.get("strict_root_file_patterns", [])
    )


def _decision_for_path(
    path: str,
    manifest: dict[str, Any],
    include_rules: list[tuple[dict[str, Any], str]],
    exclude_rules: list[tuple[dict[str, Any], str]],
    security_rules: list[tuple[dict[str, Any], str]],
) -> tuple[str, str, str | None, str | None]:
    include_match = _matching_rule(path, include_rules)
    security_match = _matching_rule(path, security_rules)
    if security_match:
        rule, _ = security_match
        conflict = include_match is not None
        return (
            "blocked" if conflict else "excluded",
            "A security exclusion overrides the allowlist." if conflict else rule["reason"],
            rule["id"],
            "security-include-conflict" if conflict else None,
        )
    exclude_match = _matching_rule(path, exclude_rules)
    if exclude_match:
        rule, _ = exclude_match
        return "excluded", rule["reason"], rule["id"], None
    if include_match:
        rule, _ = include_match
        return "included", rule["reason"], rule["id"], None
    if _is_strict_path(path, manifest):
        return (
            "unclassified",
            "This path is under a strict runtime root but has no include or exclusion rule.",
            None,
            "unclassified-runtime-path",
        )
    return (
        "excluded",
        "Not selected by the Stable allowlist; source-only material remains in the research repository.",
        "default-out-of-scope",
        None,
    )


def _walk_source(
    root: Path,
    manifest: dict[str, Any],
    state: dict[str, set[str]],
    blockers: list[dict[str, str]],
) -> list[PathRecord]:
    include_rules = _compiled_rules(manifest.get("include", []))
    exclude_rules = _compiled_rules(manifest.get("exclude", []))
    security_rules = [
        item for item in exclude_rules
        if str(item[0].get("id", "")).startswith("security-")
    ]
    ordinary_excludes = [item for item in exclude_rules if item not in security_rules]
    records: list[PathRecord] = []
    seen: set[str] = set()

    for current, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        kept_dirs: list[str] = []
        for dirname in sorted(dirnames):
            child = current_path / dirname
            relative = _normalized_relative(child.relative_to(root))
            if child.is_symlink():
                action, reason, rule_id, code = _decision_for_path(
                    relative, manifest, include_rules, ordinary_excludes, security_rules
                )
                records.append(PathRecord(
                    relative + "/", "blocked" if action != "excluded" else "excluded",
                    "Symbolic-link directories are never followed; " + reason,
                    rule_id, source_status=_source_status(relative, state),
                ))
                if action != "excluded":
                    blockers.append({"code": "symlink-source", "path": relative, "message": "A symbolic-link directory intersects the Stable source scope."})
                continue
            probe = relative + "/__stable_packaging_probe__"
            security_match = _matching_rule(probe, security_rules)
            if security_match:
                rule, _ = security_match
                records.append(PathRecord(
                    relative + "/", "excluded", rule["reason"], rule["id"],
                    source_status=_source_status(relative, state),
                ))
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            source = current_path / filename
            relative = _normalized_relative(source.relative_to(root))
            if relative in seen:
                continue
            seen.add(relative)
            source_status = _source_status(relative, state)
            if source.is_symlink():
                action, reason, rule_id, _ = _decision_for_path(
                    relative, manifest, include_rules, ordinary_excludes, security_rules
                )
                decision = "blocked" if action != "excluded" else "excluded"
                records.append(PathRecord(relative, decision, "Symbolic links are not copied. " + reason, rule_id, source_status=source_status))
                if decision == "blocked":
                    blockers.append({"code": "symlink-source", "path": relative, "message": "A symbolic link intersects the Stable source scope."})
                continue
            action, reason, rule_id, error_code = _decision_for_path(
                relative, manifest, include_rules, ordinary_excludes, security_rules
            )
            if error_code:
                blockers.append({"code": error_code, "path": relative, "message": reason})
            if action == "included" and source_status in {"ignored", "unknown"}:
                code = "ignored-runtime-source" if source_status == "ignored" else "unknown-git-source-status"
                blocker_reason = "Git ignores this selected source file; it is never copied implicitly." if source_status == "ignored" else "Git could not classify this selected source file as tracked, staged, modified, or untracked."
                records.append(PathRecord(relative, "blocked", blocker_reason, rule_id, source_status=source_status))
                blockers.append({"code": code, "path": relative, "message": blocker_reason})
                continue
            try:
                size = source.stat().st_size
            except OSError as exc:
                records.append(PathRecord(relative, "blocked", f"Could not inspect source file: {exc}", rule_id, source_status=source_status))
                blockers.append({"code": "source-stat-failed", "path": relative, "message": "Could not inspect an input file."})
                continue
            records.append(PathRecord(relative, action, reason, rule_id, source_status, size_bytes=size))

    for missing in sorted(state["deleted"]):
        try:
            relative = _normalized_relative(missing)
        except PackagingError:
            continue
        if relative in seen:
            continue
        action, reason, rule_id, error_code = _decision_for_path(
            relative, manifest, include_rules, ordinary_excludes, security_rules
        )
        if action == "included" or _is_strict_path(relative, manifest):
            blockers.append({
                "code": "deleted-runtime-source",
                "path": relative,
                "message": "A tracked runtime-scope file is deleted in the worktree; review the deletion before staging.",
            })
        if error_code:
            blockers.append({"code": error_code, "path": relative, "message": reason})
        records.append(PathRecord(
            relative, "deleted", "Deleted from the current worktree; no file is copied. " + reason,
            rule_id, source_status="deleted",
        ))
    return records


def _secret_findings(text: str) -> list[str]:
    return [name for name, pattern in SECRET_PATTERNS if pattern.search(text)]


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise PackagingError(f"Expected one {label} anchor; found {count}.")
    return text.replace(old, new, 1)


def _replace_repo_urls(text: str) -> tuple[str, int]:
    patterns = (
        ("https://raw.githubusercontent.com/dennysjmarquez/MemoryBioRAG", "https://raw.githubusercontent.com/dennysjmarquez/MemoryBioRAG-Stable"),
        ("https://api.github.com/repos/dennysjmarquez/MemoryBioRAG", "https://api.github.com/repos/dennysjmarquez/MemoryBioRAG-Stable"),
        ("https://github.com/dennysjmarquez/MemoryBioRAG", "https://github.com/dennysjmarquez/MemoryBioRAG-Stable"),
    )
    count = 0
    for old, new in patterns:
        text, found = re.subn(re.escape(old) + r"(?!-Stable)", new, text)
        count += found
    return text, count


def _transform_project_metadata(text: str, expected_version: str) -> tuple[str, list[str]]:
    try:
        project = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise PackagingError(f"Source pyproject.toml is invalid TOML: {exc}") from exc
    metadata = project.get("project", {})
    text, vcount = re.subn(
        r'(?m)^version\s*=\s*"[^"]*"\s*$',
        f'version = "{pep440_version(expected_version)}"',
        text,
        count=1,
    )
    if vcount != 1:
        raise PackagingError("Could not update package version in pyproject.toml.")

    text, count = re.subn(
        r'(?m)^description\s*=\s*"[^"]*"\s*$',
        'description = "Persistent cognitive memory for AI agents"',
        text,
        count=1,
    )
    if count != 1:
        raise PackagingError("Could not replace the source package description with English metadata.")

    def strip_contact_emails(key: str) -> None:
        nonlocal text
        contacts = metadata.get(key)
        if contacts is None:
            return
        if not isinstance(contacts, list):
            raise PackagingError(f"Project {key} metadata must be a list of contact records.")
        names: list[str] = []
        for contact in contacts:
            if isinstance(contact, dict):
                name = contact.get("name")
            elif isinstance(contact, str):
                name = contact.split("<", 1)[0].strip()
            else:
                name = None
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
        start = text.find("[project]")
        if start < 0:
            raise PackagingError("Missing [project] metadata while sanitizing contact fields.")
        next_header = text.find("\n[", start + len("[project]"))
        end = len(text) if next_header < 0 else next_header + 1
        block = text[start:end]
        pattern = re.compile(rf"(?ms)^{re.escape(key)}\s*=\s*\[.*?^\s*\]")
        entries = ",\n".join(f"    {{ name = {json.dumps(name, ensure_ascii=False)} }}" for name in names)
        replacement = f"{key} = [\n{entries}\n]" if entries else f"{key} = []"
        block, replaced = pattern.subn(replacement, block, count=1)
        if replaced != 1:
            raise PackagingError(f"Could not sanitize project {key} metadata.")
        text = text[:start] + block + text[end:]

    strip_contact_emails("authors")
    strip_contact_emails("maintainers")

    def update_array(section: str, key: str, additions: list[str]) -> None:
        nonlocal text
        header = f"[{section}]"
        start = text.find(header)
        if start < 0:
            raise PackagingError(f"Missing [{section}] in pyproject.toml.")
        next_header = text.find("\n[", start + len(header))
        end = len(text) if next_header < 0 else next_header + 1
        block = text[start:end]
        match = re.search(rf"(?m)^{re.escape(key)}\s*=\s*\[([^\]]*)\]", block)
        if not match:
            raise PackagingError(f"Missing {key} array in [{section}].")
        values = re.findall(r'"([^\"]+)"', match.group(1))
        for value in additions:
            if value not in values:
                values.append(value)
        replacement = f'{key} = [' + ", ".join(f'"{value}"' for value in values) + "]"
        block = block[:match.start()] + replacement + block[match.end():]
        text = text[:start] + block + text[end:]

    update_array("tool.setuptools", "py-modules", ["graph_maintenance_daemon"])
    update_array("tool.setuptools.packages.find", "include", ["db*"])

    if "[tool.setuptools.package-data]" not in text:
        text = text.rstrip() + '\n\n[tool.setuptools.package-data]\ndb = ["hebbian_clusters.json"]\n'
    else:
        update_array("tool.setuptools.package-data", "db", ["hebbian_clusters.json"])

    try:
        result = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise PackagingError(f"Transformed pyproject.toml is invalid TOML: {exc}") from exc
    transformed = result.get("tool", {}).get("setuptools", {})
    if "graph_maintenance_daemon" not in transformed.get("py-modules", []):
        raise PackagingError("The maintenance daemon is missing from the wheel module list.")
    if "db*" not in transformed.get("packages", {}).get("find", {}).get("include", []):
        raise PackagingError("The runtime data package is missing from package discovery.")
    package_data = transformed.get("package-data", {}).get("db", [])
    if "hebbian_clusters.json" not in package_data:
        raise PackagingError("The generated Hebbian fallback resource is not configured as package data.")
    return text, list(metadata.get("dependencies", []))


def _render_template(root: Path, relative: str, version: str) -> str:
    template = root / relative
    try:
        text = template.read_text(encoding="utf-8")
    except OSError as exc:
        raise PackagingError(f"Required English template is missing: {relative}") from exc
    rendered = text.replace("{{VERSION}}", version)
    if "{{" in rendered or "}}" in rendered:
        raise PackagingError(f"Unresolved placeholder in template {relative}.")
    return rendered


def _write_generated(
    tree: Path,
    relative: str,
    data: bytes,
    reason: str,
    records: list[PathRecord],
) -> None:
    rel = _normalized_relative(relative)
    target = tree / Path(*PurePosixPath(rel).parts)
    if target.exists():
        raise PackagingError(f"Generated output would overwrite an included source path: {rel}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    records.append(PathRecord(
        rel, "generated", reason, "generated-overlay", size_bytes=len(data),
        staged_sha256=_sha256_bytes(data), generated=True,
    ))


def _transform_hebbian_schema(tree: Path) -> list[str]:
    source = tree / "core" / "sdm.py"
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PackagingError("Could not read the SDM module for the Stable resource-schema transform.") from exc
    replacements = (
        ("'dim_names'", "'dimension_names'"),
        ("'umbral'", "'threshold'"),
        ("'total_nodos'", "'total_nodes'"),
    )
    counts: dict[str, int] = {}
    for old, new in replacements:
        count = text.count(old)
        if count == 0:
            raise PackagingError(f"Expected Hebbian schema key {old} in core/sdm.py; found none.")
        text = text.replace(old, new)
        counts[old] = count
    source.write_text(text, encoding="utf-8")
    return [
        "Mapped the excluded corpus-derived Hebbian resource schema to English-only field names "
        "(dimension_names, threshold, total_nodes) for Stable's empty fallback."
    ]


def _disable_dashboard_cli(text: str) -> str:
    """Hide the dashboard command while preserving its handler for later reuse."""
    doc_start = "  python3 biorag.py dashboard\n"
    doc_end = "PROTOCOLO PARA EL AGENTE"
    if text.count(doc_start) != 1 or text.count(doc_end) != 1:
        raise PackagingError("Could not identify the dashboard help section in biorag.py.")
    start = text.index(doc_start)
    end = text.index(doc_end, start)
    text = text[:start] + text[end:]
    text = _replace_once(
        text,
        '        "dashboard": cmd_dashboard,\n',
        "",
        "Stable dashboard CLI registration",
    )
    try:
        module = ast.parse(text)
    except SyntaxError as exc:
        raise PackagingError("Disabling the dashboard command left biorag.py invalid.") from exc

    handlers = [
        node for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "cmd_dashboard"
    ]
    if len(handlers) != 1:
        raise PackagingError("The Stable candidate must retain exactly one cmd_dashboard handler.")
    registered = any(
        isinstance(key, ast.Constant)
        and key.value == "dashboard"
        and isinstance(value, ast.Name)
        and value.id == "cmd_dashboard"
        for node in ast.walk(module)
        if isinstance(node, ast.Dict)
        for key, value in zip(node.keys, node.values)
    )
    if registered:
        raise PackagingError("The Stable CLI still registers cmd_dashboard.")
    return text


def _apply_stable_identity(tree: Path) -> list[str]:
    notes: list[str] = []
    biorag = tree / "biorag.py"
    text = biorag.read_text(encoding="utf-8")
    text, replaced = _replace_repo_urls(text)
    if replaced == 0:
        raise PackagingError("The Stable repository URL was not found in biorag.py.")
    text = _disable_dashboard_cli(text)
    biorag.write_text(text, encoding="utf-8")
    notes.append("Repointed the CLI repository link to MemoryBioRAG-Stable, disabled the dashboard help and command registration, and retained its handler as dormant code.")

    installer = tree / "install.py"
    text = installer.read_text(encoding="utf-8")
    text = _replace_once(
        text,
        'REPO_NAME = "MemoryBioRAG"',
        'REPO_NAME = "MemoryBioRAG-Stable"',
        "installer repository name",
    )
    text, replaced = _replace_repo_urls(text)
    if replaced == 0:
        raise PackagingError("The installer contains no source-repository URLs to repoint.")
    installer.write_text(text, encoding="utf-8")
    notes.append("Repointed installer clone, ZIP fallback, and raw installer URLs to MemoryBioRAG-Stable; retained the API-aware OpenCode plugin installer for both bundled plugin versions.")

    checker = tree / "core" / "mcp_server" / "update_checker.py"
    text = checker.read_text(encoding="utf-8")
    text, replaced = _replace_repo_urls(text)
    if replaced == 0:
        raise PackagingError("The update checker contains no source-repository URL to repoint.")
    version_line = r'_VERSION_PATTERN = re.compile(r"^[vV]?(\d+(?:\.\d+){1,2})$")'
    replacement_line = (
        version_line
        + '\n_STABLE_TAG_PATTERN = re.compile(r"^v(?:0|[1-9][0-9]*)\\.(?:0|[1-9][0-9]*)$")'
    )
    text = _replace_once(text, version_line, replacement_line, "update-checker version pattern")
    anchor = (
        '    return ".".join(str(part) for part in key) if key is not None else value.strip()\n'
        '\n'
        '\n'
        'def installed_version() -> str:'
    )
    insertion = (
        '    return ".".join(str(part) for part in key) if key is not None else value.strip()\n'
        '\n'
        '\n'
        'def _is_stable_tag(value: str) -> bool:\n'
        '    """Return whether value is a canonical vX.X Stable tag."""\n'
        '    return bool(_STABLE_TAG_PATTERN.fullmatch(value.strip()))\n'
        '\n'
        '\n'
        'def installed_version() -> str:'
    )
    text = _replace_once(text, anchor, insertion, "update-checker Stable tag validator")
    text = _replace_once(
        text,
        'if isinstance(tag, str) and _version_key(tag) is not None:',
        'if isinstance(tag, str) and _is_stable_tag(tag):',
        "update-checker tag filter",
    )
    old_blocked = (
        'if not isinstance(blocked, list) or any(\n'
        '                not isinstance(tag, str) or _version_key(tag) is None for tag in blocked\n'
        '            ):'
    )
    new_blocked = (
        'if not isinstance(blocked, list) or any(\n'
        '                not isinstance(tag, str) or not _is_stable_tag(tag) for tag in blocked\n'
        '            ):'
    )
    text = _replace_once(text, old_blocked, new_blocked, "update-policy blocked-tag validator")
    text = _replace_once(
        text,
        'if recommended_key is None:\n                raise ValueError("Tag recomendado no es una versión estable")',
        'if not _is_stable_tag(recommended) or recommended_key is None:\n'
        '                raise ValueError("Recommended tag is not a vX.X Stable version")',
        "update-policy recommended-tag validator",
    )
    text = _replace_once(
        text,
        'if isinstance(tag, str) and _version_key(tag) == recommended_key',
        'if isinstance(tag, str) and _is_stable_tag(tag) and _version_key(tag) == recommended_key',
        "update-checker matching-tag validator",
    )
    text = text.replace(
        '"La versión recomendada aún no existe como tag en MemoryBioRAG."',
        '"The recommended Stable tag is not published in MemoryBioRAG-Stable yet."',
    )
    if 'https://api.github.com/repos/dennysjmarquez/MemoryBioRAG"' in text:
        raise PackagingError("The update checker still points at the research repository.")
    if '_STABLE_TAG_PATTERN' not in text or '_is_stable_tag(tag)' not in text:
        raise PackagingError("The Stable tag restriction was not applied to the update checker.")
    checker.write_text(text, encoding="utf-8")
    notes.append("Moved update checks to Stable and restricted policy/tags to canonical vX.X tags only.")
    return notes


def _copy_source_file(root: Path, tree: Path, record: PathRecord, manifest: dict[str, Any], blockers: list[dict[str, str]]) -> None:
    source = root / Path(*PurePosixPath(record.path).parts)
    target = tree / Path(*PurePosixPath(record.path).parts)
    maximum = int(manifest.get("max_source_file_bytes", 5_000_000))
    if record.size_bytes is not None and record.size_bytes > maximum:
        record.decision = "blocked"
        record.reason = f"Selected source exceeds the configured {maximum}-byte limit."
        blockers.append({"code": "source-file-too-large", "path": record.path, "message": record.reason})
        return
    try:
        data = source.read_bytes()
        text = data.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        record.decision = "blocked"
        record.reason = f"Selected source is unreadable UTF-8 text: {exc.__class__.__name__}."
        blockers.append({"code": "source-read-failed", "path": record.path, "message": record.reason})
        return
    findings = _secret_findings(text)
    if findings:
        record.decision = "blocked"
        record.reason = "High-confidence credential pattern detected: " + ", ".join(findings)
        blockers.append({"code": "secret-pattern", "path": record.path, "message": record.reason})
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    record.source_sha256 = _sha256_bytes(data)
    record.staged_sha256 = _sha256_bytes(data)


def _update_record_hash(records: list[PathRecord], relative: str, tree: Path) -> None:
    target = tree / Path(*PurePosixPath(relative).parts)
    for record in records:
        if record.path == relative and record.decision in {"included", "generated"}:
            record.size_bytes = target.stat().st_size
            record.staged_sha256 = _sha256_file(target)
            return
    records.append(PathRecord(
        relative, "generated", "Stable-specific transformation.", "stable-transform",
        size_bytes=target.stat().st_size, staged_sha256=_sha256_file(target), generated=True,
    ))


def _dependencies_from_project(project: dict[str, Any]) -> tuple[list[str], set[str]]:
    dependencies = list(project.get("project", {}).get("dependencies", []))
    normalized: set[str] = set()
    for requirement in dependencies:
        name = re.split(r"[<>=!~;\[]", str(requirement), maxsplit=1)[0].strip()
        if not name:
            continue
        normalized.add(re.sub(r"[-_.]+", "-", name).lower())
    return dependencies, normalized


def _collect_imports(tree: Path, pyproject: dict[str, Any], manifest: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    _, declared = _dependencies_from_project(pyproject)
    optional_map = manifest.get("dependencies", {}).get("optional_module_distributions", {})
    optional_modules = {str(module): str(dist) for module, dist in optional_map.items()}
    known_local = {"core", "config", "middleware", "db", "biorag", "mcp_server", "install", "graph_maintenance_daemon"}

    def module_exists(module: str) -> bool:
        if not module:
            return True
        candidate = tree.joinpath(*module.split("."))
        return candidate.with_suffix(".py").is_file() or (candidate / "__init__.py").is_file()

    for source in sorted(tree.rglob("*.py")):
        try:
            parsed = ast.parse(source.read_text(encoding="utf-8"), filename=source.as_posix())
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            relative = source.relative_to(tree).as_posix()
            blockers.append({"code": "python-syntax", "path": relative, "message": f"Python source is not parseable ({exc.__class__.__name__})."})
            continue
        relative = source.relative_to(tree).as_posix()
        for node in ast.walk(parsed):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level:
                    parent_parts = list(PurePosixPath(relative).parent.parts)
                    keep = max(0, len(parent_parts) - node.level + 1)
                    base = parent_parts[:keep]
                    target = ".".join(base + ([module] if module else []))
                    if target and not module_exists(target):
                        blockers.append({"code": "missing-local-import", "path": relative, "message": f"Relative import target is absent from the Stable tree: {target}."})
                    continue
                if module:
                    imported.append(module)
            for name in imported:
                top_level = name.split(".", 1)[0]
                if top_level in known_local:
                    if not module_exists(name):
                        blockers.append({"code": "missing-local-import", "path": relative, "message": f"Required local module is absent from the Stable tree: {name}."})
                    continue
                if top_level in sys.stdlib_module_names:
                    continue
                distribution = IMPORT_TO_DISTRIBUTION.get(top_level, top_level)
                normalized = re.sub(r"[-_.]+", "-", distribution).lower()
                if normalized in declared:
                    continue
                if top_level in optional_modules:
                    warnings.append({"code": "optional-dependency", "path": relative, "message": f"Optional import {top_level!r} is not installed by default; optional distribution {optional_modules[top_level]!r} is not bundled."})
                    continue
                blockers.append({"code": "undeclared-dependency", "path": relative, "message": f"Imported third-party module {top_level!r} is not declared in project.dependencies."})
    for requirement in pyproject.get("project", {}).get("dependencies", []):
        if "==" not in str(requirement):
            blockers.append({"code": "unpinned-runtime-dependency", "path": "pyproject.toml", "message": f"Stable runtime dependency is not exactly pinned: {requirement!r}."})
    return blockers, warnings


def _language_segments(
    path: Path,
    text: str,
    scan_python: bool,
    scan_identifiers: bool,
) -> list[tuple[int, str, str]]:
    if path.suffix.lower() == ".py" and (scan_python or scan_identifiers):
        segments: list[tuple[int, str, str]] = []
        try:
            for token in tokenize.generate_tokens(io.StringIO(text).readline):
                if scan_python and token.type in {tokenize.COMMENT, tokenize.STRING}:
                    kind = "comment" if token.type == tokenize.COMMENT else "string/docstring"
                    for offset, line in enumerate(token.string.splitlines() or [token.string]):
                        segments.append((token.start[0] + offset, kind, line))
                if scan_identifiers and token.type == tokenize.NAME:
                    segments.append((token.start[0], "identifier", token.string))
        except (tokenize.TokenError, IndentationError):
            return [(number, "source", line) for number, line in enumerate(text.splitlines(), start=1)]
        return segments
    if path.suffix.lower() == ".py":
        return []
    if path.suffix.lower() == ".md":
        segments = []
        in_fence = False
        fence_marker = ""
        for number, line in enumerate(text.splitlines(), start=1):
            stripped = line.lstrip()
            marker = stripped[:3]
            if marker in {"```", "~~~"}:
                if not in_fence:
                    in_fence = True
                    fence_marker = marker
                elif marker == fence_marker:
                    in_fence = False
                continue
            if in_fence:
                continue
            prose = re.sub(r"`[^`]*`", "", line)
            segments.append((number, "prose", prose))
        return segments
    return [(number, "prose", line) for number, line in enumerate(text.splitlines(), start=1)]


def _non_english_findings(tree: Path, manifest: dict[str, Any]) -> list[dict[str, str]]:
    language = manifest.get("language", {})
    markers = [str(item).casefold() for item in language.get("spanish_markers", [])]
    exceptions = [str(item).casefold() for item in language.get("english_exceptions", [])]
    scan_python = bool(language.get("scan_python_comments_and_strings", True))
    scan_identifiers = bool(language.get("scan_python_identifiers", True))
    findings: list[dict[str, str]] = []
    publication_extensions = {".md", ".rst", ".txt"}
    publication_names = {"LICENSE", "VERSION", ".gitignore", "ENVIRONMENT.example"}
    for path in sorted(item for item in tree.rglob("*") if item.is_file()):
        if path.suffix.lower() not in publication_extensions and path.name not in publication_names:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        matches: set[tuple[int, str, str]] = set()
        for line_number, kind, segment in _language_segments(path, text, scan_python, scan_identifiers):
            normalized = segment.casefold()
            for exception in exceptions:
                normalized = normalized.replace(exception, "")
            for marker in markers:
                if marker and marker in normalized:
                    matches.add((line_number, kind, marker))
        if matches:
            ordered = sorted(matches)
            examples = "; ".join(
                f"{kind} line {line_number} ({marker!r})"
                for line_number, kind, marker in ordered[:3]
            )
            additional = len(ordered) - min(len(ordered), 3)
            if additional:
                examples += f"; {additional} additional marker hits"
            findings.append({
                "code": "non-english-content",
                "path": path.relative_to(tree).as_posix(),
                "message": (
                    "Spanish-language markers were detected at " + examples
                    + "; Stable requires English content and human review."
                ),
            })
    return findings


def _candidate_security_findings(tree: Path, manifest: dict[str, Any]) -> list[dict[str, str]]:
    security_rules = [
        item for item in _compiled_rules(manifest.get("exclude", []))
        if str(item[0].get("id", "")).startswith("security-")
    ]
    findings: list[dict[str, str]] = []
    for path in sorted(tree.rglob("*")):
        relative = path.relative_to(tree).as_posix()
        if path.is_symlink():
            findings.append({"code": "candidate-symlink", "path": relative, "message": "Symbolic links are not allowed in the candidate tree."})
            continue
        if not path.is_file():
            continue
        match = _matching_rule(relative, security_rules)
        if match:
            findings.append({"code": "candidate-security-path", "path": relative, "message": "The candidate contains a path covered by a security exclusion."})
            continue
        try:
            data = path.read_bytes()
            text = data.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            findings.append({"code": "candidate-binary-file", "path": relative, "message": "The Stable core profile accepts text source only; binary data is not allowed."})
            continue
        secrets = _secret_findings(text)
        if secrets:
            findings.append({"code": "candidate-secret-pattern", "path": relative, "message": "High-confidence credential pattern detected: " + ", ".join(secrets)})
    return findings


def _candidate_privacy_findings(tree: Path, manifest: dict[str, Any]) -> list[dict[str, str]]:
    privacy = manifest.get("privacy", {})
    allowed_emails = {str(item).casefold() for item in privacy.get("allowed_emails", [])}
    allowed_emails.add("noreply@github.com")
    scan_paths = bool(privacy.get("scan_absolute_user_paths", True))
    findings: list[dict[str, str]] = []
    for path in sorted(item for item in tree.rglob("*") if item.is_file()):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(tree).as_posix()
        for email in EMAIL_PATTERN.findall(text):
            if email.casefold() not in allowed_emails:
                findings.append({
                    "code": "unapproved-email-address",
                    "path": relative,
                    "message": "An email address not explicitly approved for this distribution was found; the value is withheld from the report.",
                })
        if scan_paths and any(pattern.search(text) for pattern in PRIVATE_PATH_PATTERNS):
            findings.append({
                "code": "absolute-user-path",
                "path": relative,
                "message": "An absolute path containing a home-directory username was found; the path value is withheld from the report.",
            })
    return findings


def _validate_runtime_assets(tree: Path, version: str, project: dict[str, Any]) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    required = [
        "README.md", "CHANGELOG.md", "LICENSE", "VERSION", "pyproject.toml",
        "requirements.txt", "update_policy.json", "biorag.py", "mcp_server.py",
        "install.py", "graph_maintenance_daemon.py", "core/memory_store.py",
        "core/mcp_server/server.py", "core/mcp_server/update_checker.py",
        "skills/biorag-memory/SKILL.md",
        "plugin/opencode-biorag-remember-plugin.ts",
        "plugin/opencode-2-biorag-remember-plugin.ts",
        "db/__init__.py", "db/hebbian_clusters.json",
    ]
    for relative in required:
        if not (tree / relative).is_file():
            blockers.append({"code": "missing-runtime-file", "path": relative, "message": "Required Stable runtime or generated file is missing."})
    try:
        staged_version = validate_stable_tag((tree / "VERSION").read_text(encoding="utf-8").strip())
        staged_project = tomllib.loads((tree / "pyproject.toml").read_text(encoding="utf-8"))
        if staged_version != version or staged_project.get("project", {}).get("version") != pep440_version(version):
            blockers.append({"code": "staged-version-mismatch", "path": "VERSION", "message": "Candidate VERSION and Python package metadata do not match the requested Stable tag."})
        if staged_project.get("project", {}).get("readme") != "README.md":
            blockers.append({"code": "readme-metadata-mismatch", "path": "pyproject.toml", "message": "Python package metadata must reference the generated English README.md."})
    except (OSError, tomllib.TOMLDecodeError, PackagingError) as exc:
        blockers.append({"code": "staged-metadata-invalid", "path": "pyproject.toml", "message": f"Candidate metadata could not be validated ({exc.__class__.__name__})."})
    try:
        data = json.loads((tree / "db" / "hebbian_clusters.json").read_text(encoding="utf-8"))
        expected = {"clusters": [], "idf": {}, "dimension_names": {}, "threshold": 0.25, "total_nodes": 0}
        if data != expected:
            blockers.append({"code": "unsafe-hebbian-resource", "path": "db/hebbian_clusters.json", "message": "Stable must bundle only the empty fallback resource, not a learned or research-derived graph."})
    except (OSError, json.JSONDecodeError):
        blockers.append({"code": "invalid-hebbian-resource", "path": "db/hebbian_clusters.json", "message": "Generated fallback resource is missing or invalid JSON."})
    try:
        policy = json.loads((tree / "update_policy.json").read_text(encoding="utf-8"))
        if policy != {
            "schema_version": 1,
            "channel": "stable",
            "recommended_tag": version,
            "blocked_tags": [],
        }:
            blockers.append({"code": "invalid-update-policy", "path": "update_policy.json", "message": "Stable update policy does not exactly match the requested vX.X candidate."})
    except (OSError, json.JSONDecodeError):
        blockers.append({"code": "invalid-update-policy", "path": "update_policy.json", "message": "Generated update policy is missing or invalid JSON."})
    return blockers


def _tree_inventory(tree: Path) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for path in sorted(item for item in tree.rglob("*") if item.is_file()):
        relative = path.relative_to(tree).as_posix()
        inventory.append({"path": relative, "size_bytes": path.stat().st_size, "sha256": _sha256_file(path)})
    return inventory


def tree_sha256(tree: Path) -> str:
    digest = hashlib.sha256()
    for entry in _tree_inventory(tree):
        digest.update(entry["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(entry["sha256"].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _add_record_hashes(records: list[PathRecord], tree: Path) -> None:
    by_path = {record.path: record for record in records}
    for path in sorted(item for item in tree.rglob("*") if item.is_file()):
        relative = path.relative_to(tree).as_posix()
        if relative in by_path and by_path[relative].decision in {"included", "generated"}:
            record = by_path[relative]
            record.size_bytes = path.stat().st_size
            record.staged_sha256 = _sha256_file(path)
        else:
            records.append(PathRecord(
                relative, "generated", "Stable-specific transformation or generated overlay.",
                "stable-transform", size_bytes=path.stat().st_size,
                staged_sha256=_sha256_file(path), generated=True,
            ))


def _write_stage_reports(stage_dir: Path, payload: dict[str, Any]) -> None:
    manifest_path = stage_dir / "manifest.json"
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    included = [record for record in payload["files"] if record["decision"] in {"included", "generated"}]
    excluded = [record for record in payload["files"] if record["decision"] in {"excluded", "deleted"}]
    other = [record for record in payload["files"] if record["decision"] not in {"included", "generated", "excluded", "deleted"}]
    lines = [
        "# MemoryBioRAG-Stable staging report",
        "",
        f"- **Status:** `{payload['status'].upper()}`",
        f"- **Version:** `{payload['version']}`",
        f"- **Candidate tree SHA-256:** `{payload['tree_sha256']}`",
        f"- **Included or generated files:** {len(included)}",
        f"- **Excluded or deleted paths:** {len(excluded)}",
        f"- **Unclassified or blocked paths:** {len(other)}",
        "- **Publication actions:** none; this is a local preview only.",
        "",
        "## Blockers",
        "",
    ]
    if payload["blockers"]:
        for problem in payload["blockers"]:
            lines.append(f"- `{problem.get('code')}` — `{problem.get('path', '-')}`: {problem.get('message')}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Warnings", ""])
    if payload["warnings"]:
        for problem in payload["warnings"]:
            lines.append(f"- `{problem.get('code')}` — `{problem.get('path', '-')}`: {problem.get('message')}")
    else:
        lines.append("- None.")
    lines.extend([
        "",
        "## Included and generated files",
        "",
        "| Path | Source status | SHA-256 | Reason |",
        "|---|---|---|---|",
    ])
    for record in included:
        path = record["path"].replace("|", "\\|")
        status = record.get("source_status") or "generated"
        digest = record.get("staged_sha256") or "-"
        reason = record.get("reason", "").replace("|", "\\|")
        lines.append(f"| `{path}` | {status} | `{digest}` | {reason} |")
    lines.extend([
        "",
        "## Excluded and deleted paths",
        "",
        "| Path | Decision | Reason |",
        "|---|---|---|",
    ])
    for record in excluded:
        path = record["path"].replace("|", "\\|")
        reason = record.get("reason", "").replace("|", "\\|")
        lines.append(f"| `{path}` | {record['decision']} | {reason} |")
    lines.extend([
        "",
        "## Unclassified or blocked paths",
        "",
    ])
    if other:
        for record in other:
            lines.append(f"- `{record['path']}` — {record['decision']}: {record['reason']}")
    else:
        lines.append("- None.")
    lines.extend([
        "",
        "## Review notes",
        "",
        "The single current preview is built from the working tree without changing Git's index. "
        "A release command requires an explicit version, this preview path, and the exact tree SHA-256 shown above. "
        "The release command only creates local artifacts outside .staging; publishing requires separate authorization.",
        "",
    ])
    (stage_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    (stage_dir / "TREE_SHA256").write_text(payload["tree_sha256"] + "\n", encoding="ascii")


def _is_git_ignored(root: Path, relative: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", "--", relative], cwd=root,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def _safe_repo_output_root(root: Path, relative: str, label: str) -> Path:
    normalized = _normalized_relative(relative)
    parts = PurePosixPath(normalized).parts
    target = root.joinpath(*parts)
    cursor = root
    for part in parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise PackagingError(f"{label} path contains a symbolic link: {normalized!r}.")
    resolved = target.resolve()
    if not resolved.is_relative_to(root):
        raise PackagingError(f"{label} path must remain inside the source repository.")
    return resolved


STAGING_ROOT_RELATIVE = ".staging"
LEGACY_STAGES_RELATIVE = ".staging/stable/stages"
LEGACY_RELEASES_RELATIVE = ".staging/stable/releases"
LEGACY_RUN_PATTERN = re.compile(r"^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)-\d{8}T\d{6}Z-[0-9a-f]{8}$")


def _create_preview_paths(root: Path, manifest: dict[str, Any]) -> tuple[Path, Path]:
    """Return the one current preview path and a temporary sibling build directory."""
    relative = _normalized_relative(manifest["output"]["staging_directory"])
    preview_dir = _safe_repo_output_root(root, relative, "Stable preview")
    ignored_probe = (PurePosixPath(relative) / "ignore-check").as_posix()
    if not _is_git_ignored(root, ignored_probe):
        raise PackagingError(
            f"Preview path {relative!r} is not ignored by Git. Add an ignore rule before staging."
        )
    try:
        preview_dir.parent.mkdir(parents=True, exist_ok=True)
        build_dir = preview_dir.parent / f".preview-build-{uuid.uuid4().hex[:12]}"
        build_dir.mkdir(parents=False, exist_ok=False)
    except OSError as exc:
        raise PackagingError(f"Could not create an isolated preview workspace ({exc.__class__.__name__}).") from exc
    return preview_dir, build_dir


def _is_generated_preview(
    path: Path,
    root: Path,
    manifest: dict[str, Any],
    *,
    expected_stage_directory: str | None = None,
) -> bool:
    """Recognize a complete tool-generated preview before replacing or releasing it."""
    try:
        relative = path.relative_to(root).as_posix()
        expected = expected_stage_directory or relative
        if path.is_symlink() or not path.is_dir():
            return False
        children = {item.name: item for item in path.iterdir()}
        allowed = {"tree", "manifest.json", "report.md", "TREE_SHA256", "wheel-build.log"}
        required = {"tree", "manifest.json", "report.md", "TREE_SHA256"}
        if not required.issubset(children) or set(children) - allowed:
            return False
        if any(item.is_symlink() for item in path.rglob("*")):
            return False
        if not children["tree"].is_dir():
            return False
        if any(not item.is_file() for name, item in children.items() if name != "tree"):
            return False
        payload = json.loads(children["manifest.json"].read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return False
        if (
            payload.get("schema_version") != 1
            or payload.get("project_name") != manifest["project_name"]
            or payload.get("candidate_tree") != "tree"
            or payload.get("stage_directory") != expected
            or payload.get("status") not in {"ready", "blocked"}
            or not isinstance(payload.get("version"), str)
            or not STABLE_TAG_PATTERN.fullmatch(payload["version"])
        ):
            return False
        inventory = _tree_inventory(children["tree"])
        digest = tree_sha256(children["tree"])
        if payload.get("tree_files") != inventory or payload.get("tree_sha256") != digest:
            return False
        if children["TREE_SHA256"].read_text(encoding="ascii").strip() != digest:
            return False
        return True
    except (OSError, ValueError, UnicodeError, TypeError, json.JSONDecodeError):
        return False


def _prune_legacy_stage_runs(root: Path, manifest: dict[str, Any]) -> None:
    """Remove only fully verified previews created by the previous multi-stage layout."""
    legacy_root = root / Path(*PurePosixPath(LEGACY_STAGES_RELATIVE).parts)
    if legacy_root.is_symlink():
        raise PackagingError("Legacy stage directory is a symbolic link; inspect it before continuing.")
    if not legacy_root.exists():
        return
    if not legacy_root.is_dir():
        raise PackagingError("Legacy stage output exists but is not a directory; inspect it before continuing.")

    verified: list[Path] = []
    for child in sorted(legacy_root.iterdir(), key=lambda item: item.name):
        relative = child.relative_to(root).as_posix()
        if child.is_symlink() or not child.is_dir():
            raise PackagingError(f"Unrecognized data in legacy stage directory: {child.name!r}; inspect it manually.")
        if not LEGACY_RUN_PATTERN.fullmatch(child.name) or not _is_generated_preview(child, root, manifest):
            raise PackagingError(f"Unrecognized directory in legacy stage output: {relative}; inspect it manually.")
        verified.append(child)

    for child in verified:
        try:
            shutil.rmtree(child)
        except OSError as exc:
            raise PackagingError(f"Could not remove the verified legacy preview {child.name!r} ({exc.__class__.__name__}).") from exc
    try:
        legacy_root.rmdir()
    except OSError as exc:
        raise PackagingError(f"Legacy stage directory is not empty after pruning ({exc.__class__.__name__}); inspect it manually.") from exc


def _is_generated_legacy_release(path: Path, root: Path, manifest: dict[str, Any]) -> bool:
    try:
        match = LEGACY_RUN_PATTERN.fullmatch(path.name)
        if path.is_symlink() or not path.is_dir() or not match:
            return False
        payload_path = path / "release-manifest.json"
        report_path = path / "report.md"
        tree = path / "tree"
        if any(item.is_symlink() for item in path.rglob("*")):
            return False
        if payload_path.is_symlink() or report_path.is_symlink() or not payload_path.is_file() or not report_path.is_file():
            return False
        if tree.is_symlink() or not tree.is_dir():
            return False
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return False
        version = path.name.split("-", 1)[0]
        if (
            payload.get("schema_version") != 1
            or payload.get("project_name") != manifest["project_name"]
            or payload.get("status") != "prepared-locally"
            or payload.get("version") != version
            or payload.get("source_tree_sha256") != tree_sha256(tree)
        ):
            return False
        artifacts = payload.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            return False
        artifact_names: set[str] = set()
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                return False
            artifact_path = artifact.get("path")
            if not isinstance(artifact_path, str):
                return False
            normalized = _normalized_relative(artifact_path)
            if len(PurePosixPath(normalized).parts) != 1 or normalized in artifact_names:
                return False
            artifact_file = path / normalized
            if artifact_file.is_symlink() or not artifact_file.is_file():
                return False
            size = artifact.get("size_bytes")
            digest = artifact.get("sha256")
            if isinstance(size, bool) or not isinstance(size, int) or artifact_file.stat().st_size != size:
                return False
            if not isinstance(digest, str) or _sha256_file(artifact_file) != digest:
                return False
            artifact_names.add(normalized)
        expected = {"tree", "release-manifest.json", "report.md", *artifact_names}
        return {item.name for item in path.iterdir()} == expected
    except (OSError, ValueError, UnicodeError, TypeError, json.JSONDecodeError, PackagingError):
        return False


def _migrate_legacy_release_outputs(root: Path, manifest: dict[str, Any]) -> None:
    """Move verified old local release artifacts out of .staging without deleting them."""
    legacy_root = root / Path(*PurePosixPath(LEGACY_RELEASES_RELATIVE).parts)
    if legacy_root.is_symlink():
        raise PackagingError("Legacy release output is a symbolic link; inspect it before continuing.")
    if not legacy_root.exists():
        return
    if not legacy_root.is_dir():
        raise PackagingError("Legacy release output exists but is not a directory; inspect it before continuing.")
    relative = _normalized_relative(manifest["output"]["release_directory"])
    destination = _safe_repo_output_root(root, relative, "Release output")
    if not _is_git_ignored(root, (PurePosixPath(relative) / "ignore-check").as_posix()):
        raise PackagingError("The new local release output path is not ignored by Git.")

    items = sorted(legacy_root.iterdir(), key=lambda path: path.name)
    for item in items:
        if not _is_generated_legacy_release(item, root, manifest):
            raise PackagingError(f"Unrecognized legacy release output {item.name!r}; inspect it manually before moving anything.")
        target = destination / item.name
        if target.exists() or target.is_symlink():
            raise PackagingError(f"Cannot migrate legacy release output because {target.name!r} already exists.")
    if not items:
        try:
            legacy_root.rmdir()
        except OSError as exc:
            raise PackagingError(f"Legacy release directory is not empty ({exc.__class__.__name__}); inspect it manually.") from exc
        return

    try:
        destination.mkdir(parents=True, exist_ok=True)
        for item in items:
            os.replace(item, destination / item.name)
        legacy_root.rmdir()
    except OSError as exc:
        raise PackagingError(f"Could not migrate verified local release artifacts ({exc.__class__.__name__}).") from exc


def _validate_single_preview_layout(
    root: Path,
    manifest: dict[str, Any],
    build_dir: Path | None,
    preview_dir: Path,
) -> None:
    relative = _normalized_relative(manifest["output"]["staging_directory"])
    parts = PurePosixPath(relative).parts
    if len(parts) != 3 or parts[0] != STAGING_ROOT_RELATIVE or parts[-1] != "preview":
        raise PackagingError("The Stable preview must live at .staging/<profile>/preview.")
    staging_root = root / STAGING_ROOT_RELATIVE
    if staging_root.is_symlink() or not staging_root.is_dir():
        raise PackagingError("The local .staging root is missing or unsafe.")
    current = staging_root
    for part in parts[1:-1]:
        if {item.name for item in current.iterdir()} != {part}:
            raise PackagingError("Unrecognized data remains in .staging; inspect it manually so only the current preview remains.")
        current = current / part
        if current.is_symlink() or not current.is_dir():
            raise PackagingError("The Stable preview parent path is missing or unsafe.")
    if current != preview_dir.parent:
        raise PackagingError("The configured Stable preview is not at the expected staging path.")
    allowed = {preview_dir.name}
    if build_dir is not None:
        allowed.add(build_dir.name)
    if {item.name for item in current.iterdir()} - allowed:
        raise PackagingError("Unrecognized data remains beside the Stable preview; inspect it manually before continuing.")


def _promote_current_preview(
    root: Path,
    manifest: dict[str, Any],
    build_dir: Path,
    preview_dir: Path,
) -> None:
    """Replace the current preview only after its tree and reports are complete."""
    stage_relative = _normalized_relative(manifest["output"]["staging_directory"])
    if not _is_generated_preview(build_dir, root, manifest, expected_stage_directory=stage_relative):
        raise PackagingError("The new preview is incomplete or failed its tree-hash integrity check.")
    had_previous = preview_dir.exists() or preview_dir.is_symlink()
    if had_previous and not _is_generated_preview(preview_dir, root, manifest):
        raise PackagingError("Refusing to overwrite unrecognized data at the single Stable preview path.")
    _prune_legacy_stage_runs(root, manifest)
    _migrate_legacy_release_outputs(root, manifest)
    _validate_single_preview_layout(root, manifest, build_dir, preview_dir)

    backup = preview_dir.parent / f".preview-backup-{uuid.uuid4().hex[:12]}"
    if backup.exists() or backup.is_symlink():
        raise PackagingError("A preview backup path unexpectedly exists; inspect it before continuing.")
    if had_previous:
        try:
            os.replace(preview_dir, backup)
        except OSError as exc:
            raise PackagingError(f"Could not move the previous preview aside ({exc.__class__.__name__}).") from exc
    try:
        os.replace(build_dir, preview_dir)
    except OSError as exc:
        if had_previous and backup.exists() and not preview_dir.exists():
            try:
                os.replace(backup, preview_dir)
            except OSError as restore_exc:
                raise PackagingError("Preview promotion failed and the previous preview could not be restored; inspect .staging manually.") from restore_exc
        raise PackagingError(f"Could not promote the completed preview ({exc.__class__.__name__}).") from exc
    if had_previous:
        try:
            shutil.rmtree(backup)
        except OSError as exc:
            try:
                os.replace(preview_dir, build_dir)
                os.replace(backup, preview_dir)
            except OSError as restore_exc:
                raise PackagingError("Could not remove the previous preview backup or restore the prior preview; inspect .staging manually.") from restore_exc
            raise PackagingError(f"Could not remove the verified previous preview ({exc.__class__.__name__}); the old preview was restored.") from exc



def _validate_required_source(root: Path, manifest: dict[str, Any], blockers: list[dict[str, str]]) -> None:
    for relative in manifest.get("required_source_paths", []):
        path = root / Path(*PurePosixPath(relative).parts)
        if not path.is_file() or path.is_symlink():
            blockers.append({
                "code": "missing-required-source",
                "path": relative,
                "message": "A required source file is missing or is not a regular file.",
            })


def _copy_selected_sources(root: Path, tree: Path, records: list[PathRecord], manifest: dict[str, Any], blockers: list[dict[str, str]]) -> None:
    for record in records:
        if record.decision != "included":
            continue
        _copy_source_file(root, tree, record, manifest, blockers)


def _generate_overlay(root: Path, tree: Path, version: str, project_text: str, dependencies: list[str], records: list[PathRecord]) -> None:
    files = {
        "README.md": (_render_template(root, "release/README.template.md", version).encode("utf-8"), "Generated from the reviewed English Stable README template."),
        "CHANGELOG.md": (_render_template(root, "release/CHANGELOG.template.md", version).encode("utf-8"), "Generated from the reviewed English Stable changelog template; it contains no imported benchmark claims."),
        ".gitignore": ((root / "release" / "gitignore.template").read_bytes(), "Generated from the reviewed English Stable ignore template."),
        "ENVIRONMENT.example": ((root / "release" / "env.example.template").read_bytes(), "Generated safe English environment example with no credentials."),
        "skills/biorag-memory/SKILL.md": (
            _render_template(root, "release/SKILL.template.md", version).encode("utf-8"),
            "Generated English BioRAG agent skill; install.py copies it to supported agent skill directories.",
        ),
    }
    for relative, (data, reason) in files.items():
        _write_generated(tree, relative, data, reason, records)
    requirement_lines: list[str] = []
    for dependency in dependencies:
        value = str(dependency).strip()
        if "==" not in value:
            raise PackagingError(f"Runtime dependency is not exactly pinned: {value!r}")
        requirement_lines.append(value)
    if not requirement_lines:
        raise PackagingError("pyproject.toml declares no runtime dependencies.")
    requirements = ("\n".join(requirement_lines) + "\n").encode("utf-8")
    _write_generated(tree, "requirements.txt", requirements, "Generated from the exactly pinned runtime dependencies in pyproject.toml.", records)
    policy = {
        "schema_version": 1,
        "channel": "stable",
        "recommended_tag": version,
        "blocked_tags": [],
    }
    _write_generated(
        tree, "update_policy.json",
        (json.dumps(policy, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        "Generated Stable update policy for the explicitly selected candidate version.", records,
    )
    init = '"""Bundled, non-personal default resources for the Stable distribution."""\n'
    _write_generated(tree, "db/__init__.py", init.encode("utf-8"), "Generated package marker so the fallback JSON is included in wheels.", records)
    fallback = (root / "release" / "empty_hebbian_clusters.json").read_bytes()
    _write_generated(tree, "db/hebbian_clusters.json", fallback, "Generated empty fallback; source-derived clusters and IDF data are deliberately not copied.", records)


def _transform_candidate(root: Path, tree: Path, version: str, records: list[PathRecord], blockers: list[dict[str, str]]) -> list[str]:
    notes: list[str] = []
    try:
        project_path = tree / "pyproject.toml"
        transformed, dependencies = _transform_project_metadata(project_path.read_text(encoding="utf-8"), version)
        project_path.write_text(transformed, encoding="utf-8")
        _update_record_hash(records, "pyproject.toml", tree)
        version_path = tree / "VERSION"
        version_path.write_text(f"{version}\n", encoding="utf-8")
        _update_record_hash(records, "VERSION", tree)
        _generate_overlay(root, tree, version, transformed, dependencies, records)
        notes.extend(_transform_hebbian_schema(tree))
        notes.extend(_apply_stable_identity(tree))
    except (OSError, UnicodeDecodeError, PackagingError) as exc:
        blockers.append({"code": "stable-transform-failed", "path": "-", "message": str(exc)})
    for relative in ("biorag.py", "install.py", "core/mcp_server/update_checker.py"):
        if (tree / relative).is_file():
            _update_record_hash(records, relative, tree)
    return notes


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", value)
    return tuple(int(part) for part in parts) if parts else ()


def _check_build_requirements(project: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for requirement in project.get("build-system", {}).get("requires", []):
        requirement = str(requirement)
        match = re.match(r"\s*([A-Za-z0-9_.-]+)\s*(?:>=\s*([0-9.]+))?", requirement)
        if not match:
            continue
        name, minimum = match.groups()
        try:
            installed = importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError:
            missing.append(f"{name} is not installed")
            continue
        if minimum and _version_tuple(installed) < _version_tuple(minimum):
            missing.append(f"{name}>={minimum} is required (found {installed})")
    return missing


def _verify_wheel(
    tree: Path,
    project: dict[str, Any],
    scratch_root: Path,
    log_path: Path,
    preserve_wheel: Path | None = None,
) -> dict[str, Any]:
    build_requirements = _check_build_requirements(project)
    if build_requirements:
        raise PackagingError("Missing local build requirements: " + "; ".join(build_requirements))
    with tempfile.TemporaryDirectory(prefix="stable-wheel-check-", dir=scratch_root) as temp_name:
        temp = Path(temp_name)
        source = temp / "source"
        shutil.copytree(tree, source)
        dist = temp / "dist"
        dist.mkdir()
        command = [
            sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
            "--wheel-dir", str(dist), str(source),
        ]
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, check=False, timeout=240, cwd=temp)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PackagingError(f"Local wheel build could not complete: {exc.__class__.__name__}.") from exc
        log_path.write_text(result.stdout or "", encoding="utf-8")
        if result.returncode != 0:
            tail = "\n".join((result.stdout or "").splitlines()[-12:])
            raise PackagingError(f"Local wheel build failed with exit code {result.returncode}. See wheel-build.log.\n{tail}")
        wheels = sorted(dist.glob("*.whl"))
        if len(wheels) != 1:
            raise PackagingError(f"Expected one wheel from the candidate build; found {len(wheels)}.")
        wheel = wheels[0]
        with zipfile.ZipFile(wheel) as archive:
            names = set(archive.namelist())
            required_entries = {
                "biorag.py", "mcp_server.py", "install.py", "graph_maintenance_daemon.py",
                "core/memory_store.py", "core/mcp_server/update_checker.py",
                "db/__init__.py", "db/hebbian_clusters.json",
            }
            missing = sorted(required_entries - names)
            if missing:
                raise PackagingError("Wheel is missing required modules/resources: " + ", ".join(missing))
            forbidden_suffixes = (".db", ".sqlite", ".sqlite3", ".sql", ".jsonl", ".pem", ".key")
            forbidden_parts = {"tests", "docs", "snapshots", "MemoryBioRAG_Data", "google_drive"}
            for name in sorted(names):
                path = PurePosixPath(name)
                if path.suffix.lower() in forbidden_suffixes or any(part in forbidden_parts for part in path.parts):
                    raise PackagingError(f"Wheel contains a forbidden file: {name}")
            metadata_paths = [name for name in names if name.endswith(".dist-info/METADATA")]
            if len(metadata_paths) != 1:
                raise PackagingError("Wheel must contain exactly one dist-info/METADATA file.")
            metadata_path = metadata_paths[0]
            dist_info_root = metadata_path.rsplit("/", 1)[0]
            for name in sorted(names):
                if name.startswith(dist_info_root + "/"):
                    continue
                source_file = tree / Path(*PurePosixPath(name).parts)
                if not source_file.is_file() or source_file.is_symlink():
                    raise PackagingError(f"Wheel contains a payload file not present in the reviewed source tree: {name}")
                if archive.read(name) != source_file.read_bytes():
                    raise PackagingError(f"Wheel payload differs from the reviewed source file: {name}")
            metadata_text = archive.read(metadata_path).decode("utf-8")
            version_match = re.search(r"(?m)^Version: (.+)$", metadata_text)
            if not version_match:
                raise PackagingError("Wheel metadata does not declare a version.")
            expected = str(project.get("project", {}).get("version", ""))
            if version_match.group(1).strip() != expected:
                raise PackagingError("Wheel metadata version does not match pyproject.toml.")
            if _secret_findings(metadata_text):
                raise PackagingError("Wheel METADATA contains a high-confidence credential pattern.")
        install_dir = temp / "install"
        install_dir.mkdir()
        install_command = [sys.executable, "-m", "pip", "install", "--no-deps", "--no-compile", "--target", str(install_dir), str(wheel)]
        installed = subprocess.run(install_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, check=False, timeout=120, cwd=temp)
        if installed.returncode != 0:
            log_path.write_text((log_path.read_text(encoding="utf-8") if log_path.exists() else "") + "\n" + (installed.stdout or ""), encoding="utf-8")
            raise PackagingError("The candidate wheel could not be installed into a temporary target; see wheel-build.log.")
        smoke = (
            "from pathlib import Path\n"
            "import json\n"
            "import core.sdm as sdm\n"
            "import core.mcp_server.update_checker as checker\n"
            "assert Path(sdm._HEBBIAN_PATH).is_file()\n"
            "expected_hebbian = {'clusters': [], 'idf': {}, 'dimension_names': {}, 'threshold': 0.25, 'total_nodes': 0}\n"
            "assert json.loads(Path(sdm._HEBBIAN_PATH).read_text(encoding='utf-8')) == expected_hebbian\n"
            "assert sdm.sdm_info()['clusters_hebbianos'] == 0\n"
            "assert 'MemoryBioRAG-Stable' in checker._POLICY_API\n"
            "assert 'MemoryBioRAG-Stable' in checker._TAGS_PAGE\n"
            "assert checker._is_stable_tag('v36.1')\n"
            "assert not checker._is_stable_tag('v36.1.0')\n"
            "assert not checker._is_stable_tag('v36.1-rc1')\n"
        )
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env["PYTHONPATH"] = str(install_dir)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        empty_cwd = temp / "empty-cwd"
        empty_cwd.mkdir()
        smoke_result = subprocess.run(
            [sys.executable, "-c", smoke], cwd=empty_cwd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            check=False, timeout=60,
        )
        if smoke_result.returncode != 0:
            log_path.write_text((log_path.read_text(encoding="utf-8") if log_path.exists() else "") + "\n" + (smoke_result.stdout or ""), encoding="utf-8")
            raise PackagingError("Installed wheel resource/import smoke test failed; see wheel-build.log.")
        if preserve_wheel is not None:
            preserve_wheel.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(wheel, preserve_wheel)
        return {
            "status": "passed",
            "wheel_name": wheel.name,
            "wheel_size_bytes": wheel.stat().st_size,
            "wheel_sha256": _sha256_file(wheel),
            "checked_entries": len(names),
            "local_resource_smoke_test": "passed",
        }


def _copy_tree(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, symlinks=False)


def _build_archive(tree: Path, destination: Path, version: str, prefix: str) -> None:
    archive_prefix = f"{prefix}-{version}"
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in tree.rglob("*") if item.is_file()):
            relative = path.relative_to(tree).as_posix()
            info = zipfile.ZipInfo(f"{archive_prefix}/{relative}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes())


def create_stage(root: Path = REPOSITORY_ROOT, requested_version: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    manifest = _load_manifest(root)
    source_version, _ = _read_source_version(root, manifest)
    if requested_version is None:
        raise PackagingError("Stage requires an explicit --version vX.X; no version is selected automatically.")
    version = validate_stable_tag(requested_version)

    preview_dir, build_dir = _create_preview_paths(root, manifest)
    promoted = False
    try:
        tree = build_dir / "tree"
        tree.mkdir()
        blockers: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        state = _git_state(root)
        _validate_required_source(root, manifest, blockers)
        records = _walk_source(root, manifest, state, blockers)
        _copy_selected_sources(root, tree, records, manifest, blockers)
        transform_notes = _transform_candidate(root, tree, version, records, blockers)

        try:
            project = tomllib.loads((tree / "pyproject.toml").read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            project = {}
            blockers.append({"code": "candidate-metadata-invalid", "path": "pyproject.toml", "message": f"Candidate project metadata could not be parsed ({exc.__class__.__name__})."})

        local_blockers, dependency_warnings = _collect_imports(tree, project, manifest)
        blockers.extend(local_blockers)
        warnings.extend(dependency_warnings)
        blockers.extend(_validate_runtime_assets(tree, version, project))
        blockers.extend(_candidate_security_findings(tree, manifest))
        blockers.extend(_candidate_privacy_findings(tree, manifest))
        blockers.extend(_non_english_findings(tree, manifest))

        wheel_check: dict[str, Any] = {"status": "not-run"}
        if project and (tree / "pyproject.toml").is_file():
            try:
                wheel_check = _verify_wheel(tree, project, build_dir, build_dir / "wheel-build.log")
            except PackagingError as exc:
                wheel_check = {"status": "blocked", "detail": str(exc)}
                blockers.append({"code": "wheel-validation-failed", "path": "pyproject.toml", "message": str(exc)})

        _add_record_hashes(records, tree)
        files = [asdict(record) for record in sorted(records, key=lambda item: (item.path, item.decision))]
        tree_digest = tree_sha256(tree)
        status = "ready" if not blockers else "blocked"
        payload: dict[str, Any] = {
            "schema_version": 1,
            "project_name": manifest["project_name"],
            "repository_url": manifest["repository_url"],
            "version": version,
            "source_version": source_version,
            "status": status,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "stage_directory": preview_dir.relative_to(root).as_posix(),
            "candidate_tree": "tree",
            "tree_sha256": tree_digest,
            "tree_files": _tree_inventory(tree),
            "transforms": transform_notes,
            "wheel_validation": wheel_check,
            "blockers": blockers,
            "warnings": warnings,
            "files": files,
            "publication_actions": [],
        }
        _write_stage_reports(build_dir, payload)
        _promote_current_preview(root, manifest, build_dir, preview_dir)
        promoted = True
        return payload
    finally:
        if not promoted and build_dir.exists():
            shutil.rmtree(build_dir)



def _safe_stage_tree(root: Path, manifest: dict[str, Any], stage_directory: str | Path) -> tuple[Path, dict[str, Any]]:
    stage_relative = _normalized_relative(manifest["output"]["staging_directory"])
    stage_dir = _safe_repo_output_root(root, stage_relative, "Stable preview")
    supplied = Path(stage_directory)
    if not supplied.is_absolute():
        supplied = root / supplied
    supplied = Path(os.path.abspath(supplied))
    if supplied != stage_dir:
        raise PackagingError(
            f"Only the current Stable preview may be released; use {stage_relative!r}. "
            "Each new stage replaces that preview."
        )
    if not stage_dir.is_dir():
        raise PackagingError("The current Stable preview does not exist or is not a regular directory.")
    _validate_single_preview_layout(root, manifest, None, stage_dir)
    report_path = stage_dir / "manifest.json"
    if report_path.is_symlink() or not report_path.is_file():
        raise PackagingError("The current preview has no regular manifest.json.")
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackagingError("The current preview has no valid manifest.json.") from exc
    if payload.get("schema_version") != 1 or payload.get("candidate_tree") != "tree":
        raise PackagingError("The current preview manifest schema is invalid or unsupported.")
    if payload.get("stage_directory") != stage_relative:
        raise PackagingError("Preview manifest path does not match the configured current-preview path.")
    if not _is_generated_preview(stage_dir, root, manifest):
        raise PackagingError("The current preview is incomplete or its tree/report integrity checks failed.")
    return stage_dir, payload


def create_release(
    root: Path = REPOSITORY_ROOT,
    version: str | None = None,
    stage_directory: str | Path | None = None,
    confirmed_tree_sha256: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    manifest = _load_manifest(root)
    if version is None:
        raise PackagingError("Release requires an explicit --version vX.X; no version is selected automatically.")
    version = validate_stable_tag(version)
    source_version, _ = _read_source_version(root, manifest)
    if stage_directory is None:
        raise PackagingError("Release requires --stage-dir so it can promote the reviewed preview, not recopy a moving worktree.")
    if not confirmed_tree_sha256:
        raise PackagingError("Release requires --confirm-tree-sha256 copied from the reviewed stage report.")
    stage_dir, stage_manifest = _safe_stage_tree(root, manifest, stage_directory)
    if stage_manifest.get("status") != "ready":
        raise PackagingError("The selected stage is blocked; resolve every blocker and create a fresh preview before release.")
    if stage_manifest.get("version") != version:
        raise PackagingError("The selected stage version does not match --version.")
    tree = stage_dir / "tree"
    if not tree.is_dir() or tree.is_symlink():
        raise PackagingError("The selected stage has no safe candidate tree.")
    digest = tree_sha256(tree)
    if digest != stage_manifest.get("tree_sha256"):
        raise PackagingError("The stage tree changed after preview; create and review a fresh stage.")
    if digest != confirmed_tree_sha256:
        raise PackagingError("The supplied SHA-256 does not match the reviewed candidate tree.")
    stage_relative_path = stage_dir.relative_to(root).as_posix()
    if not _is_git_ignored(root, stage_relative_path):
        raise PackagingError("The selected stage is no longer ignored by Git; update .gitignore before preparing artifacts.")
    release_relative = _normalized_relative(manifest["output"]["release_directory"])
    release_probe = (PurePosixPath(release_relative) / "ignore-check").as_posix()
    if not _is_git_ignored(root, release_probe):
        raise PackagingError("The local release output directory is not ignored by Git.")
    release_root = _safe_repo_output_root(root, release_relative, "Release output")

    try:
        project = tomllib.loads((tree / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise PackagingError("The staged pyproject.toml is invalid.") from exc
    blockers = _validate_runtime_assets(tree, version, project)
    blockers.extend(_candidate_security_findings(tree, manifest))
    blockers.extend(_candidate_privacy_findings(tree, manifest))
    blockers.extend(_non_english_findings(tree, manifest))
    local_blockers, _ = _collect_imports(tree, project, manifest)
    blockers.extend(local_blockers)
    if blockers:
        raise PackagingError("Candidate validation failed: " + "; ".join(f"{item['code']} ({item['path']})" for item in blockers[:8]))

    try:
        release_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PackagingError(f"Could not create the ignored local release directory ({exc.__class__.__name__}).") from exc
    release_dir = release_root / f"{version}-{_utc_stamp()}-{uuid.uuid4().hex[:8]}"
    if release_dir.exists() or release_dir.is_symlink():
        raise PackagingError("The randomly named release output already exists; retry after inspection.")

    with tempfile.TemporaryDirectory(prefix=".stable-release-build-", dir=release_root) as temporary:
        scratch = Path(temporary)
        validated_wheel = scratch / "validated-wheel.whl"
        wheel_info = _verify_wheel(
            tree, project, scratch, scratch / "wheel-build.log", preserve_wheel=validated_wheel,
        )
        archive_temp = scratch / f"{manifest['output']['source_archive_prefix']}-{version}.zip"
        _build_archive(tree, archive_temp, version, manifest["output"]["source_archive_prefix"])

        candidate_dir = scratch / "candidate"
        candidate_dir.mkdir()
        _copy_tree(tree, candidate_dir / "tree")
        archive_path = candidate_dir / archive_temp.name
        shutil.copy2(archive_temp, archive_path)
        final_wheel = candidate_dir / str(wheel_info["wheel_name"])
        shutil.copy2(validated_wheel, final_wheel)
        if _sha256_file(final_wheel) != wheel_info["wheel_sha256"]:
            raise PackagingError("The validated wheel changed while being copied to the local release directory.")

        artifacts = [
            {"path": archive_path.name, "size_bytes": archive_path.stat().st_size, "sha256": _sha256_file(archive_path)},
            {"path": final_wheel.name, "size_bytes": final_wheel.stat().st_size, "sha256": _sha256_file(final_wheel)},
        ]
        release_payload = {
            "schema_version": 1,
            "project_name": manifest["project_name"],
            "version": version,
            "status": "prepared-locally",
            "source_stage": stage_dir.relative_to(root).as_posix(),
            "source_tree_sha256": digest,
            "wheel_validation": wheel_info,
            "artifacts": artifacts,
            "publication_actions": [],
            "notes": "No commit, tag, push, merge, upload, or publication was performed.",
        }
        (candidate_dir / "release-manifest.json").write_text(
            json.dumps(release_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        (candidate_dir / "report.md").write_text(
            "# Local Stable release candidate\n\n"
            f"- Version: `{version}`\n- Status: `prepared-locally`\n"
            f"- Source tree SHA-256: `{digest}`\n"
            "- Publication actions: none.\n\n"
            "Review the `tree/`, source archive, wheel, and `release-manifest.json`. This command does not publish anything.\n",
            encoding="utf-8",
        )
        candidate_dir.rename(release_dir)

    return release_payload | {"release_directory": release_dir.relative_to(root).as_posix()}
