#!/usr/bin/env python3
"""Build a blind, deterministic E1 semantic-review package (no engine calls)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/casos_qa_intuicion_asociaciones_e1.jsonl"
PUBLIC_PACKAGE = ROOT / "docs/paquete_ciego_revision_semantica_e1_v1.jsonl"
PUBLIC_MANIFEST = ROOT / "docs/manifiesto_paquete_ciego_revision_semantica_e1_v1.json"
REVIEW_INSTRUCTIONS = ROOT / "docs/INSTRUCCIONES_REVISOR_CIEGO_E1_V1.md"
PRIVATE_CROSSWALK = ROOT / ".private_evidence/e1_blind_review_v1/crosswalk_private_r7.jsonl"
SEED = 20261101
ADDITIONAL_PER_CASE = 2

# Source fixture uses numbered leading titles. Remove the entire title, regardless
# of its role-bearing wording; retain the sentence body verbatim.
HEADING_RE = re.compile(r"^.{1,90}?\b[0-9]{1,3}\s*:\s*")
# Role-revealing body fragments in this fixture, removed by exact logged rules.
ROLE_SUFFIX_RE = re.compile(r"\s*This is the primary decision\.\s*$")
PRIMARY_ROLE_PHRASE_RE = re.compile(r"\bacción primaria es\b", re.IGNORECASE)
SOURCE_ID_RE = re.compile(r"\bqa_pos_[A-Za-z0-9_]+\b")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sanitize_memory_text(original: str) -> tuple[str, list[str]]:
    text = original
    transformations: list[str] = []
    match = HEADING_RE.match(text)
    if match:
        text = text[match.end():]
        transformations.append("strip_numbered_leading_title")
    new_text, n = ROLE_SUFFIX_RE.subn("", text)
    if n:
        text = new_text.rstrip()
        transformations.append("strip_exact_primary_decision_suffix")
    text, n = PRIMARY_ROLE_PHRASE_RE.subn("acción es", text)
    if n:
        transformations.append("replace_exact_primary_action_marker")
    return text, transformations


def source_gold_roles(ep: dict[str, Any], query: dict[str, Any], concept: str) -> list[str]:
    roles = []
    if concept in query.get("objetivos_principales", []):
        roles.append("objetivo_principal")
    if concept in query.get("relacionados_utiles", []):
        roles.append("relacionado_util")
    if concept in query.get("ruido_tonto", []):
        roles.append("ruido_tonto")
    if concept in ep.get("pistas_serendipia_utiles", []):
        roles.append("pista_serendipia_util")
    if concept in ep.get("recuerdos_apoyo", []):
        roles.append("recuerdo_apoyo")
    if concept in ep.get("apoyos_no_pista", []):
        roles.append("apoyo_no_pista")
    return roles


def write_private_exclusive(path: Path, records: list[dict[str, Any]]) -> bytes:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    payload = b"".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode("utf-8") + b"\n"
        for row in records
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        view = memoryview(payload)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    dir_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--private-crosswalk", type=Path, default=PRIVATE_CROSSWALK,
        help="private output path (must remain under .private_evidence; use a new path for each regeneration)",
    )
    args = parser.parse_args()
    private_crosswalk = args.private_crosswalk
    if not private_crosswalk.is_absolute():
        private_crosswalk = ROOT / private_crosswalk
    private_root = (ROOT / ".private_evidence").resolve()
    try:
        private_crosswalk.resolve().relative_to(private_root)
    except ValueError as exc:
        raise SystemExit("private crosswalk must remain under .private_evidence") from exc

    source_bytes = SOURCE.read_bytes()
    episodes = [json.loads(line) for line in source_bytes.splitlines() if line.strip()]
    episode_by_id = {ep["episode_id"]: ep for ep in episodes}

    # Find exactly the query-level assignments whose per-query evidence excerpt
    # is absent. This reads the fixture; it never writes to it.
    assignments: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    query_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for ep in episodes:
        for q in ep.get("consultas", []):
            key = (ep["episode_id"], q["query_id"])
            query_by_key[key] = q
            for role, field, evidence_field in (
                ("objetivo", "objetivos_principales", "evidencia_objetivos"),
                ("pista", "relacionados_utiles", "evidencia_relacionados_utiles"),
            ):
                for concept in q.get(field, []):
                    if not q.get(evidence_field, {}).get(concept):
                        assignments[key].append({"concept": concept, "role": role})

    rng = random.Random(SEED)
    cases = []
    crosswalk: list[dict[str, Any]] = []
    presentation_counts = {"under_review": 0, "additional": 0}
    used_case_ids: set[str] = set()
    used_candidate_ids: set[str] = set()

    for (episode_id, query_id) in sorted(assignments):
        ep = episode_by_id[episode_id]
        q = query_by_key[(episode_id, query_id)]
        flagged = assignments[(episode_id, query_id)]
        flagged_concepts = {row["concept"] for row in flagged}
        node_by_id = {node["id"]: node for node in ep.get("nodos", [])}
        if not flagged_concepts <= set(node_by_id):
            raise ValueError(f"Missing source node for a flagged assignment: {query_id}")

        extra_concepts = sorted(set(node_by_id) - flagged_concepts)
        if len(extra_concepts) < ADDITIONAL_PER_CASE:
            raise ValueError(f"Insufficient same-episode additions for {query_id}")
        selected_extra = rng.sample(extra_concepts, ADDITIONAL_PER_CASE)
        candidate_sources = [
            (item["concept"], "under_review", item["role"]) for item in flagged
        ] + [(concept, "additional", None) for concept in selected_extra]
        rng.shuffle(candidate_sources)

        case_id = f"case-{rng.getrandbits(64):016x}"
        while case_id in used_case_ids:
            case_id = f"case-{rng.getrandbits(64):016x}"
        used_case_ids.add(case_id)
        public_candidates = []
        for concept, kind, flagged_role in candidate_sources:
            candidate_id = f"item-{rng.getrandbits(64):016x}"
            while candidate_id in used_candidate_ids:
                candidate_id = f"item-{rng.getrandbits(64):016x}"
            used_candidate_ids.add(candidate_id)
            original_text = node_by_id[concept].get("contenido", "")
            presented_text, transformations = sanitize_memory_text(original_text)
            if not presented_text.strip():
                raise ValueError(f"Empty normalized candidate in {query_id}")
            public_candidates.append({"item_code": candidate_id, "text": presented_text})
            presentation_counts[kind] += 1
            crosswalk.append({
                "case_code": case_id,
                "item_code": candidate_id,
                "source_episode_id": episode_id,
                "source_query_id": query_id,
                "source_concept_id": concept,
                "source_assignment_role": flagged_role,
                "source_gold_roles_for_query_and_episode": source_gold_roles(ep, q, concept),
                "crosswalk_kind": kind,
                "original_query_text": q["query"],
                "original_memory_text": original_text,
                "presented_memory_text": presented_text,
                "transformations_applied": transformations,
            })
        cases.append({
            "case_code": case_id,
            "question": q["query"],
            "items": public_candidates,
        })

    rng.shuffle(cases)
    package_bytes = b"".join(
        json.dumps(case, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode("utf-8") + b"\n"
        for case in cases
    )
    package_text = package_bytes.decode("utf-8")
    expected_flagged = sum(len(v) for v in assignments.values())
    objective_count = sum(row["role"] == "objetivo" for rows in assignments.values() for row in rows)
    clue_count = sum(row["role"] == "pista" for rows in assignments.values() for row in rows)
    unique_assignment_keys = {
        (episode_id, query_id, row["role"], row["concept"])
        for (episode_id, query_id), rows in assignments.items() for row in rows
    }
    expected_additional = len(assignments) * ADDITIONAL_PER_CASE
    if (expected_flagged != 90 or objective_count != 33 or clue_count != 57
            or len(unique_assignment_keys) != expected_flagged
            or len(assignments) != 33 or expected_additional != 66):
        raise ValueError("Unexpected assignment/case counts; stop and review before output")
    if presentation_counts != {"under_review": 90, "additional": 66}:
        raise ValueError("Unexpected blind package candidate count")
    if SOURCE_ID_RE.search(package_text):
        raise ValueError("A source identifier leaked into the blind package")
    if any(HEADING_RE.match(item["text"]) for case in cases for item in case["items"]):
        raise ValueError("A numbered label-bearing title remains in the package")
    if ROLE_SUFFIX_RE.search(package_text) or PRIMARY_ROLE_PHRASE_RE.search(package_text):
        raise ValueError("A label-bearing decision phrase remains in the package")
    for case in cases:
        if set(case) != {"case_code", "question", "items"}:
            raise ValueError("Unexpected case field could expose gold metadata")
        for item in case["items"]:
            if set(item) != {"item_code", "text"}:
                raise ValueError("Unexpected candidate field could expose gold metadata")

    crosswalk_bytes = write_private_exclusive(private_crosswalk, crosswalk)
    PUBLIC_PACKAGE.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_PACKAGE.write_bytes(package_bytes)
    os.chmod(PUBLIC_PACKAGE, 0o644)

    transform_spec = {
        "question_text": "copied verbatim from query; no query_id/type/answer/abstention field is emitted",
        "memory_text": [
            {"regex": HEADING_RE.pattern, "operation": "remove matched leading numbered title, preserve following body verbatim"},
            {"regex": ROLE_SUFFIX_RE.pattern, "operation": "remove exact trailing sentence if present"},
            {"regex": PRIMARY_ROLE_PHRASE_RE.pattern, "operation": "replace exact phrase with 'la acción es' to remove the embedded role marker, preserving the action text"},
        ],
        "identifiers": "source episode/query/concept IDs and role names replaced by seeded opaque case/item codes; not serialized in agent package",
        "foils": f"exactly {ADDITIONAL_PER_CASE} items per case sampled uniformly without replacement from other nodes in the same episode, excluding that case's flagged concepts; no role-based filtering",
        "ordering": "sort source cases and available foils before seeded PRNG; sample foils, shuffle items within cases, shuffle cases, then assign opaque codes from the same PRNG stream",
        "text_policy": "no translation, paraphrase, lowercasing, or content rewriting beyond the listed transformations",
    }
    transformation_counts = Counter(
        transformation
        for row in crosswalk
        for transformation in row["transformations_applied"]
    )
    transformed_presentations = sum(bool(row["transformations_applied"]) for row in crosswalk)
    unchanged_presentations = len(crosswalk) - transformed_presentations
    transformation_summary = {
        "transformed_presentations": transformed_presentations,
        "unchanged_presentations": unchanged_presentations,
        "total_rule_applications": sum(transformation_counts.values()),
    }
    if transformation_summary != {
        "transformed_presentations": 152,
        "unchanged_presentations": 4,
        "total_rule_applications": 156,
    }:
        raise ValueError(f"Unexpected transformation summary: {transformation_summary}")
    manifest = {
        "title": "Blind E1 semantic review package, v1",
        "status": "prepared_not_reviewed",
        "seed": SEED,
        "source": "scripts/casos_qa_intuicion_asociaciones_e1.jsonl",
        "source_sha256": sha256(source_bytes),
        "case_count": len(cases),
        "under_review_assignments": presentation_counts["under_review"],
        "under_review_objective_assignments": objective_count,
        "under_review_clue_assignments": clue_count,
        "additional_candidate_presentations": presentation_counts["additional"],
        "additional_per_case": ADDITIONAL_PER_CASE,
        "total_candidate_presentations": sum(presentation_counts.values()),
        "unique_queries": len(assignments),
        "crosswalk_file_count_in_agent_package": 0,
        "agent_package": str(PUBLIC_PACKAGE.relative_to(ROOT)),
        "agent_package_sha256": sha256(package_bytes),
        "reviewer_instructions": str(REVIEW_INSTRUCTIONS.relative_to(ROOT)),
        "reviewer_instructions_sha256": sha256(REVIEW_INSTRUCTIONS.read_bytes()),
        "agent_package_file_mode": "0644",
        "agent_visible_inputs": [str(PUBLIC_PACKAGE.relative_to(ROOT)), str(REVIEW_INSTRUCTIONS.relative_to(ROOT))],
        "agent_visible_fields": ["case_code", "question", "items[].item_code", "items[].text"],
        "agent_must_not_receive": ["this manifest", str(private_crosswalk.relative_to(ROOT)), "gold JSONL", "source labels", "query evidence/justifications", "repository checkout/history", "other agent response"],
        "private_crosswalk_path": str(private_crosswalk.relative_to(ROOT)),
        "private_crosswalk_sha256": sha256(crosswalk_bytes),
        "private_crosswalk_directory_mode": "0700",
        "private_crosswalk_file_mode": "0600",
        "crosswalk_security": {
            "reconstructible_from_public_repo": True,
            "reconstruction_inputs": ["source gold JSONL", "this generator", f"seed={SEED}"],
            "private_copy_is_not_a_blinding_security_boundary": True,
            "private_copy_purpose": "reduce accidental exposure; agents must lack repository/history access",
        },
        "delivery_plan": {
            "verified_now": False,
            "two_fresh_external_sessions_required": True,
            "only_files_to_each_session": [str(PUBLIC_PACKAGE.relative_to(ROOT)), str(REVIEW_INSTRUCTIONS.relative_to(ROOT))],
            "deny_repository_history_memory_connectors_and_other_response": True,
            "if_isolation_unverified": "exploratory_non_independent",
        },
        "adjudication_original_text_review": {
            "all_presentations_transformed": False,
            "presentation_count_to_compare": sum(presentation_counts.values()),
            "requirement": "human adjudicator compares question, presented text, and original text for all presentations, including unchanged ones; records semantic impact before revealing gold role",
            "source_of_originals": str(private_crosswalk.relative_to(ROOT)),
        },
        "transformations": transform_spec,
        "transformation_application_counts": dict(sorted(transformation_counts.items())),
        "transformation_summary": transformation_summary,
        "leak_checks": {
            "source_concept_id_pattern_found": False,
            "numbered_title_prefix_remaining": False,
            "primary_decision_suffix_remaining": False,
            "primary_action_role_phrase_remaining": False,
            "gold_metadata_keys_in_package": False,
            "all_case_codes_unique": len(used_case_ids) == len(cases),
            "all_candidate_codes_unique": len(used_candidate_ids) == sum(presentation_counts.values()),
            "passed": True,
        },
        "agent_sessions": {
            "identified_sessions": ["current Arena Agent Mode conversation only; no separate agent-session ID or second isolated session is exposed to this turn"],
            "current_session_eligible_as_blind_reviewer": False,
            "second_session_available_and_identified": False,
            "separation_verified": False,
            "review_passes_started": 0,
            "classification_if_attempted_without_verification": "exploratory_non_independent",
            "verification_required": [
                "two distinct session IDs recorded before assignment",
                "fresh isolated contexts with shared history/memory disabled or demonstrably inaccessible",
                "identical package hash and rubric hash supplied to both",
                "no cross-access to gold, crosswalk, manifest, or other response",
                "each response frozen and hashed before unblinding/comparison",
            ],
        },
        "review_procedure": [
            "The custodian creates two fresh sessions outside the repository and gives each only the agent_package and reviewer_instructions; no manifest, source, repo/history, connectors, crosswalk, or other output.",
            "Review each item independently for direct answer, useful indirect clue, neutral, irrelevant/harmful, or insufficient evidence; record a query-specific textual warrant, doubt, and confidence.",
            "Keep original outputs separately; compare only after both are frozen. Do not merge votes or call agent judgments human annotations.",
            "After freezing both responses, a named bilingual human adjudicator selected by Dennys compares question, presented text, and original text for all 156 presentations (152 transformed, 4 unchanged; 156 rule applications, with overlap); records semantic impact before unblinding source gold roles.",
            "Preserve both initial judgments and adjudication rationale; this process does not automatically substitute agent passes for human reviewers.",
            "If isolation cannot be verified, label both passes exploratory/non-independent and defer gold changes/closure pending two genuinely independent human reviews or a verifiable isolated protocol.",
        ],
        "gold_modified": False,
        "campaign_executed": False,
        "engine_or_database_changed": False,
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                                indent=2).encode("utf-8") + b"\n"
    PUBLIC_MANIFEST.write_bytes(manifest_bytes)
    os.chmod(PUBLIC_MANIFEST, 0o644)
    print(json.dumps({
        "cases": len(cases),
        "under_review": presentation_counts["under_review"],
        "additional_presentations": presentation_counts["additional"],
        "total_presentations": sum(presentation_counts.values()),
        "package_sha256": sha256(package_bytes),
        "crosswalk_sha256": sha256(crosswalk_bytes),
        "manifest": str(PUBLIC_MANIFEST.relative_to(ROOT)),
        "private_crosswalk": str(private_crosswalk.relative_to(ROOT)),
        "blind_checks_passed": True,
        "review_passes_started": 0,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
