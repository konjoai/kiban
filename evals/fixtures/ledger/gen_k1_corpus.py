#!/usr/bin/env python3
"""Generate the KT-1 / KT-2 test corpus for Sprint K1 (cortex projection).

No real ~/.konjo/state/ledger/decisions.jsonl exists anywhere reachable from this
repo or this container -- confirmed at sprint kickoff (KT-1's own brief). Real usage
data lives only on the user's laptop. Per Wes's explicit choice (Phase 0), this
corpus is built by transcribing kiban's own real historical decisions -- the ones
already recorded in prose in `LEDGER.md` -- into the Ledger's event schema, rather
than fabricating synthetic content. Every `decision`/`rationale` string below is a
compressed, faithful restatement of a real `LEDGER.md` entry; nothing here was
invented.

A handful of entries needed a synthetic *predecessor* event to give the corpus a
supersede chain or a redact target to search for -- `LEDGER.md` records the outcome
of a change ("runs=1 -> runs=3", "advisory -> blocking for lopi") but not always the
original decision as its own dated entry. Those predecessors are marked
`# synthetic predecessor` below and kept minimal; the real content is always the
event that matters (the supersede/redact payload).

Deterministic: ids are `sha1(decision_text)[:12]`, so re-running this script against
an empty state dir reproduces byte-identical output -- required for KT-2's idempotency
claim to mean anything applied to a realistic-sized corpus, not just the unit-test
fixture in `tests/test_cortex.py`.

Sprint K5 moved the store from one appended JSONL file to one file per event
(`ledger/events/<id>.json`) -- this generator writes through `lib.event_store` now,
same as any other writer, so the fixture stays representative of real storage.

Usage:
    KONJO_STATE_DIR=/path/to/fixture/state python3 evals/fixtures/ledger/gen_k1_corpus.py
"""

from __future__ import annotations

import hashlib
import pathlib
import sys

_KIBAN_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
if str(_KIBAN_ROOT) not in sys.path:
    sys.path.insert(0, str(_KIBAN_ROOT))

from lib import event_store  # noqa: E402

SCOPE = "repo:kiban"
AUTHOR = "wes"
LEDGER_PATH = "ledger/events"


def _id(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


# (date, decision, rationale, alternatives, confidence) -- 25 pristine, standalone
# topics, each its own decide event, drawn one-to-one from a real LEDGER.md entry.
PRISTINE: list[tuple[str, str, str, list[str], int]] = [
    ("2026-06-15",
     "Absorb the konjo-* skill family into kiban's global plugins/konjo/skills/ plane "
     "instead of keeping a per-repo copy.",
     "lopi's docs/LOOP_ENGINEERING_ROADMAP.md asserted four capability gaps already "
     "closed on main because konjo-ship's checklist named no file that would ever "
     "surface it; the per-repo copy plane is what let it decay unnoticed.",
     ["keep the per-repo plane and build a sync mechanism", "hand-edit lopi/miru now"], 8),
    ("2026-06-16",
     "Add Konjo-Doc-Verified as a fourth record-and-check trailer, reusing "
     "oneway.make_trailer/find_trailer and the existing fingerprint scheme.",
     "a decays: state doc with no verified-against stamp is a hard FAIL; the trailer "
     "needed a home in the same family as Konjo-Acknowledged-Oneway and "
     "Konjo-Prove-Merge rather than inventing a fourth format.",
     ["invent a new ad hoc trailer format"], 9),
    ("2026-06-18",
     "Make review incompleteness block the merge instead of passing silently.",
     "CLIBackend.dispatch funneled TimeoutExpired, OSError, and a non-zero CLI exit "
     "into a return value the parser reads as zero findings, so a specialist that "
     "never completed was indistinguishable from a clean review.",
     ["WARN-only signal on incomplete review"], 9),
    ("2026-06-19",
     "Retry a failed review specialist once before hard-blocking, rather than "
     "blocking immediately on first failure.",
     "a transient network blip should not cost the same as a specialist that is "
     "actually broken, or operators will start treating every INCOMPLETE as noise.",
     ["immediate block on first failure", "multi-run self-consistency"], 7),
    ("2026-06-24",
     "Write KONJO_FORWARD.md for real instead of continuing to cite it as an "
     "already-established doc.",
     "the birth-defect proposal and this sprint's own brief quoted exact sentences "
     "from a doc that did not exist in the repo; the gap needed recording, not "
     "papering over.",
     ["quietly author it with no note that it was previously missing"], 8),
    ("2026-06-30",
     "Author profiles/lopi.yml documenting what lopi's CI already enforces, without "
     "rebuilding lopi's own enforcement.",
     "nine of lopi's real CI checks stay repo-native by design; this phase connects "
     "the pilot, it does not take over lopi's CI.",
     ["migrate lopi's checks into konjo-gates wholesale"], 7),
    ("2026-07-03",
     "Build konjo-threat / gate_threat_model as a third record-and-check pair, and "
     "add security_globs as a new permanent profile field.",
     "brief-time classification against a fixed eight-class trust-boundary taxonomy, "
     "matching konjo-oneway/konjo-prove's existing shape.",
     ["fold threat classification into the existing oneway mechanism instead of a "
      "new pair"], 7),
    ("2026-07-05",
     "Add evals/gen_fixtures/ and konjo-eval gen as a new, report-only fixture "
     "generation path.",
     "grows the eval corpus's shape without a blocking gate; distinct fixture shape "
     "from the hand-authored ones, so it needed its own CI job.",
     ["extend the existing hand-authored fixture path instead of a new one"], 6),
    ("2026-07-07",
     "Convert lopi's four sprint-cited security lines through konjo-learn instead of "
     "leaving them as prose citations.",
     "confirmed by running the guardrail for real -- only security.md carried any "
     "Sprint S\\d+ citations, and all four found a home.",
     ["leave the citations as plain prose, uningested"], 6),
    ("2026-07-09",
     "Author profiles/squish.yml and profiles/vectro.yml promote/keep/delete tables "
     "without rebuilding either repo's CI.",
     "matches Lopi-Gate-Reconciliation-1's own non-goal-respecting shape: connect "
     "and record what exists, don't rebuild it.",
     ["rebuild squish's and vectro's CI while reconciling"], 7),
    ("2026-07-10",
     "Record that most of squish's and vectro's 'Wall 2' CI is decorative, without "
     "fixing it this phase.",
     "read both repos' real konjo-gate.yml in full rather than trusting "
     "profiles/*.yml's existing declarations; a real finding neither the brief nor "
     "either repo's own CLAUDE.md had named.",
     ["silently fix the decorative CI while reconciling"], 7),
    ("2026-07-13",
     "Classify 4 more of the 8 defect taxonomy classes mechanically (3 to 7 of 8) in "
     "evals/genfixtures.py.",
     "grew mechanical coverage without writing a fully new detector for most of it, "
     "per 'reuse before you build'.",
     ["write a bespoke detector for every remaining taxonomy class"], 6),
    ("2026-07-15",
     "Publish an honest null result: both tested context-reduction candidates "
     "measured null on real closed lopi work.",
     "2 tasks, 3 conditions, deliberately distinct from KT-14.1's tasks to avoid "
     "confounding incidental-defect reduction with explicit-fix-instruction "
     "following; the measurement itself caught a live classifier bug.",
     ["quietly shelve the null result and not publish it"], 7),
    ("2026-07-17",
     "Build lib/gen_runner.py + evals/gen_cassettes.py + konjo-eval genrun as the "
     "missing 'task in, diff out' measurement instrument.",
     "konjo-headless/lib/headless.py was found to be a thin claude -p argv builder "
     "with no such loop; Phase 1 builds the loop as a consumer of lib.headless, not "
     "a replacement.",
     ["replace lib.headless outright instead of building a consumer on top"], 8),
    ("2026-07-19",
     "Instrument the review-pipeline plan's telemetry and backfill it against real "
     "history before writing any gate.",
     "PF-1 corrected the plan on two tooling assumptions before any code was "
     "written.",
     ["build the gate first and instrument telemetry later"], 7),
    ("2026-07-21",
     "Ship the plan-artifact schema and the telemetry fields it feeds from kiban's "
     "side, leaving the Planner/Executor handoff itself to lopi's own sprint.",
     "kiban's scope is the schema and telemetry wiring; the handoff and its "
     "kill-tests are recorded in lopi's own LEDGER.md.",
     ["implement the Planner/Executor handoff inside kiban itself"], 6),
    ("2026-07-23",
     "Ship the mutation-feedback formatter (section 2) this phase; defer sections 1, "
     "3, and 4 until the PF-0 baseline exists.",
     "PF-3 passed as the load-bearing kill-test; the deferred sections were "
     "explicitly calibrated against data PF-0 had not produced yet.",
     ["build all four sections against a synthetic baseline"], 6),
    ("2026-07-25",
     "Fix three real lib/bench.py bugs found while gathering a third PF-0 data "
     "point, rather than working around them.",
     "cargo 1.88.0 exits 101 (not 127) on an unrecognized subcommand; the "
     "nextest-missing fallback never fired until this was fixed.",
     ["special-case the new exit code at the call site instead of fixing bench.py"], 8),
    ("2026-07-27",
     "Extend konjo-ast-diff-rs with a --items mode using real syn spans, rather "
     "than falling back to an outcomes.json-derived approximation.",
     "confirmed with a minimal scratch crate that span-locations gives real "
     "1-indexed LineColumn values before touching the real crate.",
     ["use the outcomes.json-derived fallback line-number approximation"], 8),
    ("2026-07-28",
     "Scope --in-diff against the fixed production diff (diff_base_ref), separate "
     "from the round's own worktree checkout point (base_ref).",
     "scoping --in-diff against a round's own test-writing diff touches zero "
     "production lines, so the loop would never find a single mutant; found by "
     "actually running the loop, not by inspection.",
     ["scope --in-diff against the round's own diff and accept the loop never "
      "finding mutants"], 9),
    ("2026-07-29",
     "Package konjo/mutation-hunt as a skill pointing at bin/kiban-mutation-hunt, "
     "with lopi's CI job opt-in via workflow_dispatch only.",
     "the plan's own non-goal is no new default gate this sprint, and the loop "
     "spends real model tokens per round, so it should not run on every push.",
     ["wire it into the required push-triggered gate set immediately"], 7),
    ("2026-07-31",
     "Treat the task-to-diff harness as a permanent, one-way measurement "
     "instrument for every future authoring-context claim, not a one-off script.",
     "Phase 2's six candidate invariants (and every later claim) now measure "
     "against this harness; reverting it invalidates the measurement basis those "
     "claims rest on.",
     ["treat it as disposable, throwaway tooling for this phase only"], 8),
    ("2026-08-02",
     "Add a tier field (blocking/advisory) to the profile schema, with the "
     "pre-existing advisory: bool flags kept working as aliases.",
     "companion to lopi's own Gate-Tiering-1, so the BLOCKING/ADVISORY split does "
     "not have to be independently rediscovered per repo.",
     ["drop the legacy advisory: bool flags outright instead of aliasing them"], 8),
    ("2026-08-04",
     "Measure what a gate costs, not just what it catches, via gate_stats.py's "
     "BLOCKING_READY/ADVISORY_ONLY/INSUFFICIENT_DATA tags against a 5% "
     "false-positive ceiling over a 20-run floor.",
     "the framework already measured whether a gate catches a defect; it never "
     "measured cost, and promoting a gate needs both a passing kill-test and a "
     "measured false-positive rate.",
     ["promote gates on kill-test results alone, without a cost measurement"], 7),
    ("2026-08-06",
     "Add gate_blocking_promotion as its own meta-gate rather than folding the "
     "check into gate_can_fail's existing blanket rule.",
     "deliberately narrower -- the tier-specific half of the two promotion "
     "criteria -- so it survives independent of whether gate_can_fail's rule ever "
     "loosens for advisory-tier entries.",
     ["extend gate_can_fail's existing rule to cover tier promotion too"], 7),
]

# 3 supersede chains: (predecessor decision/rationale, then the real-content
# supersede's decision/rationale/alternatives/confidence).
CHAINS: list[dict] = [
    {
        "date_a": "2026-06-27", "date_b": "2026-07-11",
        # synthetic predecessor
        "decision_a": "Ship gate_claude_contract as advisory across every pilot repo.",
        "rationale_a": "made S13 Phase 0's one-time hand audit of CLAUDE.md permanent "
                       "and mechanical, starting from the same adoption-ramp shape as "
                       "gate_polarity.",
        "decision_b": "Flip gate_claude_contract to blocking for lopi (0 standing "
                      "violations); keep squish and vectro advisory.",
        "rationale_b": "a default change made per-repo on measured evidence, not a "
                       "blanket flip -- Phase 4 measured check_contract against all "
                       "three real pilot repos' actual current CLAUDE.md.",
        "alts_b": ["flip all three repos to blocking at once"], "conf_b": 8,
    },
    {
        "date_a": "2026-05-20", "date_b": "2026-06-26",
        "decision_a": "Sprint completion checklist requires a self-graded 'zero dead "
                      "code' line.",  # synthetic predecessor
        "rationale_a": "original checklist wording; no independently verifiable "
                       "command backed it.",
        "decision_b": "Remove the self-graded 'zero dead code' checklist line and "
                      "replace it with two concrete commands.",
        "rationale_b": "self-grading zero dead code produced no evidence a reviewer "
                       "could check; kiban ships from one global clone, so replacing "
                       "the line changes every consuming repo's definition of done "
                       "simultaneously.",
        "alts_b": ["keep the self-graded line and add commands alongside it"], "conf_b": 8,
    },
    {
        "date_a": "2026-06-01", "date_b": "2026-06-22",
        "decision_a": "review_diff defaults to runs=1 -- one pass per PR.",  # synthetic predecessor
        "rationale_a": "initial implementation default, never revisited after "
                       "multi-run machinery was built.",
        "decision_b": "Default review_diff to runs=3 instead of runs=1.",
        "rationale_b": "one pass was not enough for the single most consequential "
                       "judgment in the framework; runs=1 was a leftover default "
                       "nobody had revisited.",
        "alts_b": ["keep runs=1", "make it repo-configurable only"], "conf_b": 7,
    },
]

# 2 redacts: (predecessor decide, then a real-content redact reason).
REDACTS: list[dict] = [
    {
        "date_a": "2026-07-20", "date_b": "2026-07-27",
        "decision_a": "If real syn spans don't work, fall back to an "
                      "outcomes.json-derived line-number approximation for "
                      "--items.",  # synthetic predecessor / contingency plan
        "rationale_a": "PF-1b's own stop rule named this as the fallback path if "
                       "span-locations proved unusable.",
        "reason_b": "confirmed span-locations gives real 1-indexed LineColumn "
                    "values against a known 5-line snippet; the fallback was not "
                    "needed.",
    },
    {
        "date_a": "2026-07-12", "date_b": "2026-07-13",
        "decision_a": "Attempt to mechanically classify raw_index_external_input "
                      "the same way as the other seven defect taxonomy "
                      "classes.",  # synthetic predecessor
        "rationale_a": "taxonomy completeness goal for evals/genfixtures.py's "
                       "MECHANICALLY_CLASSIFIED coverage.",
        "reason_b": "confirmed genuinely not mechanically classifiable this way; "
                    "recorded honestly as a gap rather than forced.",
    },
]


def main() -> None:
    for date, decision, rationale, alts, conf in PRISTINE:
        did = _id(decision)
        event_store.write_event(LEDGER_PATH, did, {
            "event": "decide", "id": did, "scope": SCOPE,
            "decision": decision, "rationale": rationale,
            "alternatives_considered": alts, "confidence": conf,
            "date": f"{date}T12:00:00Z", "author": AUTHOR,
        })

    for c in CHAINS:
        a_id = _id(c["decision_a"])
        b_id = _id(c["decision_b"])
        event_store.write_event(LEDGER_PATH, a_id, {
            "event": "decide", "id": a_id, "scope": SCOPE,
            "decision": c["decision_a"], "rationale": c["rationale_a"],
            "alternatives_considered": [], "confidence": 5,
            "date": f"{c['date_a']}T12:00:00Z", "author": AUTHOR,
        })
        event_store.write_event(LEDGER_PATH, b_id, {
            "event": "supersede", "id": b_id, "supersedes": a_id, "scope": SCOPE,
            "decision": c["decision_b"], "rationale": c["rationale_b"],
            "alternatives_considered": c["alts_b"], "confidence": c["conf_b"],
            "date": f"{c['date_b']}T12:00:00Z", "author": AUTHOR,
        })

    for r in REDACTS:
        a_id = _id(r["decision_a"])
        event_store.write_event(LEDGER_PATH, a_id, {
            "event": "decide", "id": a_id, "scope": SCOPE,
            "decision": r["decision_a"], "rationale": r["rationale_a"],
            "alternatives_considered": [], "confidence": 5,
            "date": f"{r['date_a']}T12:00:00Z", "author": AUTHOR,
        })
        redact_id = _id(r["decision_a"] + ":redact")
        event_store.write_event(LEDGER_PATH, redact_id, {
            "event": "redact", "id": redact_id,
            "redacts": a_id, "reason": r["reason_b"],
            "date": f"{r['date_b']}T12:00:00Z", "author": AUTHOR,
        })

    print(f"generated {len(PRISTINE)} pristine + {len(CHAINS)} chains + "
          f"{len(REDACTS)} redacts = {len(PRISTINE) + len(CHAINS) + len(REDACTS)} topics")


if __name__ == "__main__":
    main()
