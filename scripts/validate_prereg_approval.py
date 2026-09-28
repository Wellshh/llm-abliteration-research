from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PROTOCOL_REL = Path("reports/PREREGISTRATION_PHASE0_REVISION_v2_1.yaml")
SIDECAR_REL = Path("reports/PREREGISTRATION_PHASE0_REVISION_v2_1_APPROVAL.json")
APPROVED_PROTOCOL_SHA256 = "7bbd58cae219508702de6293a99ffb8ee1aeb275d29f43aae83a1eaa7d4f1196"
APPROVED_SIDECAR_SHA256 = "5255be431add85e29eccb29892b7bc4c912f94ed03b0c886c8213689c251d96b"


def _fail(message: str) -> None:
    raise SystemExit(f"RC-C3 REFUSING consumer authorization: {message}")


def _read_bytes(path: Path, what: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:  # environment-level failures stay disciplined (review F-3)
        _fail(f"cannot read {what}: {exc}")


def _require_cons_int(value: Any, expected: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value != expected:
        _fail(f"C-18 numeric pin violated: {name} must be exactly {expected} "
              f"(found {value!r}); pins change only together with re-pinned approval bytes")


# Semantic battery, split out for regression-testability (review F-1): these checks
# are what a FUTURE re-pinned approval (e.g. v2.2) must still satisfy; the pinned
# SHAs protect today, this battery protects the re-pin moment.
def _validate_semantics(proto: dict[str, Any], card: dict[str, Any]) -> None:
    # --- approver choices recorded in the sidecar ---
    choices = card.get("approver_choice_record")
    if not isinstance(choices, dict):
        _fail("approver_choice_record is missing")
    expected = {"C-07": "(a)", "C-08": "(P)", "C-18": "(i)"}
    for key, value in expected.items():
        if not isinstance(choices.get(key), dict) or choices[key].get("choice") != value:
            _fail(f"approved choice {key} does not match {value}")
    c18 = choices["C-18"]
    if c18.get("mandatory_denominator") != "(iv) frozen denominator; invalid/missing remain in denominator and never numerator":
        _fail("C-18 mandatory denominator semantics are not approved (iv)")

    # --- authorization scope: the protocol itself keeps every run path closed ---
    scope = proto.get("approval_scope")
    if not isinstance(scope, dict) or scope.get("phase0_construct_admission_met") is not False:
        _fail("protocol phase0_construct_admission_met is not false")
    for key in ("C_freeze_authorized", "level_B_authorized", "model_gpu_authorized", "S_authorized", "round1_authorized"):
        if scope.get(key) is not False:
            _fail(f"protocol authorization scope {key} is not false")
    if scope.get("RC-C3") != "freeze_ticket_mechanical_sidecar_validator_remains_prerequisite":
        _fail("protocol does not preserve RC-C3 as a freeze prerequisite")

    # --- C-07 (a): macro gate at 0.75, categories report-only ---
    cgate = proto.get("c_round_gate", {})
    sem = cgate.get("semantic_accuracy", {})
    if sem.get("aggregation", "").split("=")[0].strip() != "PRIMARY":
        _fail("C-07 protocol aggregation is not primary")
    if sem.get("min") != 0.75 or sem.get("per_category_floor") is not None:
        _fail("C-07 protocol does not encode macro >= 0.75 with report-only categories")

    # --- C-08 (P): percentile, screening, power caveat ---
    tgate = proto.get("t_round_gate", {}).get("c08_uncertainty_rule", {})
    if "PERCENTILE" not in str(tgate.get("interval", "")).upper() or tgate.get("not_a_confirmatory_test") is not True:
        _fail("C-08 protocol is not percentile and non-confirmatory")
    if "SCREENING" not in str(tgate.get("power_caveat", "")).upper():
        _fail("C-08 protocol lacks screening framing and power caveat")

    # --- C-18 (i): swap-only gated; numeric pins symmetric with C-07 (review F-1) ---
    consistency = cgate.get("label_swap_consistency", {})
    pair_set = str(consistency.get("pair_set", ""))
    if not pair_set.startswith("within-family"):
        _fail("C-18 pair_set is not within-family")
    for needle in ("primary_map_1", "primary_map_2", "ONLY", "contribute no pair"):
        if needle not in pair_set:
            _fail("C-18 pair_set does not encode swap-only semantics (missing "
                  f"{needle!r}: merged or widened pair sets are not the approved (i))")
    _require_cons_int(consistency.get("expected_pair_count_round1"), 10, "expected_pair_count_round1")
    if isinstance(consistency.get("min"), bool) or consistency.get("min") != 0.85:
        _fail("C-18 numeric pin violated: min must be exactly 0.85 (found "
              f"{consistency.get('min')!r}); thresholds change only by re-approval")

    # --- C-18 (iv): frozen denominator, defended beyond substrings (CS-1 class) ---
    denom = str(consistency.get("denominator_semantics", ""))
    for needle in ("FROZEN pair count", "NOT recomputed from the outputs",
                   "REMAINS in the denominator", "EXCLUDED from the numerator"):
        if needle not in denom:
            _fail(f"C-18 denominator_semantics missing required clause {needle!r}")
    for forbidden in ("is recomputed from the outputs", "DROPPED"):
        if forbidden in denom:
            _fail(f"C-18 denominator_semantics contains output-dependent language {forbidden!r} "
                  "(the round-B CS-1 major: malformed output must never lower the bar)")

    # --- C-18 (i) stance arm: reported, never gated ---
    stance = cgate.get("stance_consistency")
    if not isinstance(stance, dict) or stance.get("min") is not None:
        _fail("C-18(i): stance_consistency must remain reported-but-UNGATED (min: null)")


def validate_prereg_approval(repo_root: Path, protocol_path: Path | None = None,
                             sidecar_path: Path | None = None) -> dict[str, Any]:
    """Validate the approved v2.1 protocol at the consumer boundary.

    This is deliberately independent of any manifest self-report. It reads both
    bytes ONCE, binds the sidecar to the exact v2.1 path and SHA, checks the
    approved choices and gate-body semantics against the parsed protocol, and
    returns a small audit record only after every check passes; it emits no
    output on rejection.
    """
    if isinstance(repo_root, str):  # review F-3: str roots fail disciplined, not as tracebacks
        repo_root = Path(repo_root)
    if not isinstance(repo_root, Path):
        _fail(f"repo_root must be a Path (got {type(repo_root).__name__})")
    root = repo_root.resolve()
    protocol = (protocol_path or root / PROTOCOL_REL).resolve()
    sidecar = (sidecar_path or root / SIDECAR_REL).resolve()
    expected_protocol = (root / PROTOCOL_REL).resolve()
    expected_sidecar = (root / SIDECAR_REL).resolve()
    if protocol != expected_protocol or sidecar != expected_sidecar:
        _fail("protocol and sidecar paths must be the canonical v2.1 paths")
    if not protocol.is_file() or not sidecar.is_file():
        _fail("approved v2.1 protocol or sidecar is missing")
    # read ONCE; hashing and parsing act on the SAME bytes (review F-4: no
    # hash-check/parse TOCTOU window between separate reads)
    sidecar_raw = _read_bytes(sidecar, "sidecar")
    protocol_raw = _read_bytes(protocol, "protocol")
    sidecar_sha = hashlib.sha256(sidecar_raw).hexdigest()
    if sidecar_sha != APPROVED_SIDECAR_SHA256:
        _fail("sidecar bytes are not the pinned approved v2.1 bytes")
    try:
        import yaml
    except Exception as exc:
        _fail(f"YAML parser unavailable: {exc}")
    try:
        proto = yaml.safe_load(protocol_raw.decode("utf-8"))
        card = json.loads(sidecar_raw.decode("utf-8"))
    except Exception as exc:
        _fail(f"protocol/sidecar parse failed: {exc}")
    if not isinstance(proto, dict) or not isinstance(card, dict):
        _fail("protocol and sidecar must be mappings")
    if card.get("protocol_path") != PROTOCOL_REL.as_posix():
        _fail("sidecar protocol_path is not the canonical v2.1 path")
    if card.get("status") != "approved_data_after_amendment":
        _fail("sidecar is not approved_data_after_amendment")
    if proto.get("status") != "approved_data_after_amendment":
        _fail("protocol status is not approved_data_after_amendment")
    actual_sha = hashlib.sha256(protocol_raw).hexdigest()
    if card.get("protocol_sha256") != actual_sha:
        _fail("sidecar protocol_sha256 does not match protocol bytes")
    if actual_sha != APPROVED_PROTOCOL_SHA256:
        _fail("protocol bytes are not the pinned approved v2.1 bytes")
    freeze = card.get("freeze")
    if not isinstance(freeze, dict) or freeze.get("effective") is not True:
        _fail("sidecar freeze.effective is not true")
    approval = card.get("approval_record")
    if not isinstance(approval, dict) or not approval.get("approved_at"):
        _fail("approval_record is missing approved_at")
    if approval.get("approval_semantics") != "user_approved_phase0_revision_v2_1_choices_C07_C08_C18":
        _fail("approval semantics do not identify the approved v2.1 choices")
    _validate_semantics(proto, card)
    return {"status": card["status"], "effective": True, "protocol_sha256": actual_sha,
            "sidecar_sha256": sidecar_sha,
            "choices": {"C-07": "(a)", "C-08": "(P)", "C-18": "(i)"}, "phase0_construct_admission_met": False}
