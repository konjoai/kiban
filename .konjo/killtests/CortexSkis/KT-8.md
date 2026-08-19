# KT-8 -- Does the skis-contract drift gate actually block?

**Status at pre-registration time: NOT YET RUN.** Fixture edits and expected
gate output are written and committed *before* either leg runs, per Finding
3's own instruction: KT-3's honest asterisk this same sprint (not
pre-registered) exists precisely because that discipline was skipped once
already this cycle. Numbered 8, not 7 -- `KT-7` already used that name for
the `source_url` reachability test.

## What this tests

`Skis-Contract-1`'s Finding 3: a gate introduced in a form that cannot
reject anything has shipped at least three times before (`mutation-hunt`,
`gate_claude_contract`, a self-graded checklist line) across different
repos and sprints. Phase 1's `bin/konjo-skis-check`
(`lib/skis_contract.py`, `konjo-skis/CONTRACT.yml`) is wired BLOCKING into
`.github/workflows/ci.yml` on the strength of that same finding. This kill
test is the demonstration that it is not the fourth instance of the
pattern: a gate that has never been shown to actually fail on real drift,
whatever tier it claims.

Two legs, both must pass or the manifest does not ship (this file's own
stop rule, restated at the end).

## Leg 1: a correctness edit to a must-match section must FAIL, naming the section and both paths

**Fixture edit (pre-registered):** in `plugins/konjo/skills/recall/SKILL.md`
only, inside the `<!-- skis-contract:recall.chain-reasoning -->` block,
change:

> "Only walk the chain or mention a superseded predecessor when the question
> is explicitly about history"

to:

> "Never mention a superseded predecessor, even when the question is
> explicitly about history"

This is a real correctness regression, not a cosmetic edit: it silently
drops the plugin variant's ability to answer a "what did we used to do"
question, while `konjo-skis/recall/SKILL.md` keeps the correct rule --
exactly the shape of drift a consistency requirement with no gate cannot
catch (`konjo-skis/README.md`'s own stated risk, restated in
`Skis-Contract-1`).

**Expected gate output:** `python3 bin/konjo-skis-check` exits 1, printing a
`content_mismatch` line naming section `recall.chain-reasoning` and both
`plugins/konjo/skills/recall/SKILL.md` and `konjo-skis/recall/SKILL.md`.

**Then:** apply the identical edit to `konjo-skis/recall/SKILL.md`'s
`recall.chain-reasoning` block (both files now say the same, regressed,
thing -- this step only proves the gate re-clears on a real sync, not that
the regression is desirable; the regression is reverted afterward in both
files, it does not ship).

**Expected gate output after the sync:** exits 0, summary line reports 2
pairs / 6 must-match / 1 divergent, unchanged from the clean baseline.

## Leg 2: an edit inside a declared-divergent section must stay quiet

**Fixture edit (pre-registered):** in
`plugins/konjo/skills/recall/SKILL.md` only, inside the
`<!-- skis-contract:recall.read-path -->` block, change the trailing
sentence from "no projection step, no staleness window" to "no projection
step, no staleness window, and no supersede-chain rendering of its own --
the CLI prints raw matches, chain reasoning happens in the reader's head,
not in the tool" -- a real, substantive addition to the divergent section,
not a whitespace no-op, so a gate that merely ignores whitespace inside
divergent sections cannot be mistaken for one that correctly treats
declared divergence as declared.

**Expected gate output:** `python3 bin/konjo-skis-check` exits 0, unchanged
summary, no drift lines at all -- the edit is inside a section declared
divergent in `konjo-skis/CONTRACT.yml`, and divergent-section content is
never compared.

## Stop rule

A gate that passes on drift is not a gate, and a gate that blocks
legitimate divergence gets disabled within two sprints, leaving neither the
gate nor the two-file discipline (`konjo-skis/README.md`'s own point). Both
legs must pass exactly as pre-registered above or the manifest does not
ship this sprint -- reverted, not weakened, if either fails.
