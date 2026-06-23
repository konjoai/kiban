#!/usr/bin/env bash
# self_update.sh: throttled, failure-safe self-update for the kiban clone.
#
# Every skill preamble sources or calls this. It must be cheap, silent, and incapable
# of blocking or erroring a session. A network or git failure is swallowed; the only
# visible effect of success is a fast-forwarded clone.
#
# Behavior:
#   - Bypass entirely when KONJO_SKIP_UPDATE=1.
#   - Throttle on ~/.konjo/.last_update_check; skip if checked within the interval.
#     Interval default 3600s, override with KONJO_UPDATE_INTERVAL.
#   - Pinning: if .konjo/kiban.ref exists in the cwd repo OR KIBAN_REF is set, check
#     out that ref instead of pulling main.
#   - Unpinned: fetch then merge --ff-only. Fast-forward only; never auto-merge a
#     divergence.
#   - Update the sentinel only after a successful check.

set -u

KONJO_HOME="${KONJO_HOME:-$HOME/.konjo}"
KIBAN_DIR="${KIBAN_DIR:-$KONJO_HOME/kiban}"
SENTINEL="$KONJO_HOME/.last_update_check"
INTERVAL="${KONJO_UPDATE_INTERVAL:-3600}"

konjo_self_update() {
  # Hard bypass.
  if [ "${KONJO_SKIP_UPDATE:-0}" = "1" ]; then
    return 0
  fi

  # Nothing to update if the clone is missing; stay silent.
  if [ ! -d "$KIBAN_DIR/.git" ]; then
    return 0
  fi

  mkdir -p "$KONJO_HOME" 2>/dev/null || return 0

  # Throttle check.
  if [ -f "$SENTINEL" ]; then
    local now last age
    now="$(date +%s 2>/dev/null)" || return 0
    last="$(cat "$SENTINEL" 2>/dev/null || echo 0)"
    case "$last" in
      ''|*[!0-9]*) last=0 ;;
    esac
    age=$(( now - last ))
    if [ "$age" -lt "$INTERVAL" ]; then
      return 0
    fi
  fi

  # Resolve a pinned ref, if any. A per-repo pin wins over the env pin.
  local pin=""
  if [ -f ".konjo/kiban.ref" ]; then
    pin="$(tr -d ' \t\n\r' < .konjo/kiban.ref 2>/dev/null)"
  elif [ -n "${KIBAN_REF:-}" ]; then
    pin="$KIBAN_REF"
  fi

  # All git work is best-effort. Any failure returns 0 without touching the sentinel,
  # so the next invocation retries.
  if ! git -C "$KIBAN_DIR" fetch --quiet --all 2>/dev/null; then
    return 0
  fi

  if [ -n "$pin" ]; then
    if ! git -C "$KIBAN_DIR" checkout --quiet "$pin" 2>/dev/null; then
      return 0
    fi
  else
    if ! git -C "$KIBAN_DIR" merge --ff-only --quiet '@{u}' 2>/dev/null; then
      # Divergence or no upstream. Do not force; leave the clone as-is.
      return 0
    fi
  fi

  # Success: stamp the sentinel.
  date +%s > "$SENTINEL" 2>/dev/null || true
  return 0
}

# When executed directly (not sourced), run the update.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  konjo_self_update
fi
