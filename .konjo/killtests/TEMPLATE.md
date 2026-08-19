# KT-N -- <the one-sentence question this test answers>

**Template, Sprint K3.** Copy this file to `.konjo/killtests/<Category>/KT-N.md`
(next unused number across the whole `.konjo/killtests/` tree, not per
category -- `KT-7` and `KT-8` both live under `CortexSkis/` but are numbered
globally) and fill it in. Delete this comment block once filled in; keep
every section below, even the ones that end up short. Two prior instances of
skipping a section here are recorded and named, not hypothetical:
`.konjo/killtests/CortexSkis/KT-3.md`'s original run treated a `[]` result
from `ListConnectors` as proof of absence with no positive control, and
stayed wrong across two sprints; the same file's Sprint K3 disposition (an
otherwise-solid live-routine result) skipped pre-registration and had to be
recorded with an honest asterisk instead of a scored PASS. Both are exactly
what the two required sections below exist to stop happening a third time.

## Pre-registration (write this section BEFORE running anything)

State the exact method, the exact questions or fixture edits, and the exact
expected result -- **committed to the repo before the test runs**, not
written up afterward from memory of what happened. `.konjo/killtests/CortexSkis/KT-7.md`
and `KT-8.md` are the worked examples: both were committed in their own
"pre-registration" commit, separate from the later "verdict" commit, so the
diff itself proves the questions were not adjusted after seeing the answer.

If this step is skipped -- a live run happens first, and the writeup comes
after -- **say so explicitly in the verdict, with an honest asterisk, and do
not describe the result as a scored PASS/FAIL.** `KT-3`'s Sprint K3
disposition is the pattern: real evidence, genuinely resolves the question,
still flagged as unregistered rather than dressed up as a graded run.

## Absence-of-evidence check

Required whenever this test's verdict rests on a tool returning nothing, or
on treating some component as belonging to a category (a name, a UI
listing, an API response shape). Answer explicitly, do not skip because it
"obviously" doesn't apply:

1. **What tool or assumption is the negative resting on?** Name it exactly
   (e.g. "`ListConnectors` filtered on `github` returned `[]`", or "the
   claude.ai UI element is labeled 'connector'").
2. **What was it expected to enumerate or correctly categorize, and is that
   documented anywhere, or assumed?** If assumed, say so -- an assumption is
   not a fact just because it went unquestioned across a prior sprint.
   `Routine-Reach-1`/`Skis-Contract-1` Finding 1 is the exact failure this
   question exists to catch: a `[]` result and a UI label were both taken at
   face value, and the resulting misclassification survived two sprints of
   review because nobody asked this question of either one.
3. **Flag the reading as unconfirmed until the positive-control step below
   passes.** A verdict that rests on an unconfirmed negative is provisional,
   not final, no matter how confidently it reads.

## Positive control

Required alongside the absence-of-evidence check, not instead of it. A
negative finding is not trustworthy until you have shown the same mechanism
*can* produce a positive at all, on the same data, by the same method.

Worked example: `Skis-Contract-1` Finding 2. The gate-tiering decision's
Cortex entry reported no predecessor -- on its own, a bare "None" cannot
distinguish "no chain exists" from "the chain renderer is broken and never
shows one." The positive control was checking whether *any* chain renders
anywhere on the same page; three genuine chains were found elsewhere in the
same 33-decision corpus, which is what makes the gate-tiering entry's
"None" trustworthy rather than merely unexamined.

State here: what positive result would prove the mechanism works, and did
you actually go find or produce one on real data (not a synthetic fixture
built to pass) before trusting the negative this test is otherwise about to
report.

## Method

The actual steps taken, including tool calls, commands, and file paths --
enough that a future session could redo this test without re-deriving the
approach from scratch.

## Stop rule

State, before running anything, what would make this test's own status
(e.g. a session reaching `IDLE`, a command exiting 0) insufficient to call a
verdict -- and what has to be independently verified instead. `KT-3`'s
original stop rule ("a session finishing IDLE proves it produced an
answer, not a correct one") is the pattern; `KT-7`/`KT-8`'s deposit-an-artifact
method (below) is one way to satisfy a stop rule that a session-status field
alone cannot.

## Grading anything that runs outside this session

Standard method, not this test's invention: if the thing under test is a
spawned session, a fired routine, or anything else whose reasoning this
session cannot directly observe, **do not grade it from a status field**
(`IDLE`, exit code, "task complete"). No tool available to a kiban session
can retrieve another session's verbatim transcript (`ListAgents`,
`SendMessage`, `list_sessions`, `WebFetch` were all tried and failed for
this exact purpose in `KT-3`'s original run; `list_events` has also been
checked and is not available). Instead:

1. Have the spawned session **commit its answer to a branch** in a repo
   this session can also read (a markdown file, a fixed format, one commit).
2. Grade by **reading that commit back through the GitHub API** (or
   equivalent), independently of anything the spawned session reported
   about itself.
3. **Contamination guard:** pick questions whose answers do not exist
   anywhere the spawned session might have prior access to. In this repo
   specifically, `evals/fixtures/ledger/` carries the K1 fixture corpus's
   ids and decision text verbatim -- a session with `kiban` checked out can
   answer a question about that content without ever reading the thing
   actually under test. `KT-7` used `projected-at` (a value the fold
   generates, present nowhere in `kiban`) as the discriminating question for
   exactly this reason -- prefer a question with the same property over one
   that merely sounds specific.

## Verdict (appended after the run, in its own commit)

PASS / FAIL / BLOCKED / INVALID PREMISE -- pick the one that actually
describes what happened, don't force it into PASS/FAIL if the premise
itself is what broke (`KT-3`'s Sprint K3 disposition is the precedent for
INVALID PREMISE). State the evidence, grade it against the pre-registered
expectation exactly, and say plainly if either the absence-of-evidence
check or the positive control did not get done -- an unconfirmed reading
recorded honestly is worth more than a confident one that turns out wrong
two sprints later.
