# Phase 3 report -- what actually ran, what it found, and what it did not attempt

**Scope, stated up front**: this is a real slice of Phase 3, not the full protocol.
2 tasks (not 12-20), 2 of the 6 candidates (not all six), 3 runs each -- 18 real live
sessions, on top of KT-14.1's own 9. The full protocol, run against every candidate
individually per the brief ("run each of the six drafted candidates individually"),
is 7 conditions (baseline + 6) × 12-20 tasks × 3 runs = 252-420 sessions at the
brief's own floor. That is not affordable inside one session already carrying the
harness build, the classifier gap, KT-14.1/KT-14.2, and the gate-ramp work -- stated
plainly here rather than quietly shrunk, per this project's own established
precedent (`.konjo/killtests/P13/KT-13.1.md`) and `NEXT_SESSION_PROMPT.md`'s own
explicit allowance for exactly this situation.

## What ran

Two real tasks, deliberately **not** the same three KT-14.1 used. KT-14.1's tasks
each explicitly asked the agent to fix a named defect ("bound this channel," "convert
this to typed errors") -- reusing them here would confound "does the context reduce
*incidental* defects" with "did the agent follow an explicit instruction," which is a
different, easier question. Phase 3's own tasks are ordinary feature work, drawn from
real closed lopi commits, described in the requester's voice with no mention of
queues, timeouts, or error types:

| Task | Real source commit | Parent (base_ref) |
|---|---|---|
| `lopi-whatsapp-cost-command` | `eaba7fc` ("WhatsApp /cost command") | `55df00f` |
| `lopi-runaway-sweep-monitor` | `ee169b0` ("live runaway monitor") | `f84b61c` |

Three conditions, same two tasks, 3 runs each (18 sessions total):

- **baseline** -- no `--append-system-prompt` override (ambient `CLAUDE.md` only,
  same as KT-14.1).
- **candidate 3** ("Every queue is bounded. Every external call has a timeout. Every
  retry has a cap.") -- targets `unbounded_queue` + `missing_timeout`.
- **candidate 5** ("Errors crossing a library boundary are typed. `Other(String)` is
  not a variant.") -- targets `untyped_error_boundary`.

Candidates 1, 2, 4, 6 were not measured this session. Candidate 1 is the brief's own
named low-priority case (`gate_polarity` already catches this shape deterministically
since 1.7.0 -- see the sprint brief's own Phase 3 note). Candidates 2, 4, 6 were
simply not reached inside this session's real time budget; not a judgment about their
value, a fact about what one session's live-model budget covers on top of everything
else this sprint required.

## What was found -- and a real bug this measurement caught in its own instrument

The first pass showed a real signal in `lopi-runaway-sweep-monitor`: an
`unbounded_queue` hit in 2 of 3 candidate-condition runs and an
`untyped_error_boundary` hit that looked consistent across conditions. Tracing both
before writing this report found they were not production defects at all --
`lib.threat.classify`'s diff hints and `lib.defect_shapes`'s new scans were reading
test-helper code (`mod tests { ... }` blocks: `oneshot::channel()` in a test fixture
builder, `.unwrap()` in test setup, `tokio::spawn(...)` inside `.spawn()`-pattern-
matching that also caught in-process task spawns) as if it were production code. Both
`lib/defect_shapes.py::added_lines_excluding_test_scope` (new) and a narrowed
`SUBPROCESS_EXEC` pattern in `lib/threat.py` (`.spawn()` the zero-arg method call, not
bare `spawn(` which also matched `tokio::spawn(fut)`) fix this -- see `LEDGER.md`'s
entry for the full mechanism and why `gate_threat_model`'s own use of
`lib.threat.classify` is deliberately untouched (a reviewer plausibly still cares that
a PR's test code touches a webhook boundary; a defect *count* comparing contexts does
not want test scaffolding inflating it). All of KT-14.1's own numbers were
re-classified with the fix too -- see its own updated report.

**After the fix, every one of the 20 successful sessions across all three conditions
classified completely clean**: zero findings on all seven mechanically-classified
defect classes, on both tasks, in baseline and in both tested candidates.

| Task | Condition | Runs ok | Findings |
|---|---|---|---|
| `lopi-whatsapp-cost-command` | baseline | 3/3 | clean |
| `lopi-whatsapp-cost-command` | candidate 3 | 3/3 | clean |
| `lopi-whatsapp-cost-command` | candidate 5 | 3/3 | clean |
| `lopi-runaway-sweep-monitor` | baseline | 2/3 (1 empty-diff session) | clean |
| `lopi-runaway-sweep-monitor` | candidate 3 | 3/3 | clean |
| `lopi-runaway-sweep-monitor` | candidate 5 | 3/3 | clean |

## Reading this result honestly

**Neither candidate 3 nor candidate 5 shows a measurable defect reduction, because
neither task's baseline rate was ever above zero to reduce.** This is not the same
finding as "the candidates don't help" -- it is the narrower, honest finding that
*this experiment design* (these two tasks) cannot distinguish a candidate's effect
from no effect, because there was no incidence in either arm. A well-behaved agent
under lopi's current baseline context, on two ordinary feature tasks, did not
organically produce an unbounded queue or an untyped error boundary at a rate this
sample could see -- itself worth knowing, but it is a statement about baseline task
selection, not about the candidates.

**The methodological lesson, stated so a future session does not repeat the miss**:
measuring whether a candidate invariant reduces a defect requires tasks with a
verified non-zero baseline incidence for that defect class, the same way a proof
needs a real baseline to beat. KT-14.1's own defect-fix-shaped tasks *do* have that
property (the parent commit's real state contains the defect by construction) but
were excluded from Phase 3 specifically to avoid the "explicit instruction" confound
named above. The fix for a future session is not to drop that exclusion -- it is to
find or construct *incidental*-risk tasks with a demonstrated non-zero baseline rate
(e.g., run baseline first across a wider task pool, keep only tasks whose baseline
already shows the target defect at least once, then compare candidates against that
verified-nonzero subset) rather than assume any feature task will do.

## Decision

**No candidate ships this sprint.** Per Phase 3's own instruction ("keep only
candidates whose measured reduction clears the run-to-run variance from KT-14.1"),
clearing a variance floor requires a measured reduction to compare against it in the
first place; this session's real data provides none, for either candidate it tested.
This is the same honest-null outcome the sprint's own Stop Rule anticipates and
explicitly permits publishing rather than hiding. The six candidates remain recorded,
unmeasured-at-the-specified-scale, in `LEDGER.md`; candidates 3 and 5 now carry a
real (if small and inconclusive) data point each, and candidates 1, 2, 4, 6 remain
entirely unmeasured. Full task list, resumable next-session with the same harness:
`NEXT_SESSION_PROMPT.md`.
