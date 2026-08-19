#!/usr/bin/env bash
# cortex_fold_push.sh: re-fold the live Ledger into the Cortex read model and push it.
#
# Sprint K5 moved the Ledger's canonical home into the konjo-cortex clone itself
# ($KONJO_CORTEX_DIR/ledger/events) -- `konjo-decision decide`/`supersede`/`redact`
# already fold, commit, and push inline at write time (`lib/cortex_sync.py`), on
# every surface, cloud and phone included, not just wherever this session-end hook
# happens to fire. This hook is now a safety-net sweep, not the only path: it catches
# a push that failed inline and was left local, or a page edited outside the CLI.
# Same contract as always -- it can never block or error a session, every failure is
# swallowed.

set -u

KONJO_HOME="${KONJO_HOME:-$HOME/.konjo}"
CORTEX_DIR="${KONJO_CORTEX_DIR:-$KONJO_HOME/cortex}"

# Nothing to push into: no local konjo-cortex clone configured. Report once, don't block.
if [ ! -d "$CORTEX_DIR/.git" ]; then
  echo "cortex_fold_push: KONJO_CORTEX_DIR ($CORTEX_DIR) is not a git clone -- skipping fold-and-push. Set KONJO_CORTEX_DIR or clone konjo-cortex there." >&2
  exit 0
fi

# Nothing to fold from: no events written into this clone yet on this machine.
if [ ! -d "$CORTEX_DIR/ledger/events" ]; then
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
