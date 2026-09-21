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


def validate_prereg_approval(repo_root: Path, protocol_path: Path | None = None,
                             sidecar_path: Path | None = None) -> dict[str, Any]:
    """Validate the approved v2.1 protocol at the consumer boundary.

    This is deliberately independent of any manifest self-report. It reads both
    bytes, binds the sidecar to the exact v2.1 path and SHA, and checks the
    approved choices against the parsed protocol. It returns a small audit record
    only after every check passes and emits no output on rejection.
    """
    root = repo_root.resolve()
    protocol = (protocol_path or root / PROTOCOL_REL).resolve()
    sidecar = (sidecar_path or root / SIDECAR_REL).resolve()
    expected_protocol = (root / PROTOCOL_REL).resolve()
    expected_sidecar = (root / SIDECAR_REL).resolve()
    if protocol != expected_protocol or sidecar != expected_sidecar:
        _fail("protocol and sidecar paths must be the canonical v2.1 paths")
    if not protocol.is_file() or not sidecar.is_file():
        _fail("approved v2.1 protocol or sidecar is missing")
    sidecar_sha = hashlib.sha256(sidecar.read_bytes()).hexdigest()
    if sidecar_sha != APPROVED_SIDECAR_SHA256:
        _fail("sidecar bytes are not the pinned approved v2.1 bytes")
    try:
        import yaml
    except Exception as exc:
        _fail(f"YAML parser unavailable: {exc}")
    try:
        proto = yaml.safe_load(protocol.read_text(encoding="utf-8"))
        card = json.loads(sidecar.read_text(encoding="utf-8"))
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
    actual_sha = hashlib.sha256(protocol.read_bytes()).hexdigest()
    if card.get("protocol_sha256") != actual_sha:
        _fail("sidecar protocol_sha256 does not match protocol bytes")
    if actual_sha != APPROVED_PROTOCOL_SHA256:
        _fail("protocol bytes are not the pinned approved v2.1 bytes")
    freeze = card.get("freeze")
    if not isinstance(freeze, dict) or freeze.get("effective") is not True:
        _fail("sidecar freeze.effective is not true")
    approval = card.get("approval_record")
    choices = card.get("approver_choice_record")
    if not isinstance(approval, dict) or not approval.get("approved_at"):
        _fail("approval_record is missing approved_at")
    if approval.get("approval_semantics") != "user_approved_phase0_revision_v2_1_choices_C07_C08_C18":
        _fail("approval semantics do not identify the approved v2.1 choices")
    if not isinstance(choices, dict):
        _fail("approver_choice_record is missing")
    expected = {"C-07": "(a)", "C-08": "(P)", "C-18": "(i)"}
    for key, value in expected.items():
        if not isinstance(choices.get(key), dict) or choices[key].get("choice") != value:
            _fail(f"approved choice {key} does not match {value}")
    c18 = choices["C-18"]
    if c18.get("mandatory_denominator") != "(iv) frozen denominator; invalid/missing remain in denominator and never numerator":
        _fail("C-18 mandatory denominator semantics are not approved (iv)")
    scope = proto.get("approval_scope")
    if not isinstance(scope, dict) or scope.get("phase0_construct_admission_met") is not False:
        _fail("protocol phase0_construct_admission_met is not false")
    for key in ("C_freeze_authorized", "level_B_authorized", "model_gpu_authorized", "S_authorized", "round1_authorized"):
        if scope.get(key) is not False:
            _fail(f"protocol authorization scope {key} is not false")
    if scope.get("RC-C3") != "freeze_ticket_mechanical_sidecar_validator_remains_prerequisite":
        _fail("protocol does not preserve RC-C3 as a freeze prerequisite")
    cgate = proto.get("c_round_gate", {})
    sem = cgate.get("semantic_accuracy", {})
    if sem.get("aggregation", "").split("=")[0].strip() != "PRIMARY":
        _fail("C-07 protocol aggregation is not primary")
    if sem.get("min") != 0.75 or sem.get("per_category_floor") is not None:
        _fail("C-07 protocol does not encode macro >= 0.75 with report-only categories")
    tgate = proto.get("t_round_gate", {}).get("c08_uncertainty_rule", {})
    if "PERCENTILE" not in str(tgate.get("interval", "")).upper() or tgate.get("not_a_confirmatory_test") is not True:
        _fail("C-08 protocol is not percentile and non-confirmatory")
    if "SCREENING" not in str(tgate.get("power_caveat", "")).upper():
        _fail("C-08 protocol lacks screening framing and power caveat")
    consistency = cgate.get("label_swap_consistency", {})
    denom = str(consistency.get("denominator_semantics", ""))
    if not str(consistency.get("pair_set", "")).startswith("within-family") or "FROZEN pair count" not in denom or "REMAINS in the denominator" not in denom:
        _fail("C-18 protocol does not encode swap-only frozen-denominator semantics")
    return {"status": card["status"], "effective": True, "protocol_sha256": actual_sha,
            "sidecar_sha256": sidecar_sha,
            "choices": expected, "phase0_construct_admission_met": False}
