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
#   - Unpinned: fetch, then advance only to the newest signed release tag reachable
#     from the tracking branch (never to the raw, unsigned branch tip), via
#     merge --ff-only. Fast-forward only; never auto-merge a divergence. If a prior
#     pinned checkout left HEAD detached and the pin is now gone, reattach to the
#     default branch first so @{u} resolves again (C2).
#   - Every tag this script would apply -- pinned or the resolved unpinned target --
#     is verified against security/allowed_signers (git verify-tag, ssh signing)
#     *before* it is merged or checked out. Verification reads that file as it stands
#     in the working tree pre-update, never from the fetched ref, so a compromised
#     push can't rewrite its own trust anchor and pass. An unsigned or invalidly
#     signed unpinned target is a silent no-op, exactly like a network failure. A
#     pinned ref that fails verification is refused rather than applied blindly.
#   - A verification failure (as opposed to a network/fetch failure) is appended to
#     $KONJO_HOME/security.log so a repeated failure is discoverable, not invisible
#     forever. See konjo_security_log / konjo_verify_tag below.
#   - Fetch only the tracking remote, not every remote (C4).
#   - Update the sentinel only after a successful check.

set -u

KONJO_HOME="${KONJO_HOME:-$HOME/.konjo}"
KIBAN_DIR="${KIBAN_DIR:-$KONJO_HOME/kiban}"
SENTINEL="$KONJO_HOME/.last_update_check"
SECURITY_LOG="$KONJO_HOME/security.log"
INTERVAL="${KONJO_UPDATE_INTERVAL:-3600}"

# Appends one line to the security log. Best-effort: a logging failure must never
# affect the update outcome. $1=event $2=ref $3=reason $4=detail (git's own message).
konjo_security_log() {
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" || ts="unknown-time"
  {
    printf '%s event=%s ref=%s reason=%s detail=%s\n' \
      "$ts" "$1" "$2" "$3" "$(printf '%s' "${4:-}" | tr '\n\r' '  ')"
  } >> "$SECURITY_LOG" 2>/dev/null || true
}

# Verifies tag $1 against security/allowed_signers as it stands in the working tree
# right now (i.e. before any merge/checkout this run might apply -- see file header).
# Returns 0 on a good signature. On failure, sets KONJO_VERIFY_REASON to one of:
#   unsigned          - the ref resolves to a real object but there is no tag
#                        signature to check: a lightweight tag, an annotated-but-
#                        unsigned tag, or (git's own ref resolution finding it
#                        unambiguously first) a branch name or bare sha.
#   invalid_signature - signed, but not by a key in allowed_signers (wrong key,
#                        tampered content). This is the strongest tamper signal.
#   unresolvable_ref  - the name doesn't resolve to anything at all (typo, deleted
#                        tag).
#   unverifiable      - anything else (e.g. verification tooling unavailable).
konjo_verify_tag() {
  local tag="$1" out rc allowed_signers
  allowed_signers="$KIBAN_DIR/security/allowed_signers"
  # Force the real ssh-keygen for verification regardless of what a user's own
  # gpg.ssh.program may be set to (e.g. a custom commit-signing wrapper) -- that
  # setting is about the user's own signing identity, not kiban's trust anchor.
  out="$(git -C "$KIBAN_DIR" -c "gpg.ssh.allowedSignersFile=$allowed_signers" \
    -c gpg.ssh.program=ssh-keygen verify-tag "$tag" 2>&1)"
  rc=$?
  if [ "$rc" -eq 0 ]; then
    return 0
  fi
  case "$out" in
    *"cannot verify a non-tag object"*|*"no signature found"*)
      KONJO_VERIFY_REASON="unsigned" ;;
    *"No principal matched"*|*"BAD"*|*"bad signature"*)
      KONJO_VERIFY_REASON="invalid_signature" ;;
    *"not a valid"*|*"unknown revision"*|*"fatal:"*|*"not found"*)
      KONJO_VERIFY_REASON="unresolvable_ref" ;;
    *)
      KONJO_VERIFY_REASON="unverifiable" ;;
  esac
  KONJO_VERIFY_DETAIL="$out"
  return 1
}

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

  # The tracking remote for the current branch, or origin as the fallback. Fetching
  # just this remote is lighter than --all (C4).
  local remote
  remote="$(git -C "$KIBAN_DIR" config "branch.$(git -C "$KIBAN_DIR" \
    symbolic-ref --quiet --short HEAD 2>/dev/null).remote" 2>/dev/null)"
  [ -n "$remote" ] || remote="origin"

  # All git work is best-effort. Any failure returns 0 without touching the sentinel,
  # so the next invocation retries. --tags: signed release tags must be fetched from
  # this same single remote too, or there is nothing to verify against.
  if ! git -C "$KIBAN_DIR" fetch --quiet --tags "$remote" 2>/dev/null; then
    return 0
  fi

  if [ -n "$pin" ]; then
    # A pin is expected to name a signed tag. Refuse rather than apply blindly if it
    # doesn't verify -- this is deliberately stricter than the unpinned path's silent
    # skip: a pin is an explicit operator choice, so a pin that can no longer be
    # honored is worth a security-log entry every time, not just on first discovery.
    if konjo_verify_tag "$pin"; then
      if ! git -C "$KIBAN_DIR" checkout --quiet "$pin" 2>/dev/null; then
        return 0
      fi
    else
      konjo_security_log "pin_refused" "$pin" "$KONJO_VERIFY_REASON" "${KONJO_VERIFY_DETAIL:-}"
      return 0
    fi
  else
    # C2: a previous pinned checkout leaves HEAD detached. In that state @{u} does not
    # resolve, so the ff-only merge would silently no-op forever. When unpinned and
    # detached, reattach to the remote's default branch before merging.
    if ! git -C "$KIBAN_DIR" symbolic-ref --quiet HEAD >/dev/null 2>&1; then
      local default_ref default_branch
      default_ref="$(git -C "$KIBAN_DIR" symbolic-ref --quiet \
        "refs/remotes/$remote/HEAD" 2>/dev/null)"
      default_branch="${default_ref##*/}"
      [ -n "$default_branch" ] || default_branch="main"
      if ! git -C "$KIBAN_DIR" checkout --quiet "$default_branch" 2>/dev/null; then
        return 0
      fi
    fi

    # The update unit is the newest signed release tag reachable from the tracking
    # branch, not the raw branch tip: verifying every commit on main would mean
    # signing every commit, which is explicitly out of scope. This is a narrower
    # target than plain '@{u}', not a wider one -- ff-only still guards it, and if
    # no tag is reachable yet (e.g. between this feature landing and the first
    # signed release) the update is a no-op, same as any other failure-safe skip.
    local upstream target_tag
    upstream="$(git -C "$KIBAN_DIR" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)"
    if [ -z "$upstream" ]; then
      return 0
    fi
    target_tag="$(git -C "$KIBAN_DIR" tag --list --merged "$upstream" --sort=-v:refname 2>/dev/null | head -n1)"
    if [ -z "$target_tag" ]; then
      return 0
    fi

    if konjo_verify_tag "$target_tag"; then
      if ! git -C "$KIBAN_DIR" merge --ff-only --quiet "$target_tag" 2>/dev/null; then
        # Divergence, or the tag isn't a descendant of HEAD. Do not force.
        return 0
      fi
    else
      konjo_security_log "update_skipped" "$target_tag" "$KONJO_VERIFY_REASON" "${KONJO_VERIFY_DETAIL:-}"
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
