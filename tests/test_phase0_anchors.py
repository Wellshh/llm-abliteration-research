"""§12 D5 consumer-gate tests — CPU-only, no tokenizer, no weights, no GPU.

Two halves:
  * against the COMMITTED `artifacts/setup/TOKEN_ANCHORS.json` — the disclosure that D5
    relied on must actually be present in the shipped bytes, and the accessor must refuse
    to hand a T anchor to a single-token-locus consumer;
  * against synthetic anchors — the fail-closed paths (stripped caveat, unknown tokenarity,
    broken equality, task/tokenarity mismatch, bad schema, empty package).
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from minicpm_research.phase0_anchors import (  # noqa: E402
    DEFAULT_ANCHORS,
    MULTI_TOKEN_LOCUS,
    SCHEMA,
    SINGLE_TOKEN_LOCUS,
    AmbiguousDecisionLocusError,
    first_generated_token_locus,
    load_anchor_package,
    package_summary,
    single_token_decision_locus,
    validate_anchor_disclosure,
)


def _anchor(**over) -> dict:
    a = {
        "example_id": "synthetic-X-0",
        "family_id": "synthetic-X",
        "task": "V",
        "P_user": 3,
        "P_boundary": 9,
        "P_decision": 9,
        "decision_tokenarity": SINGLE_TOKEN_LOCUS,
        "position_definitions": {
            "P_boundary": "last token of the full assistant prefix; its hidden state predicts the FIRST generated token",
            "P_decision": ("… For T native tool calls the action is distributed over multiple generated tokens, so "
                            "P_decision==P_boundary is the FIRST-generated-token locus, NOT a single-token decision "
                            "locus (plan §6.1; audit F-06)."),
        },
    }
    a.update(over)
    return a


class CommittedPackageTests(unittest.TestCase):
    """The requirement is pinned to the shipped artifact, not to a fixture."""

    @classmethod
    def setUpClass(cls):
        cls.doc = load_anchor_package()
        cls.anchors = cls.doc["anchors"]

    def test_artifact_is_the_committed_one(self):
        self.assertTrue(DEFAULT_ANCHORS.exists(), DEFAULT_ANCHORS)

    def test_per_task_counts_and_s_fail_closed(self):
        s = package_summary(self.doc)
        self.assertEqual(s["schema"], SCHEMA)
        self.assertEqual(s["ticket"], "B8-01")
        self.assertEqual(s["anchors_per_task"], {"V": 8, "T": 8, "C": 8})
        self.assertEqual(s["anchor_count"], 24)
        self.assertNotIn("S", s["anchors_per_task"])
        self.assertEqual(s["s_anchor_count"], 0)
        self.assertEqual(s["s_coverage_status"], "blocked")
        self.assertEqual(s["single_token_locus_anchors"], 16)
        self.assertEqual(s["multi_token_locus_anchors"], 8)

    def test_every_anchor_passes_disclosure_validation(self):
        for a in self.anchors:
            self.assertEqual(validate_anchor_disclosure(a), [], a["example_id"])

    def test_tokenarity_matches_task(self):
        for a in self.anchors:
            expected = MULTI_TOKEN_LOCUS if a["task"] == "T" else SINGLE_TOKEN_LOCUS
            self.assertEqual(a["decision_tokenarity"], expected, a["example_id"])

    def test_c_anchors_marked_provisional_not_frozen(self):
        """The C re-export-after-freeze obligation must remain visible in the artifact."""
        s = package_summary(self.doc)
        self.assertIn("candidate_draft_not_frozen", s["c_coverage_status"])
        self.assertIn("reexport_after_freeze", s["c_coverage_status"])
        for a in self.anchors:
            if a["task"] == "C":
                self.assertIn("candidate_draft_not_frozen", a["source_status"])

    def test_single_token_locus_works_for_v_and_c(self):
        for a in self.anchors:
            if a["decision_tokenarity"] == SINGLE_TOKEN_LOCUS:
                loc = single_token_decision_locus(a)
                self.assertTrue(loc["is_single_token_decision_locus"])
                self.assertEqual(loc["P_decision"], a["P_boundary"])

    def test_single_token_locus_refuses_every_t_anchor(self):
        """D5's substance: no T anchor may be consumed as a single-token decision locus."""
        t_anchors = [a for a in self.anchors if a["task"] == "T"]
        self.assertEqual(len(t_anchors), 8)
        for a in t_anchors:
            with self.assertRaises(AmbiguousDecisionLocusError) as ctx:
                single_token_decision_locus(a)
            msg = str(ctx.exception)
            self.assertIn("first-generated-token locus", msg)
            self.assertIn("F-06", msg)
            self.assertIn(a["example_id"], msg)

    def test_first_generated_token_locus_is_never_a_single_token_claim(self):
        for a in self.anchors:
            loc = first_generated_token_locus(a)
            self.assertEqual(loc["P_boundary"], a["P_boundary"])
            self.assertFalse(loc["is_single_token_decision_locus"])
            self.assertIn("plan §6.1", loc["read_before_use"])

    def test_lock_binding_is_the_locked_tokenizer(self):
        lock = json.loads((DEFAULT_ANCHORS.parents[1] / "model/MODEL_MANIFEST.json").read_text(encoding="utf-8"))
        lb = package_summary(self.doc)["lock_binding"]
        self.assertEqual(lb["revision_sha"], lock["revision_sha"])
        self.assertEqual(lb["tokenizer_file_sha256"], lock["files"]["tokenizer.json"]["sha256"])
        self.assertEqual(lb["chat_template_sha256"], lock["chat_template_sha256"])


class FailClosedTests(unittest.TestCase):
    def test_stripped_caveat_is_a_violation(self):
        a = _anchor()
        a["position_definitions"]["P_decision"] = "the decision locus"
        self.assertTrue(any("F-06" in p for p in validate_anchor_disclosure(a)))

    def test_missing_position_definitions_is_a_violation(self):
        a = _anchor()
        a.pop("position_definitions")
        self.assertTrue(validate_anchor_disclosure(a))

    def test_unknown_tokenarity_is_a_violation_and_short_circuits(self):
        a = _anchor(decision_tokenarity="who_knows")
        problems = validate_anchor_disclosure(a)
        self.assertEqual(len(problems), 1)
        self.assertIn("not a known tokenarity class", problems[0])

    def test_broken_equality_is_a_violation(self):
        a = _anchor(P_decision=8)
        self.assertTrue(any("P_decision" in p and "P_boundary" in p for p in validate_anchor_disclosure(a)))

    def test_task_tokenarity_mismatch_is_a_violation(self):
        """A re-export that labels a T anchor single-token (erasing F-06) must not pass."""
        a = _anchor(task="T")
        problems = validate_anchor_disclosure(a)
        self.assertTrue(any("expected 'multi_token_native_tool_call'" in p for p in problems))

    def test_synthetic_t_anchor_refused_by_single_token_accessor(self):
        a = _anchor(task="T", decision_tokenarity=MULTI_TOKEN_LOCUS)
        with self.assertRaises(AmbiguousDecisionLocusError):
            single_token_decision_locus(a)
        self.assertFalse(first_generated_token_locus(a)["is_single_token_decision_locus"])

    def _write(self, doc) -> Path:
        tmp = Path(tempfile.mkdtemp()) / "TOKEN_ANCHORS.json"
        tmp.write_text(json.dumps(doc), encoding="utf-8")
        return tmp

    def test_load_refuses_bad_schema(self):
        doc = copy.deepcopy(self_doc())
        doc["schema"] = "phase0_token_anchors_v0"
        with self.assertRaises(AmbiguousDecisionLocusError):
            load_anchor_package(self._write(doc))

    def test_load_refuses_empty_anchor_list(self):
        doc = copy.deepcopy(self_doc())
        doc["anchors"] = []
        with self.assertRaises(AmbiguousDecisionLocusError):
            load_anchor_package(self._write(doc))

    def test_load_refuses_when_reexport_dropped_the_disclosure(self):
        doc = copy.deepcopy(self_doc())
        doc["anchors"][0]["position_definitions"]["P_decision"] = "the decision locus"
        with self.assertRaises(AmbiguousDecisionLocusError) as ctx:
            load_anchor_package(self._write(doc))
        self.assertIn("violation", str(ctx.exception))

    # ---- §12 round-2 hardening: type strictness, non-dict inputs, coverage policy ----

    def test_string_position_is_a_violation_not_a_vacuous_equality(self):
        """'7' == 7 is False, but a missing type check let a str locus through the equality test."""
        a = _anchor(P_decision="7", P_boundary="7")
        problems = validate_anchor_disclosure(a)
        self.assertTrue(any("must be a non-negative int" in p for p in problems), problems)
        with self.assertRaises(AmbiguousDecisionLocusError):
            single_token_decision_locus(a)

    def test_bool_position_is_a_violation(self):
        """True == 1 in Python; a bool locus must not read as index 1."""
        a = _anchor(P_decision=True, P_boundary=True)
        self.assertTrue(any("must be a non-negative int" in p for p in validate_anchor_disclosure(a)))

    def test_missing_positions_violate_instead_of_raising_keyerror(self):
        a = _anchor()
        for k in ("P_user", "P_boundary", "P_decision"):
            a.pop(k)
        self.assertTrue(any("must be a non-negative int" in p for p in validate_anchor_disclosure(a)))
        with self.assertRaises(AmbiguousDecisionLocusError):
            single_token_decision_locus(a)      # documented exception, not KeyError

    def test_non_dict_anchor_is_a_violation(self):
        self.assertTrue(validate_anchor_disclosure("oops"))
        doc = copy.deepcopy(self_doc())
        doc["anchors"].append("oops")
        with self.assertRaises(AmbiguousDecisionLocusError):
            load_anchor_package(self._write(doc))

    def test_unknown_task_is_a_violation(self):
        """The old code only checked tokenarity when the task was known, so an unseen task could
        carry any class — including a task='S' anchor smuggled into a package that claims S is blocked."""
        a = _anchor(task="S", decision_tokenarity=SINGLE_TOKEN_LOCUS)
        self.assertTrue(any("not one of" in p for p in validate_anchor_disclosure(a)), )

    def test_load_refuses_a_smuggled_S_anchor(self):
        doc = copy.deepcopy(self_doc())
        doc["anchors"].append(_anchor(example_id="smuggled-S-0", family_id="smuggled-S", task="S",
                                      decision_tokenarity=SINGLE_TOKEN_LOCUS))
        with self.assertRaises(AmbiguousDecisionLocusError) as ctx:
            load_anchor_package(self._write(doc))
        # refused at the anchor layer (unknown task) before the package layer could be reached
        self.assertIn("task 'S'", str(ctx.exception))

    def test_load_refuses_an_S_coverage_claim_that_is_not_blocked(self):
        """The package-level half of the same invariant: an S coverage block that no longer says
        'blocked / 0 anchors' cannot load either, even with every anchor individually valid."""
        doc = copy.deepcopy(self_doc())
        doc["coverage"]["S"] = {"required_min": 8, "anchors": 0, "status": "intake_complete"}
        with self.assertRaises(AmbiguousDecisionLocusError) as ctx:
            load_anchor_package(self._write(doc))
        self.assertIn("coverage policy", str(ctx.exception))

    def test_load_refuses_coverage_counts_that_lie(self):
        doc = copy.deepcopy(self_doc())
        doc["coverage"]["V"]["anchors"] = 99          # declares 9, ships 8
        with self.assertRaises(AmbiguousDecisionLocusError) as ctx:
            load_anchor_package(self._write(doc))
        self.assertIn("coverage.V.anchors", str(ctx.exception))


class ProvenancePinTests(unittest.TestCase):
    """§12 round-2 falsification test (skeptic RT-3): the record's strongest present-tense claim is
    'both B8-01 artifacts are byte-unchanged'. Until now that was human-verified prose only, with the
    hashes appearing in no test. Pinning them converts it into code: ANY byte change fails here
    immediately, including a re-export that preserves every semantic check below.

    ESCAPE HATCH, deliberately loud: these pins are EXPECTED to fail the moment the mandated
    post-freeze C re-export (§C / audit F-07) or an approved S intake re-export runs. That failure is
    the gate working — update these values only together with (i) the approved amendment that
    authorised the re-export, (ii) a new §12 re-verification record of the new bytes, and (iii)
    updates to every report citing the old hashes (INDEPENDENT_REVERIFICATION_20260917.md,
    B8_01_EXECUTION_NOTE_20260916.md, CURRENT_STATE §12, APPROVAL_PACKETS §F).
    """

    PINNED_SHA256 = {
        "TOKEN_ANCHORS.json": "ecdac639ab8a42aa92a5db9cd632df3a6d84e8d04f56da0c3c4562fe78174c91",
        "ENVIRONMENT.json": "5b8b5bf6cf96d68bc6c556b300dcdce09a5589db058389f81622a9e3400fd027",
    }
    # Independent of the file hash: catches an off-by-one that shifts every locus index while
    # leaving the disclosure shape intact, and says so in its own message.
    PINNED_LOCUS_DIGEST = "b3eb7eedcdb4447b5efa24247c1bfbd58b67d0a0cf123c92c2034582d415580f"

    def test_artifact_bytes_match_the_recorded_hashes(self):
        for name, expected in self.PINNED_SHA256.items():
            with self.subTest(artifact=name):
                actual = hashlib.sha256((DEFAULT_ANCHORS.parents[0] / name).read_bytes()).hexdigest()
                self.assertEqual(actual, expected,
                                 f"{name} changed on disk. If this was an authorised re-export, follow "
                                 "the escape hatch in this class docstring; otherwise STOP — an "
                                 "hash-pinned Phase-0 precondition artifact was silently modified.")

    def test_locus_positions_match_the_recorded_digest(self):
        doc = json.loads(DEFAULT_ANCHORS.read_text(encoding="utf-8"))
        rows = sorted((a["example_id"], a["task"], a["P_user"], a["P_boundary"], a["P_decision"]) for a in doc["anchors"])
        digest = hashlib.sha256(json.dumps(rows, sort_keys=True).encode("utf-8")).hexdigest()
        self.assertEqual(digest, self.PINNED_LOCUS_DIGEST,
                         "P_user/P_boundary/P_decision changed for at least one anchor while the file may "
                         "still look structurally valid — this is exactly the semantic re-export that "
                         "disclosure checks cannot see.")


_DOC_CACHE: dict | None = None


def self_doc() -> dict:
    global _DOC_CACHE
    if _DOC_CACHE is None:
        _DOC_CACHE = json.loads(DEFAULT_ANCHORS.read_text(encoding="utf-8"))
    return _DOC_CACHE


if __name__ == "__main__":
    unittest.main()
