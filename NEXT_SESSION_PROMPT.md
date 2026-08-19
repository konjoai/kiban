# kiban is dormant. One habit is the only open item.

**kiban is feature-complete for this line of work as of v1.19.0.** Sprint K4 shipped the
last substantive item (real data, the Ledger folding for real, KT-1's threshold shown
unreachable). This closeout (v1.19.1) is maintenance only: a quoting defect in the
one-way-door hook's write path, a projection-ordering decision, and two pre-existing test
failures fixed at the root. Nothing here reopens a settled question.

**The only open item is P-0b.** Events with `decided_at > 2026-08-19T15:16:52Z`. Check it
mechanically:

```bash
python3 - <<'PY'
from ledger.engine import Ledger
CLOSE = "2026-08-19T15:16:52Z"
f = Ledger()._fold()
p0b = [d for d in f if d.decided_at > CLOSE]
print(f"P-0b events since K4 close: {len(p0b)}")
for d in p0b:
    print(f"  {d.decided_at}  {d.scope:12s}  {d.decision[:60]}")
PY
```

**P-0b is a habit, not a task. No session can advance it.** It counts real decisions
captured at the time they were made, on the machine that holds the Ledger. A session
cannot manufacture that -- transcribing history is P-0a (already done, and not to be
repeated), and fabricating events to move the number is explicitly a non-goal. If you are
reading this in a session, the only correct action on P-0b is to check the count and
report it honestly, not to try to close it.

**The trigger to reopen kiban: P-0b reaches 15 events across at least 2 scopes.** At that
point the KT-1 re-run becomes worth attempting, with a properly powered corpus and a
revised threshold -- K4 showed the original `>= 20` point absolute bar was unreachable by
construction (it requires a retriever scoring above 100% against K1's own keyword
baseline). Changing the threshold is its own decision and is not made here; it becomes
worth making once the corpus exists to test it against.

**Until then, kiban gets bug fixes only.** No new gates, skills, or contract sections. If
a session lands here and P-0b has not reached the trigger, the correct output is: check
the number, report it, stop. That is not a failure to find work -- it is the tooling
doing exactly what it was built to do.
