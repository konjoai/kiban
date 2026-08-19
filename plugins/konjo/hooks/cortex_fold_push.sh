#!/usr/bin/env bash
# cortex_fold_push.sh: re-fold the live Ledger into the Cortex read model and push it.
#
# Replaces konjo-ship's old manual checklist line ("konjo-decision project --all-scopes
# --out-dir <cortex clone>, commit, push"). The real Ledger only ever exists on the
# machine that logged it -- this hook is meaningless (and a safe no-op) anywhere else,
# so it can only run where a human actually has both a real ~/.konjo/state/ledger and a
# local clone of konjo-cortex to push into. It can never block or error a session: every
# failure is swallowed, the same contract preamble_update.sh already established.

set -u

KONJO_HOME="${KONJO_HOME:-$HOME/.konjo}"
KIBAN_DIR="${KIBAN_DIR:-$KONJO_HOME/kiban}"
LEDGER_PATH="${KONJO_LEDGER_PATH:-$KONJO_HOME/state/ledger/decisions.jsonl}"
CORTEX_DIR="${KONJO_CORTEX_DIR:-$KONJO_HOME/cortex}"

# Nothing to fold from: no real Ledger on this machine. Not an error -- most sessions
# (including every cloud one) hit this branch, per Sprint K1/K2's own P-0 finding that
# the Ledger is laptop-only.
if [ ! -f "$LEDGER_PATH" ]; then
  exit 0
fi

# Nothing to push into: no local konjo-cortex clone configured. Report once, don't block.
if [ ! -d "$CORTEX_DIR/.git" ]; then
  echo "cortex_fold_push: KONJO_CORTEX_DIR ($CORTEX_DIR) is not a git clone -- skipping fold-and-push. Set KONJO_CORTEX_DIR or clone konjo-cortex there." >&2
  exit 0
fi

if ! command -v konjo-decision >/dev/null 2>&1; then
  exit 0
fi

konjo-decision project --all-scopes --out-dir "$CORTEX_DIR" || {
  echo "cortex_fold_push: konjo-decision project failed -- Cortex not re-folded, left as-is." >&2
  exit 0
}

if git -C "$CORTEX_DIR" diff --quiet && git -C "$CORTEX_DIR" diff --cached --quiet; then
  # Fold produced no changes (no new events since the last fold) -- nothing to commit.
  exit 0
fi

git -C "$CORTEX_DIR" add -A
git -C "$CORTEX_DIR" commit -qm "cortex: re-fold from Ledger ($(date -u +%Y-%m-%dT%H:%M:%SZ))" || {
  echo "cortex_fold_push: commit failed -- left uncommitted in $CORTEX_DIR for manual review." >&2
  exit 0
}
git -C "$CORTEX_DIR" push || {
  echo "cortex_fold_push: push failed -- commit is local in $CORTEX_DIR, push manually." >&2
  exit 0
}

exit 0
