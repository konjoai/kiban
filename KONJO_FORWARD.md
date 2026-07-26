---
decays: intent
verified-against: 5760da0
verified-date: 2026-07-26
---
# Konjo Forward

*This file did not exist on disk before the K1 sprint. It is originated here, verbatim
where quoted, from "Closing the Birth-Defect Gap" (the F0/F1-derived proposal that
grounds the K1-K4 gate sprints) — the source both that proposal and the K1 sprint brief
already cite as if it were an established doc. Rather than silently invent a false
history for it, that gap is recorded here once, plainly, and the doc proceeds as the
real thing from this point forward.*

## The one idea underneath

**The thing that governs the work lives outside the work.**

A gate that lives in the same commit as the code it checks is not a gate; it is the
author's own opinion of their own output, restated. Every mechanism in this framework —
the coverage floor, the one-way-door ledger, the prove gate's paired significance test,
`newonly`'s net-new differ — exists because the check has to be a separate artifact from
the thing being checked, not a line the author writes and then grades themselves on.

A claim is part of the work. So the thing that governs a claim also lives outside it. A
number in prose is governed by a measurement artifact under version control, or it is
not a number, it is a guess with a decimal point. *(This line grounds the Family A claim
gates — G-CLAIM, G-CLAIM-ARTIFACT — which are out of scope for K1; recorded here so the
ethos does not lag the gates it will eventually justify.)*

## The three pillars

1. **Forward-never-back.** A ratchet only tightens. Coverage floors rise, they do not
   fall; a gate promoted from advisory to blocking does not quietly demote back.
2. **Main-is-truth.** The committed state of `main` is the only state that counts. A
   claim about the code that main does not itself demonstrate is not yet true.
3. **Loop-runs-to-stop-condition.** Work runs until a stated, checkable condition fires
   — not until it feels done, not until the agent decides to stop.

All three govern **motion**. None of them, on their own, governs whether the artifact
they are moving is *truthful* — which is exactly why none of them caught lopi's F0/F1
findings: a wrong claim, an unreachable feature, and a gate that never fired all
ratcheted forward perfectly, because every ratchet in this framework measures the
present against a recorded baseline, and in all three cases the baseline was wrong on
the very first commit. See "The residual" below; it is not a fourth pillar, it is the
recognition that a derivative constraint cannot catch a wrong constant.

## What Konjo Forward rejects

- **Permissive unknowns.** A branch that cannot evaluate its condition and returns the
  passing value anyway. `verifier_fail_open` is the correct shape: an operator opting
  out, on the record, of a fail-closed default. A silent `return true` on the
  unconfigured/errored/unrecognised path is not an opt-out — it is a gate that was never
  actually there, wearing the shape of one. (`G-POLARITY`, K1.)

- **Tests as proof of wiring.** A test caller is not a production caller. Coverage
  proves code *can* run; it says nothing about whether the product ever runs it. A gate
  whose only caller is its own test — `run_verifier_pass` had exactly one, and it was a
  test asserting a bool was `true`, never a verdict was produced — has never fired, no
  matter how green every build has been. (`G-CAN-FAIL`, K1; `G-WIRED`/`G-REACH`, K2+.)

*(Later sprints add: unmeasured claims with no committed measurement artifact
(`G-CLAIM`), and a capability named in user-facing docs that no production entrypoint
reaches (`G-ADVERTISED`). Not added here — K1 is Family 0 only, and this doc should not
claim gates that do not exist yet.)*

## The residual — what this cannot do

Gates are specifications, and **a specification cannot validate itself.**

`G-POLARITY` finds a branch returning the permissive value on an unknown path; it cannot
judge a threshold — a branch returning the *restrictive* value set at the wrong level
passes it clean. `G-CAN-FAIL` requires a rejecting test to exist and pass for every
declared gate; it cannot require that the test exercise the hard input rather than the
easy one — someone satisfies it honestly, with no intent to game anything, on the
trivial case, and the whole stack goes green.

That is not a testing gap this framework closes by adding more gates. It is the reason
maker≠checker exists: the checker is a *different specification*, applied
independently to the same artifact, which is the only mechanism that catches a
specification being wrong rather than merely unmet. No amount of CI substitutes for
that, which is also why a real, adversarial review stage is sequenced where it is,
relative to the gates.

So the accurate claim for everything in this framework, stated once, plainly:

> Gates can guarantee nothing ships unverified. They cannot guarantee the verification
> was adequate.

An ethos that names its own blind spot is stronger than one that adds a fourth pillar
and implies coverage it does not have.
