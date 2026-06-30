#!/usr/bin/env bash
# Konjo PostToolUse format hook (template): run the repo's formatter after an edit so a
# formatting slip never reaches CI and the format gate stays quiet. Low-risk, high-convenience.
#
# Opt-in: wire it into .claude/settings.json under hooks.PostToolUse, matched to the edit
# tools (Edit, Write, MultiEdit). It no-ops when the repo declares no format_cmd.
#
# Formatting is convenience, never a blocker: this hook always exits 0, even if the formatter
# errors. It must not break a turn over a cosmetic step.

set -u

cat >/dev/null 2>&1 || true   # drain the hook payload on stdin; we do not need it

PROFILE="${KONJO_PROFILE:-.konjo/profile.yml}"
[ -f "$PROFILE" ] || exit 0

FCMD="$(konjo-profile-get format_cmd "$PROFILE" 2>/dev/null)"
[ -n "$FCMD" ] || exit 0   # no format_cmd declared (or a TODO placeholder): nothing to run

eval "$FCMD" >&2 2>&1 || true
exit 0
