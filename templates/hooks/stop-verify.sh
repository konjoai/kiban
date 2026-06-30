#!/usr/bin/env bash
# Konjo Stop hook (template): run the repo's verify_cmd when the agent ends a turn, so a
# long autonomous run cannot end on a red state silently. This is the deterministic version
# of "verify with a background agent when done."
#
# Opt-in: wire it into .claude/settings.json under hooks.Stop (see settings.snippet.json).
# It no-ops when the repo declares no verify_cmd, so dropping it in is always safe.
#
# Exit codes (Claude Code Stop-hook contract): 0 lets the turn end; 2 blocks the stop and
# feeds stderr back to the agent. A failed verify blocks, so the turn does not end red.

set -u

cat >/dev/null 2>&1 || true   # drain the hook payload on stdin; we do not need it

PROFILE="${KONJO_PROFILE:-.konjo/profile.yml}"
[ -f "$PROFILE" ] || exit 0

VCMD="$(konjo-profile-get verify_cmd "$PROFILE" 2>/dev/null)"
[ -n "$VCMD" ] || exit 0   # no verify_cmd declared (or a TODO placeholder): nothing to run

echo "konjo stop-hook: verifying with: $VCMD" >&2
if eval "$VCMD" >&2; then
  exit 0
fi
echo "konjo stop-hook: verify_cmd failed; not ending on a red state. Fix it and retry." >&2
exit 2
