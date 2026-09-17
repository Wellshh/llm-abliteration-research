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

Exposure scope, stated so nobody over-reads it (§12 round-2 audit):

* This constrains how the anchor package may be *loaded and consumed through this API*. It is not a
  provenance credential and asserts nothing about where any decision is represented in the model —
  that is what T05 exists to find out.
* **Nothing imports this module yet.** `scripts/run_pilot.py` builds and consumes its own anchors via
  `build_token_anchor` (the T04-lineage code a T05 implementer would most likely extend). Until the
  T05 ticket makes consuming this accessor mandatory (a review rule, or a CI grep banning raw
  `json.load` of `TOKEN_ANCHORS.json`), "the API" is guidance plus tests, not an enforced path.
* A consumer can still `json.load` the file and read `anchor["P_decision"]` directly; no test can
  prevent that. What the API removes is the *default* way of getting it wrong.
* Checks are consistency-of-disclosure checks, not truth-of-content checks — see
  `validate_anchor_disclosure`'s docstring for the three demonstrated gaps (mis-constructed
  single-token content, an inverted-but-phrase-preserving reword, and positions that are only as
  correct as the exporter's tokenizer work upstream).
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
#: (coverage.S.status, coverage.S.anchors) required while S intake is blocked. See load_anchor_package.
S_COVERAGE_POLICY = ("blocked", 0)
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


def _position(value: Any) -> bool:
    """A locus index must be a real non-negative int. `True == 1` and `'7' == 7` are the two
    ways a weak check passes on data that cannot be used as an index (§12 round-2 audit)."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def validate_anchor_disclosure(anchor: dict[str, Any]) -> list[str]:
    """Return a list of disclosure violations for one anchor (empty == admissible).

    Fail-closed by construction: a non-dict anchor, an unknown `decision_tokenarity`, a task
    outside the V/T/C allow-list, a missing or non-integer position, a broken
    `P_decision == P_boundary` equality, or a stripped caveat is a violation, never a default.

    WHAT THIS DOES NOT CHECK, and cannot from CPU-side JSON: whether the anchor's CONTENT really
    is a single-token decision. `TOKENARITY_BY_TASK` pins the per-task class the exporter assigns,
    so a V anchor whose gold/label was itself mis-constructed as multi-token still passes — that
    is an upstream construct-validity question (the B9-03 human audit), not a locus-disclosure one.
    Likewise a rewording of `position_definitions.P_decision` that keeps the required substring
    while asserting the opposite meaning passes the substring check; the phrase pin catches
    *silencing*, not *inversion*. Confirming the numbers themselves are the right positions
    requires the locked tokenizer and `run_pilot.build_token_anchor`'s two-path equality (F-08),
    which is upstream of this module and out of scope for a CPU-only consumer gate.
    """
    if not isinstance(anchor, dict):
        return [f"anchor is {type(anchor).__name__}, not an object; locus semantics cannot be established"]
    problems: list[str] = []
    example_id = anchor.get("example_id", "<no example_id>")
    tokenarity = anchor.get("decision_tokenarity")
    task = anchor.get("task")
    if tokenarity not in (SINGLE_TOKEN_LOCUS, MULTI_TOKEN_LOCUS):
        problems.append(f"{example_id}: decision_tokenarity is {tokenarity!r}, not a known tokenarity class")
        return problems
    expected = TOKENARITY_BY_TASK.get(task)
    if expected is None:
        problems.append(
            f"{example_id}: task {task!r} is not one of {sorted(TOKENARITY_BY_TASK)}; this package declares no "
            "locus semantics for it (an S anchor here would also violate the S-blocked invariant)"
        )
    elif tokenarity != expected:
        problems.append(f"{example_id}: task {task} declares {tokenarity!r}, expected {expected!r}")
    for key in ("P_user", "P_boundary", "P_decision"):
        if not _position(anchor.get(key)):
            problems.append(f"{example_id}: {key} is {anchor.get(key)!r}; must be a non-negative int")
    if all(_position(anchor.get(k)) for k in ("P_boundary", "P_decision")):
        if anchor["P_decision"] != anchor["P_boundary"]:
            problems.append(
                f"{example_id}: P_decision ({anchor['P_decision']}) != P_boundary ({anchor['P_boundary']}); "
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
    """Load TOKEN_ANCHORS.json, refusing (fail-closed) on a broken disclosure or a violated
    coverage policy.

    The coverage policy is part of what this gate means: with `S_DATA_PROTOCOL_v3` still
    `pending_approval` the package MUST contain zero S anchors and MUST say so. Pinning that here
    rather than only in a test means a smuggled S anchor cannot be loaded through the API that
    §12 D5 designates as the consumer path. If S intake ever legitimately completes (§E step 9)
    and the export is re-run under a §12 re-verification, `S_COVERAGE_POLICY` is the single
    constant that changes — the change is deliberate and greppable, never incidental.
    """
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
    problems: list[str] = []
    coverage = doc.get("coverage") or {}
    if not isinstance(coverage, dict) or not coverage:
        problems.append("coverage block is missing; per-task coverage cannot be verified")
    else:
        per_task: dict[str, int] = {}
        for a in anchors:
            per_task[a["task"]] = per_task.get(a["task"], 0) + 1
        for task, entry in coverage.items():
            if isinstance(entry, dict) and isinstance(entry.get("anchors"), int) and entry["anchors"] != per_task.get(task, 0):
                problems.append(f"coverage.{task}.anchors declares {entry['anchors']} but {per_task.get(task, 0)} anchors of that task exist")
        s_entry = coverage.get("S") or {}
        s_status, s_declared = s_entry.get("status"), s_entry.get("anchors")
        if (s_status, s_declared, per_task.get("S", 0)) != (S_COVERAGE_POLICY[0], S_COVERAGE_POLICY[1], 0):
            problems.append(
                f"S coverage is (status={s_status!r}, declared anchors={s_declared!r}, actual={per_task.get('S', 0)}), "
                f"expected {S_COVERAGE_POLICY!r} while S intake is blocked; an S anchor in this package would mean "
                "either S content entered without the §E chain completing, or the policy was changed without a §12 record"
            )
    if problems:
        raise AmbiguousDecisionLocusError(f"{path}: coverage policy violated:\n  " + "\n  ".join(problems))
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
