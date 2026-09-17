"""D5 consumer gate for artifacts/setup/TOKEN_ANCHORS.json (plan §6.1; audit F-06; §12 D5).

`export_phase0_artifacts.py` pins `P_decision == P_boundary` for EVERY task (its position
invariant asserts the equality), because both are the last token of the assistant prefix.
What that index MEANS is task-dependent:

* V / C — the gold decision is a single-token-start letter label, so the hidden state at
  `P_decision` IS the decision locus.
* T — the decision is a native tool call distributed over several generated tokens, so
  `P_decision == P_boundary` is only the **first-generated-token** locus. Reading it as
  "the" single-token decision locus asserts a locus that plan §6.1 says does not exist.

The 2026-09-17 §12 re-verification recorded this as defect **D5** and DEFERRED it: the
artifact already carries the disclosure (`decision_tokenarity` per anchor plus
`position_definitions.P_decision`), and a machine-readable single-locus flag would have
forced a third B8-01 re-export of hash-pinned artifacts
(`TOKEN_ANCHORS.json` sha256 `ecdac639ab8a42aa…`, `ENVIRONMENT.json` sha256 `5b8b5bf6cf96d68b…`)
that the re-verification record and the batch-10 P1–P8 precondition both bind to.

This module is the non-churning enforcement of the same requirement, placed where the
consumer is instead of in the frozen artifact: a T05 probing / activation-extraction
implementation cannot ask for "the single-token decision locus" of a T anchor without
going through an API that raises. `tests/test_phase0_anchors.py` pins the disclosure
against the COMMITTED artifact, so a future re-export that silently drops it fails the
suite rather than the reader's attention.

Exposure scope: this constrains how the anchor package may be *consumed*. It is not a
provenance credential and it does not make any claim about where T decisions are
represented in the model — that is what T05 is supposed to find out.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ANCHORS = ROOT / "artifacts/setup/TOKEN_ANCHORS.json"

SCHEMA = "phase0_token_anchors_v1"
SINGLE_TOKEN_LOCUS = "single_token_start_label"
MULTI_TOKEN_LOCUS = "multi_token_native_tool_call"
TOKENARITY_BY_TASK = {"V": SINGLE_TOKEN_LOCUS, "C": SINGLE_TOKEN_LOCUS, "T": MULTI_TOKEN_LOCUS}
#: The D5/F-06 caveat must survive any future re-export verbatim enough to be greppable.
REQUIRED_P_DECISION_CAVEAT = "NOT a single-token decision locus"
#: What a caller must do before using a multi-token locus as a probing site.
READ_BEFORE_USE = (
    "plan §6.1 + audit F-06 + §12 D5: for a multi-token decision this index is the "
    "first-GENERATED-token locus only; per-position interpretation of the action is a "
    "design decision that must be declared before the run, not inferred from P_decision"
)


class AmbiguousDecisionLocusError(ValueError):
    """Raised when a caller requests a single-token decision locus for a decision that
    is not single-token (audit F-06 / §12 D5), or for an anchor whose disclosure is
    missing or malformed enough that the request cannot be answered safely."""


def validate_anchor_disclosure(anchor: dict[str, Any]) -> list[str]:
    """Return a list of disclosure violations for one anchor (empty == admissible).

    Fail-closed by construction: an unknown `decision_tokenarity`, a missing
    `position_definitions.P_decision`, or a stripped caveat is a violation, not a default.
    """
    problems: list[str] = []
    example_id = anchor.get("example_id", "<no example_id>")
    tokenarity = anchor.get("decision_tokenarity")
    task = anchor.get("task")
    if tokenarity not in (SINGLE_TOKEN_LOCUS, MULTI_TOKEN_LOCUS):
        problems.append(f"{example_id}: decision_tokenarity is {tokenarity!r}, not a known tokenarity class")
        return problems
    expected = TOKENARITY_BY_TASK.get(task)
    if expected is not None and tokenarity != expected:
        problems.append(f"{example_id}: task {task} declares {tokenarity!r}, expected {expected!r}")
    if anchor.get("P_decision") != anchor.get("P_boundary"):
        problems.append(
            f"{example_id}: P_decision ({anchor.get('P_decision')}) != P_boundary ({anchor.get('P_boundary')}); "
            "the exported equality invariant no longer holds, so locus semantics cannot be assumed"
        )
    definition = (anchor.get("position_definitions") or {}).get("P_decision")
    if not isinstance(definition, str) or not definition.strip():
        problems.append(f"{example_id}: position_definitions.P_decision is missing; locus semantics undeclared")
    elif REQUIRED_P_DECISION_CAVEAT not in definition:
        problems.append(
            f"{example_id}: position_definitions.P_decision no longer states '{REQUIRED_P_DECISION_CAVEAT}' "
            "(audit F-06 / §12 D5 disclosure was dropped by a re-export)"
        )
    return problems


def load_anchor_package(path: Path | None = None) -> dict[str, Any]:
    """Load TOKEN_ANCHORS.json and refuse (fail-closed) if any anchor's disclosure is broken."""
    path = Path(path) if path is not None else DEFAULT_ANCHORS
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise AmbiguousDecisionLocusError(f"{path}: schema is {doc.get('schema')!r}, expected {SCHEMA!r}")
    anchors = doc.get("anchors")
    if not isinstance(anchors, list) or not anchors:
        raise AmbiguousDecisionLocusError(f"{path}: no anchors present; refusing to return an empty locus set")
    violations = [p for a in anchors for p in validate_anchor_disclosure(a)]
    if violations:
        raise AmbiguousDecisionLocusError(
            f"{path}: {len(violations)} anchor disclosure violation(s):\n  " + "\n  ".join(violations)
        )
    return doc


def package_summary(doc: dict[str, Any]) -> dict[str, Any]:
    """Describe what the package does and does not license. Pure; no file or GPU access."""
    per_task: dict[str, int] = {}
    for a in doc["anchors"]:
        per_task[a["task"]] = per_task.get(a["task"], 0) + 1
    single = [a["example_id"] for a in doc["anchors"] if a["decision_tokenarity"] == SINGLE_TOKEN_LOCUS]
    multi = [a["example_id"] for a in doc["anchors"] if a["decision_tokenarity"] == MULTI_TOKEN_LOCUS]
    return {
        "schema": doc.get("schema"),
        "ticket": doc.get("ticket"),
        "status": doc.get("status"),
        "anchor_count": len(doc["anchors"]),
        "anchors_per_task": per_task,
        "s_anchor_count": per_task.get("S", 0),
        "s_coverage_status": ((doc.get("coverage") or {}).get("S") or {}).get("status"),
        "single_token_locus_anchors": len(single),
        "multi_token_locus_anchors": len(multi),
        "c_coverage_status": ((doc.get("coverage") or {}).get("C") or {}).get("status"),
        "lock_binding": doc.get("lock_binding"),
        "read_before_use": READ_BEFORE_USE,
    }


def single_token_decision_locus(anchor: dict[str, Any]) -> dict[str, Any]:
    """The decision locus for a single-token-start label decision (V/C).

    Raises `AmbiguousDecisionLocusError` for a multi-token decision (T) rather than
    silently handing back an index that a caller could mistake for a single-token locus.
    """
    problems = validate_anchor_disclosure(anchor)
    if problems:
        raise AmbiguousDecisionLocusError("; ".join(problems))
    if anchor["decision_tokenarity"] != SINGLE_TOKEN_LOCUS:
        raise AmbiguousDecisionLocusError(
            f"{anchor.get('example_id')}: decision_tokenarity="
            f"{anchor['decision_tokenarity']!r} — P_decision==P_boundary here is the "
            f"first-generated-token locus, NOT a single-token decision locus "
            f"(plan §6.1; audit F-06; §12 D5). Use first_generated_token_locus() and "
            f"declare the per-position interpretation of the action as a design choice."
        )
    return {
        "P_decision": anchor["P_decision"],
        "decision_tokenarity": anchor["decision_tokenarity"],
        "is_single_token_decision_locus": True,
        "task": anchor.get("task"),
        "example_id": anchor.get("example_id"),
    }


def first_generated_token_locus(anchor: dict[str, Any]) -> dict[str, Any]:
    """The last-prefix-token locus that predicts the first generated token, for any task.

    `is_single_token_decision_locus` is False by construction: this is a *positional*
    anchor, and whether the decision lives there is exactly the question an experiment has
    to answer, not something the anchor package can assert.
    """
    problems = validate_anchor_disclosure(anchor)
    if problems:
        raise AmbiguousDecisionLocusError("; ".join(problems))
    return {
        "P_boundary": anchor["P_boundary"],
        "decision_tokenarity": anchor["decision_tokenarity"],
        "is_single_token_decision_locus": False,
        "task": anchor.get("task"),
        "example_id": anchor.get("example_id"),
        "read_before_use": READ_BEFORE_USE,
    }
