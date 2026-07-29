---
decays: reference
verified-against: 05c044f
verified-date: 2026-07-29
---

# Sprint brief template

No file in kiban defined this shape before Phase 13 ("The Authoring Gate"), even though
sprint briefs following this format already existed (this project's own K1 brief, and
Phase 13's own). Originated here rather than silently assumed, the same honesty move
`KONJO_FORWARD.md` made when it turned out to be cited but absent (see `LEDGER.md`,
`KONJO-Forward-Origination-1`): the shape was already real, only its existence as a
reusable template on disk was missing.

Fill in every bracketed field. `[none]` is a valid answer for TRUST BOUNDARIES and ABUSE
CASES -- state it rather than omitting the field.

```markdown
# <project> <sprint id> (<version>) -- <sprint name>

## Motivation

[Why this sprint, in a paragraph or two. What breaks if it doesn't ship.]

## Baseline evidence

[A table of claims verified against a clean clone, with the evidence for each. Re-run
and correct this table if the sprint's own kill-tests find drift from what was assumed
when the brief was written.]

## Pre-flight kill-tests (hard gates)

[Each kill-test: Question, Procedure, Pass/Fail criteria, On-fail instructions. A failed
kill-test is a complete outcome, not a blocker to route around.]

## Phases

Each phase merges independently. A red phase is fixed or reverted, never carried forward.

### Phase N -- <name>

1. [Concrete step.]
2. ...

**TRUST BOUNDARIES**: [Which of the eight classes this phase's changes cross --
authn/authz, secret lifecycle, deserialization, subprocess/exec, path handling, network
ingress, SQL construction, resource limits -- or `none`.]

**ABUSE CASES**: [One line per boundary named above: the abuse case the phase's
mitigation defeats. `none` if TRUST BOUNDARIES is `none`.]

**Verify**: [What proves this phase is done -- a command, a fixture pair, both.]

**Non-goal**: [What this phase deliberately does not do, so a later reader doesn't
mistake an intentional boundary for an oversight.]

## Non-goals

[Sprint-wide, not phase-wide -- things explicitly out of scope for the whole sprint.]

## Post-flight deliverables

[CHANGELOG.md entries, LEDGER.md entries, NEXT_SESSION_PROMPT.md update, version bump --
whatever this project's own closing convention requires.]

## Stop rule

[What ships if a kill-test fails partway through. Name which phases are independently
justified regardless of the others' outcome.]
```

## Where TRUST BOUNDARIES / ABUSE CASES come from

Phase 13's `konjo-threat`/`gate_threat_model` (`lib/threat.py`,
`packages/konjo-gates-py/.../cli.py`) is the mechanism these two fields feed: naming the
boundaries and abuse cases at brief time is the same content `konjo-threat record`
demands at brief time for an individual change, one level up (a whole phase's planned
work, not one diff). Writing them in the brief does not substitute for running
`konjo-threat record` before the code lands -- `gate_threat_model` still checks the
commit trailer, not the brief text.
