"""Focused regression tests for the Stable exporter; use temporary copies only."""
from __future__ import annotations

import ast
import json
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.stable_packaging import (
    PackagingError,
    _apply_stable_identity,
    _candidate_privacy_findings,
    _collect_imports,
    _create_preview_paths,
    _git_state,
    _load_manifest,
    _non_english_findings,
    _promote_current_preview,
    _secret_findings,
    _sha256_file,
    _tree_inventory,
    _transform_hebbian_schema,
    _transform_project_metadata,
    _walk_source,
    create_release,
    path_matches,
    tree_sha256,
    validate_stable_tag,
)

ROOT = Path(__file__).resolve().parents[1]


class StableVersionTests(unittest.TestCase):
    def test_manifest_validation_rejects_unsafe_and_ambiguous_configuration(self) -> None:
        original = (ROOT / "release_manifest.toml").read_text(encoding="utf-8")
        invalid_cases = {
            "boolean schema version": original.replace("schema_version = 1", "schema_version = true", 1),
            "parent traversal in include glob": original.replace(
                'patterns = [\n  "biorag.py",', 'patterns = [\n  "../escape.py",', 1,
            ),
            "nested output roots": original.replace(
                'release_directory = ".stable-release/stable/releases"',
                'release_directory = ".staging/stable/preview/releases"',
                1,
            ),
            "missing security exclusion": original.replace(
                'id = "security-private-and-generated-paths"',
                'id = "safety-private-and-generated-paths"',
                1,
            ).replace(
                'id = "security-secrets-and-local-data"',
                'id = "safety-secrets-and-local-data"',
                1,
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "release_manifest.toml"
            self.assertEqual(_load_manifest(ROOT)["schema_version"], 1)
            for label, content in invalid_cases.items():
                with self.subTest(case=label):
                    self.assertNotEqual(content, original)
                    manifest_path.write_text(content, encoding="utf-8")
                    with self.assertRaises(PackagingError):
                        _load_manifest(root)
            manifest_path.write_bytes(b" " * (256 * 1024 + 1))
            with self.assertRaisesRegex(PackagingError, "safety limit"):
                _load_manifest(root)

    def test_accepts_only_canonical_two_component_tags(self) -> None:
        self.assertEqual(validate_stable_tag("v36.1"), "v36.1")
        for value in ("36.1", "v36.1.0", "v36.1-rc1", "V36.1", "v036.1"):
            with self.subTest(value=value), self.assertRaises(PackagingError):
                validate_stable_tag(value)

    def test_slash_aware_globs(self) -> None:
        self.assertTrue(path_matches("core/search.py", "core/**/*.py"))
        self.assertTrue(path_matches("core/memory/search.py", "core/**/*.py"))
        self.assertFalse(path_matches("core/memory/search.md", "core/**/*.py"))
        self.assertFalse(path_matches("dashboard/src/App.tsx", "core/**/*.py"))
        self.assertTrue(path_matches("benchmark_results.json", "benchmark*"))

    def test_manifest_includes_both_opencode_plugin_apis_but_excludes_dashboard(self) -> None:
        manifest = _load_manifest(ROOT)
        include_patterns = [pattern for rule in manifest["include"] for pattern in rule["patterns"]]
        exclude_patterns = [pattern for rule in manifest["exclude"] for pattern in rule["patterns"]]
        self.assertIn("plugin/opencode-biorag-remember-plugin.ts", include_patterns)
        self.assertIn("plugin/opencode-2-biorag-remember-plugin.ts", include_patterns)
        self.assertIn("dashboard-neuro-visor/**", exclude_patterns)
        self.assertNotIn("plugin/**", exclude_patterns)


class StableSafetyTests(unittest.TestCase):
    def test_detects_high_confidence_credentials_without_echoing_values(self) -> None:
        findings = _secret_findings("token = 'ghp_" + "A" * 36 + "'")
        self.assertIn("github-token", findings)
        self.assertEqual(_secret_findings("API_KEY = 'replace-me-with-a-secret'"), [])
        self.assertIn("credential-assignment", _secret_findings("api_key = 'A7b9C2d4E6f8G1h3J5k7L9m2N4p6Q8r1'"))

    def test_english_gate_checks_public_docs_not_internal_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory)
            (tree / "module.py").write_text(
                '# Versión estable\nmessage = "recuerdo"\ndef buscar_recuerdo():\n    return None\n',
                encoding="utf-8",
            )
            (tree / "plugin.ts").write_text('const label = "memoria";\n', encoding="utf-8")
            (tree / "README.md").write_text(
                "# Stable guide\n\nUse the command name `buscar` for retrieval.\n"
                "\n```python\n# versión in source comments is not public prose\n```\n"
                "\nLa versión estable está disponible ahora.\n",
                encoding="utf-8",
            )
            manifest = {
                "language": {
                    "scan_python_comments_and_strings": False,
                    "scan_python_identifiers": False,
                    "spanish_markers": ["versión", "á", "ñ", "buscar", "recuerdo", "memoria"],
                }
            }
            findings = _non_english_findings(tree, manifest)
            self.assertEqual([item["path"] for item in findings], ["README.md"])
            self.assertIn("prose line", findings[0]["message"])
            self.assertIn("'versión'", findings[0]["message"])

    def test_ignored_selected_source_is_blocked_without_git_add(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "core").mkdir()
            (root / "core" / "private.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / ".gitignore").write_text("core/private.py\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            manifest = {
                "include": [{"id": "runtime", "patterns": ["core/**/*.py"], "reason": "runtime"}],
                "exclude": [],
                "strict_directories": ["core"],
                "strict_root_file_patterns": [],
            }
            blockers: list[dict[str, str]] = []
            records = _walk_source(root, manifest, _git_state(root), blockers)
            self.assertEqual([item.decision for item in records if item.path == "core/private.py"], ["blocked"])
            self.assertIn("ignored-runtime-source", {item["code"] for item in blockers})

    def test_privacy_gate_detects_unapproved_email_and_home_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory)
            (tree / "module.py").write_text(
                'CONTACT = "person@example.com"\\nROOT = Path("/home/alice/private")\\n',
                encoding="utf-8",
            )
            manifest = {
                "privacy": {
                    "allowed_emails": ["noreply@github.com"],
                    "scan_absolute_user_paths": True,
                }
            }
            findings = _candidate_privacy_findings(tree, manifest)
            self.assertEqual({item["code"] for item in findings}, {"unapproved-email-address", "absolute-user-path"})
            self.assertTrue(all("person@example.com" not in item["message"] for item in findings))

    def test_staged_deletion_of_runtime_file_blocks_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime_file = root / "core" / "deleted.py"
            runtime_file.parent.mkdir()
            runtime_file.write_text("VALUE = 1\\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "--", "core/deleted.py"], cwd=root, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-q", "-m", "baseline"],
                cwd=root,
                check=True,
            )
            runtime_file.unlink()
            subprocess.run(["git", "add", "-u", "--", "core/deleted.py"], cwd=root, check=True)
            manifest = {
                "include": [{"id": "runtime", "patterns": ["core/**/*.py"], "reason": "runtime"}],
                "exclude": [],
                "strict_directories": ["core"],
                "strict_root_file_patterns": [],
            }
            blockers: list[dict[str, str]] = []
            records = _walk_source(root, manifest, _git_state(root), blockers)
            self.assertEqual([item.decision for item in records if item.path == "core/deleted.py"], ["deleted"])
            self.assertIn("deleted-runtime-source", {item["code"] for item in blockers})

    def test_missing_nested_local_import_blocks_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory)
            (tree / "core").mkdir()
            (tree / "core" / "__init__.py").write_text("", encoding="utf-8")
            (tree / "core" / "caller.py").write_text(
                "import core.not_packaged\nfrom core.not_packaged import also_missing\n", encoding="utf-8"
            )
            blockers, _ = _collect_imports(tree, {"project": {"dependencies": []}}, {})
            missing = [item for item in blockers if item["code"] == "missing-local-import"]
            self.assertEqual(len(missing), 2)

    def test_hebbian_schema_transform_matches_the_empty_stable_resource(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory)
            target = tree / "core" / "sdm.py"
            target.parent.mkdir(parents=True)
            shutil.copy2(ROOT / "core" / "sdm.py", target)
            notes = _transform_hebbian_schema(tree)
            transformed = target.read_text(encoding="utf-8")
            self.assertEqual(len(notes), 1)
            self.assertIn("'dimension_names'", transformed)
            self.assertIn("'threshold'", transformed)
            self.assertIn("'total_nodes'", transformed)
            self.assertNotIn("'dim_names'", transformed)
            self.assertNotIn("'total_nodos'", transformed)

    def test_metadata_transform_adds_wheel_resources_and_english_description(self) -> None:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        transformed, requirements = _transform_project_metadata(text, "v36.1")
        self.assertIn('description = "Persistent cognitive memory for AI agents"', transformed)
        self.assertIn('name = "Dennys José Márquez Reyes"', transformed)
        self.assertNotIn("dennysjmarquez@gmail.com", transformed)
        self.assertIn('"graph_maintenance_daemon"', transformed)
        self.assertIn('"db*"', transformed)
        self.assertIn('db = ["hebbian_clusters.json"]', transformed)
        self.assertTrue(requirements)

    def test_stable_identity_transform_runs_on_a_temporary_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory)
            for relative in (
                "biorag.py",
                "install.py",
                "core/mcp_server/update_checker.py",
            ):
                target = tree / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)
            notes = _apply_stable_identity(tree)
            self.assertEqual(len(notes), 3)
            biorag = (tree / "biorag.py").read_text(encoding="utf-8")
            installer = (tree / "install.py").read_text(encoding="utf-8")
            checker = (tree / "core/mcp_server/update_checker.py").read_text(encoding="utf-8")
            source_biorag = (ROOT / "biorag.py").read_text(encoding="utf-8")
            candidate_module = ast.parse(biorag)
            source_module = ast.parse(source_biorag)
            candidate_handlers = [
                node for node in candidate_module.body
                if isinstance(node, ast.FunctionDef) and node.name == "cmd_dashboard"
            ]
            source_handlers = [
                node for node in source_module.body
                if isinstance(node, ast.FunctionDef) and node.name == "cmd_dashboard"
            ]
            self.assertEqual(len(candidate_handlers), 1)
            self.assertEqual(len(source_handlers), 1)
            self.assertIn('def cmd_dashboard(cerebro, args):', biorag)
            dashboard_registration = any(
                isinstance(key, ast.Constant)
                and key.value == "dashboard"
                and isinstance(value, ast.Name)
                and value.id == "cmd_dashboard"
                for node in ast.walk(candidate_module)
                if isinstance(node, ast.Dict)
                for key, value in zip(node.keys, node.values)
            )
            self.assertFalse(dashboard_registration)
            self.assertNotIn("python3 biorag.py dashboard", biorag)
            source_lines = source_biorag.splitlines(keepends=True)
            candidate_lines = biorag.splitlines(keepends=True)
            source_handler = "".join(source_lines[source_handlers[0].lineno - 1:source_handlers[0].end_lineno])
            candidate_handler = "".join(candidate_lines[candidate_handlers[0].lineno - 1:candidate_handlers[0].end_lineno])
            self.assertEqual(candidate_handler, source_handler)
            self.assertIn('REPO_NAME = "MemoryBioRAG-Stable"', installer)
            self.assertIn("_install_opencode_plugin()", installer)
            self.assertIn("_remove_opencode_plugin()", installer)
            self.assertIn("OPENCODE_PLUGIN_NAME", installer)
            self.assertIn("opencode-2-biorag-remember-plugin", installer)
            self.assertIn("opencode-biorag-remember-plugin", installer)
            self.assertIn('REPO_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}.git"', installer)
            self.assertIn('ZIP_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/archive/main.zip"', installer)
            self.assertIn("_STABLE_TAG_PATTERN", checker)
            self.assertIn("MemoryBioRAG-Stable/tree/", checker)
            self.assertNotIn("api.github.com/repos/dennysjmarquez/MemoryBioRAG/tags", checker)
            namespace: dict[str, object] = {"__name__": "stable_checker_test", "__file__": str(tree / "core/mcp_server/update_checker.py")}
            exec(compile(checker, namespace["__file__"], "exec"), namespace)
            is_stable_tag = namespace["_is_stable_tag"]
            self.assertTrue(is_stable_tag("v36.1"))  # type: ignore[operator]
            self.assertFalse(is_stable_tag("v36.1.0"))  # type: ignore[operator]
            self.assertFalse(is_stable_tag("v36.1-rc1"))  # type: ignore[operator]
            self.assertFalse(is_stable_tag("v036.1"))  # type: ignore[operator]
            self.assertFalse(is_stable_tag("v36.01"))  # type: ignore[operator]


class StableInstallerSafetyTests(unittest.TestCase):
    def test_skill_install_and_uninstall_preserve_other_and_modified_skills(self) -> None:
        import install as installer

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            checkout = root / "checkout"
            source = checkout / "skills" / "biorag-memory" / "SKILL.md"
            source.parent.mkdir(parents=True)
            source.write_text("BioRAG memory skill.\\n", encoding="utf-8")

            claude = home / ".claude"
            opencode = home / ".config" / "opencode"
            claude.mkdir(parents=True)
            opencode.mkdir(parents=True)
            existing = claude / "skills" / "biorag-memory" / "SKILL.md"
            existing.parent.mkdir(parents=True)
            existing.write_text("User-customized skill.\\n", encoding="utf-8")
            unrelated = claude / "skills" / "other-skill" / "SKILL.md"
            unrelated.parent.mkdir(parents=True)
            unrelated.write_text("Unrelated user skill.\\n", encoding="utf-8")
            extra = opencode / "skills" / "biorag-memory" / "notes.txt"
            extra.parent.mkdir(parents=True)
            extra.write_text("Keep user files alongside the skill.\\n", encoding="utf-8")

            with patch.object(installer, "INSTALL_DIR", checkout), patch(
                "pathlib.Path.home", return_value=home
            ):
                installer._install_skill()
                installed = opencode / "skills" / "biorag-memory" / "SKILL.md"
                self.assertEqual(installed.read_text(encoding="utf-8"), source.read_text(encoding="utf-8"))
                self.assertEqual(existing.read_text(encoding="utf-8"), "User-customized skill.\\n")
                self.assertEqual(unrelated.read_text(encoding="utf-8"), "Unrelated user skill.\\n")

                installer._remove_skill()
                self.assertFalse(installed.exists())
                self.assertTrue(extra.is_file())
                self.assertEqual(existing.read_text(encoding="utf-8"), "User-customized skill.\\n")
                self.assertEqual(unrelated.read_text(encoding="utf-8"), "Unrelated user skill.\\n")

                missing_plugin = checkout / "plugin" / "opencode-biorag-remember-plugin.ts"
                with patch.object(installer, "_pick_opencode_plugin_source", return_value=(missing_plugin, "1")):
                    self.assertFalse(installer._install_opencode_plugin())

    def test_opencode_plugin_installation_selects_api_and_preserves_local_edits(self) -> None:
        import install as installer

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            checkout = root / "checkout"
            plugin_dir = checkout / "plugin"
            plugin_dir.mkdir(parents=True)
            v1 = plugin_dir / "opencode-biorag-remember-plugin.ts"
            v2 = plugin_dir / "opencode-2-biorag-remember-plugin.ts"
            v1.write_text("legacy OpenCode plugin\n", encoding="utf-8")
            v2.write_text("V2 OpenCode plugin\n", encoding="utf-8")
            destination = home / ".config" / "opencode" / "plugins" / "opencode-biorag-remember-plugin.ts"

            with patch.object(installer, "INSTALL_DIR", checkout), patch(
                "pathlib.Path.home", return_value=home
            ):
                for api, expected_source in (("2", v2), ("1", v1)):
                    with patch.object(installer, "_detect_opencode_plugin_api", return_value=api):
                        source, detected_api = installer._pick_opencode_plugin_source()
                        self.assertEqual(source, expected_source)
                        self.assertEqual(detected_api, api)
                        self.assertTrue(installer._install_opencode_plugin())
                        self.assertEqual(destination.read_bytes(), expected_source.read_bytes())
                        self.assertTrue(installer._install_opencode_plugin())
                        destination.write_text("User-customized OpenCode plugin\\n", encoding="utf-8")
                        self.assertFalse(installer._install_opencode_plugin())
                        self.assertFalse(installer._remove_opencode_plugin())
                        self.assertEqual(destination.read_text(encoding="utf-8"), "User-customized OpenCode plugin\\n")
                        destination.write_bytes(expected_source.read_bytes())
                        self.assertTrue(installer._remove_opencode_plugin())
                        self.assertFalse(destination.exists())


class StableRuntimeFallbackTests(unittest.TestCase):
    def test_missing_qa_corpus_returns_uncalibrated_fallback_without_persistence(self) -> None:
        from core.memory import umbral

        with tempfile.TemporaryDirectory() as directory:
            fake_module = Path(directory) / "source" / "core" / "memory" / "umbral.py"
            fake_module.parent.mkdir(parents=True)
            with (
                patch.object(umbral, "__file__", str(fake_module)),
                patch.object(umbral, "UmbralConforme", lambda **kwargs: None),
            ):
                store = SimpleNamespace(
                    _umbral_conforme=None,
                    _calibracion_meta=None,
                    _contar_nodos_corpus=lambda: 0,
                    _cargar_calibracion_persistida=lambda: False,
                    _persistir_calibracion=lambda *args, **kwargs: self.fail(
                        "Calibration without a QA corpus must not be persisted."
                    ),
                )
                store.calibrar_umbral_conforme = lambda **kwargs: umbral.calibrar_umbral_conforme(
                    store, **kwargs
                )
                self.assertEqual(umbral._preparar_datos_calibracion(store), ([], []))
                self.assertEqual(umbral.calibrar_umbral_conforme(store), 0.0)
                self.assertTrue(umbral._debe_responder(store, 0.0))
                self.assertEqual(
                    umbral.calibrar_y_persistir(store, n_positivos_max=0),
                    {"umbral": 0.0, "error": "calibracion_fallida"},
                )


class StablePreviewStorageTests(unittest.TestCase):
    @staticmethod
    def _write_preview(
        path: Path,
        stage_relative: str,
        project_name: str,
        files: dict[str, str],
        *,
        version: str = "v36.1",
    ) -> None:
        tree = path / "tree"
        tree.mkdir(parents=True)
        for relative, content in files.items():
            target = tree / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        digest = tree_sha256(tree)
        payload = {
            "schema_version": 1,
            "project_name": project_name,
            "candidate_tree": "tree",
            "stage_directory": stage_relative,
            "status": "ready",
            "version": version,
            "tree_sha256": digest,
            "tree_files": _tree_inventory(tree),
        }
        (path / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
        (path / "report.md").write_text(f"Candidate tree SHA-256: {digest}\n", encoding="utf-8")
        (path / "TREE_SHA256").write_text(digest + "\n", encoding="ascii")

    def test_only_the_current_preview_remains_and_legacy_outputs_leave_staging(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".gitignore").write_text("/.staging/\n/.stable-release/\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            manifest = _load_manifest(ROOT)
            preview_relative = manifest["output"]["staging_directory"]
            preview_dir = root / preview_relative
            self._write_preview(preview_dir, preview_relative, manifest["project_name"], {"old.txt": "previous preview\n"})

            legacy_stage_relative = ".staging/stable/stages/v36.1-20260101T000000Z-deadbeef"
            legacy_stage = root / legacy_stage_relative
            self._write_preview(
                legacy_stage, legacy_stage_relative, manifest["project_name"], {"old-stage.txt": "verified legacy preview\n"},
            )

            legacy_release = root / ".staging" / "stable" / "releases" / "v36.0-20260101T000000Z-deadbeef"
            legacy_tree = legacy_release / "tree"
            legacy_tree.mkdir(parents=True)
            (legacy_tree / "source.txt").write_text("old candidate\n", encoding="utf-8")
            legacy_archive = legacy_release / "legacy.zip"
            with zipfile.ZipFile(legacy_archive, "w") as archive:
                archive.writestr("legacy.txt", "preserve this old local artifact\n")
            legacy_archive_bytes = legacy_archive.read_bytes()
            legacy_release_manifest = {
                "schema_version": 1,
                "project_name": manifest["project_name"],
                "version": "v36.0",
                "status": "prepared-locally",
                "source_tree_sha256": tree_sha256(legacy_tree),
                "artifacts": [{
                    "path": legacy_archive.name,
                    "size_bytes": legacy_archive.stat().st_size,
                    "sha256": _sha256_file(legacy_archive),
                }],
            }
            (legacy_release / "release-manifest.json").write_text(
                json.dumps(legacy_release_manifest), encoding="utf-8",
            )
            (legacy_release / "report.md").write_text("Old local release candidate.\n", encoding="utf-8")

            for marker in ("first-current-preview", "second-current-preview"):
                selected_preview, build_dir = _create_preview_paths(root, manifest)
                self.assertEqual(selected_preview, preview_dir)
                self._write_preview(build_dir, preview_relative, manifest["project_name"], {"marker.txt": marker + "\n"})
                _promote_current_preview(root, manifest, build_dir, selected_preview)

                self.assertFalse(build_dir.exists())
                self.assertEqual([path.name for path in (root / ".staging" / "stable").iterdir()], ["preview"])
                self.assertEqual((preview_dir / "tree" / "marker.txt").read_text(encoding="utf-8"), marker + "\n")
                self.assertFalse((preview_dir / "tree" / "old.txt").exists())

            migrated = root / ".stable-release" / "stable" / "releases" / legacy_release.name / "legacy.zip"
            self.assertEqual(migrated.read_bytes(), legacy_archive_bytes)
            self.assertFalse(legacy_release.exists())
            self.assertFalse((root / ".staging" / "stable" / "stages").exists())
            self.assertFalse((root / ".staging" / "stable" / "releases").exists())

    def test_unrecognized_legacy_stage_data_is_preserved_and_blocks_pruning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".gitignore").write_text("/.staging/\n/.stable-release/\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            manifest = _load_manifest(ROOT)
            preview_relative = manifest["output"]["staging_directory"]
            preview_dir = root / preview_relative
            self._write_preview(preview_dir, preview_relative, manifest["project_name"], {"marker.txt": "keep current\n"})

            legacy_root = root / ".staging" / "stable" / "stages"
            verified_old = legacy_root / "v36.1-20260101T000000Z-deadbeef"
            self._write_preview(
                verified_old, verified_old.relative_to(root).as_posix(), manifest["project_name"], {"old.txt": "old preview\n"},
            )
            unknown = legacy_root / "user-data"
            unknown.mkdir()
            sentinel = unknown / "keep.txt"
            sentinel.write_text("do not delete\n", encoding="utf-8")

            selected_preview, build_dir = _create_preview_paths(root, manifest)
            self._write_preview(build_dir, preview_relative, manifest["project_name"], {"marker.txt": "new candidate\n"})
            with self.assertRaisesRegex(PackagingError, "Unrecognized directory in legacy stage output"):
                _promote_current_preview(root, manifest, build_dir, selected_preview)

            self.assertEqual((preview_dir / "tree" / "marker.txt").read_text(encoding="utf-8"), "keep current\n")
            self.assertTrue((verified_old / "tree" / "old.txt").is_file())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "do not delete\n")
class StableReleaseIntegrationTests(unittest.TestCase):
    def test_release_builds_reviewed_local_artifacts_only(self) -> None:
        project = '''[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "memory-biorag"
version = "36.1.0"
description = "Persistent cognitive memory for AI agents"
readme = "README.md"
requires-python = ">=3.11"
dependencies = []

[tool.setuptools]
py-modules = ["biorag", "mcp_server", "install", "graph_maintenance_daemon"]

[tool.setuptools.packages.find]
where = ["."]
include = ["core*", "db*"]

[tool.setuptools.package-data]
db = ["hebbian_clusters.json"]
'''
        files = {
            "README.md": "A local-first memory package.\n",
            "CHANGELOG.md": "# Changelog\n\n## v36.1\n\nInitial local fixture.\n",
            "skills/biorag-memory/SKILL.md": "# BioRAG Memory Skill\n",
            "plugin/opencode-biorag-remember-plugin.ts": "export default {};\n",
            "plugin/opencode-2-biorag-remember-plugin.ts": "export default {};\n",
            "LICENSE": "Apache License 2.0\n",
            "VERSION": "v36.1\n",
            "pyproject.toml": project,
            ".gitignore": "/.staging/\n/.stable-release/\n__pycache__/\n*.db\n",
            "ENVIRONMENT.example": "# Optional settings.\nBIORAG_UPDATE_CHECK=1\n",
            "requirements.txt": "",
            "update_policy.json": json.dumps(
                {"schema_version": 1, "channel": "stable", "recommended_tag": "v36.1", "blocked_tags": []},
                indent=2,
            ) + "\n",
            "biorag.py": "def main():\n    return None\n",
            "mcp_server.py": "def main():\n    return None\n",
            "install.py": "def main():\n    return None\n",
            "graph_maintenance_daemon.py": "def main():\n    return None\n",
            "core/__init__.py": "",
            "core/memory_store.py": "",
            "core/sdm.py": '''import json
from pathlib import Path

_HEBBIAN_PATH = Path(__file__).parent.parent / "db" / "hebbian_clusters.json"

def _load_hebbian_data():
    return json.loads(_HEBBIAN_PATH.read_text(encoding="utf-8"))

def sdm_info():
    return {"clusters_hebbianos": len(_load_hebbian_data().get("clusters", []))}
''',
            "core/mcp_server/__init__.py": "",
            "core/mcp_server/server.py": "",
            "core/mcp_server/update_checker.py": r'''import re

_POLICY_API = "https://api.github.com/repos/dennysjmarquez/MemoryBioRAG-Stable/contents/update_policy.json"
_TAGS_PAGE = "https://github.com/dennysjmarquez/MemoryBioRAG-Stable/tree/"
_STABLE_TAG_PATTERN = re.compile(r"^v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$")

def _is_stable_tag(value):
    return bool(_STABLE_TAG_PATTERN.fullmatch(value.strip()))
''',
            "db/__init__.py": "",
            "db/hebbian_clusters.json": json.dumps(
                {"clusters": [], "idf": {}, "dimension_names": {}, "threshold": 0.25, "total_nodes": 0},
                indent=2,
            ) + "\n",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "release_manifest.toml").write_text(
                (ROOT / "release_manifest.toml").read_text(encoding="utf-8"), encoding="utf-8",
            )
            for relative, content in files.items():
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)

            stage_relative = ".staging/stable/preview"
            stage_dir = root / stage_relative
            tree = stage_dir / "tree"
            tree.mkdir(parents=True)
            for relative, content in files.items():
                target = tree / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            digest = tree_sha256(tree)
            stage_manifest = {
                "schema_version": 1,
                "project_name": _load_manifest(root)["project_name"],
                "candidate_tree": "tree",
                "stage_directory": stage_relative,
                "status": "ready",
                "version": "v36.1",
                "tree_sha256": digest,
                "tree_files": _tree_inventory(tree),
            }
            (stage_dir / "manifest.json").write_text(json.dumps(stage_manifest), encoding="utf-8")
            (stage_dir / "report.md").write_text(f"Candidate tree SHA-256: {digest}\n", encoding="utf-8")
            (stage_dir / "TREE_SHA256").write_text(digest + "\n", encoding="ascii")

            stray = root / ".staging" / "unreviewed-data"
            stray.write_text("not part of the preview\n", encoding="utf-8")
            with self.assertRaisesRegex(PackagingError, "Unrecognized data remains in .staging"):
                create_release(root, "v36.1", stage_relative, digest)
            stray.unlink()

            with self.assertRaisesRegex(PackagingError, "Only the current Stable preview"):
                create_release(root, "v36.1", ".staging/stable/stages/old-stage", digest)

            with self.assertRaisesRegex(PackagingError, "SHA-256"):
                create_release(root, "v36.1", stage_relative, "0" * 64)

            result = create_release(root, "v36.1", stage_relative, digest)
            release_dir = root / result["release_directory"]
            self.assertEqual(result["publication_actions"], [])
            self.assertTrue((release_dir / "report.md").is_file())
            self.assertTrue((release_dir / "release-manifest.json").is_file())
            self.assertTrue((release_dir / "tree" / "db" / "hebbian_clusters.json").is_file())
            self.assertEqual(result["wheel_validation"]["local_resource_smoke_test"], "passed")
            self.assertEqual(result["source_tree_sha256"], digest)
            self.assertEqual(tree_sha256(tree), digest)
            self.assertTrue(all((release_dir / artifact["path"]).is_file() for artifact in result["artifacts"]))

            expected_tree = {
                path.relative_to(tree).as_posix(): path.read_bytes()
                for path in tree.rglob("*")
                if path.is_file()
            }
            released_tree = release_dir / "tree"
            actual_tree = {
                path.relative_to(released_tree).as_posix(): path.read_bytes()
                for path in released_tree.rglob("*")
                if path.is_file()
            }
            self.assertEqual(actual_tree, expected_tree)

            archive_path = next(
                release_dir / artifact["path"]
                for artifact in result["artifacts"]
                if artifact["path"].endswith(".zip")
            )
            archive_prefix = "MemoryBioRAG-Stable-v36.1/"
            with zipfile.ZipFile(archive_path) as archive:
                archived_tree = {
                    name.removeprefix(archive_prefix): archive.read(name)
                    for name in archive.namelist()
                    if name.startswith(archive_prefix)
                }
            self.assertEqual(archived_tree, expected_tree)


if __name__ == "__main__":
    unittest.main()
