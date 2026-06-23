#!/usr/bin/env bash
# Tests for lib/self_update.sh: throttle, skip bypass, failure-safety, and pinning.
# Pure bash so it can run anywhere git is present. Exits nonzero on the first failure.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SELF_UPDATE="$REPO_ROOT/lib/self_update.sh"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fail() { echo "FAIL: $1"; exit 1; }
pass() { echo "ok: $1"; }

git_quiet() { git -C "$1" "${@:2}" >/dev/null 2>&1; }

# Build a bare "remote" with two commits, and a clone one commit behind it.
REMOTE="$WORK/remote.git"
SEED="$WORK/seed"
git init --quiet --bare "$REMOTE"
git clone --quiet "$REMOTE" "$SEED"
git -C "$SEED" config user.email t@t && git -C "$SEED" config user.name t
echo one > "$SEED/f"; git_quiet "$SEED" add f; git_quiet "$SEED" commit -m one
git_quiet "$SEED" push origin HEAD:main

export KONJO_HOME="$WORK/home"
export KIBAN_DIR="$KONJO_HOME/kiban"
mkdir -p "$KONJO_HOME"
git clone --quiet "$REMOTE" "$KIBAN_DIR"
git -C "$KIBAN_DIR" config user.email t@t && git -C "$KIBAN_DIR" config user.name t
git -C "$KIBAN_DIR" branch --quiet --set-upstream-to=origin/main main 2>/dev/null || \
  git -C "$KIBAN_DIR" checkout --quiet -b main --track origin/main 2>/dev/null || true

# Advance the remote by one commit so the clone can fast-forward.
echo two > "$SEED/f"; git_quiet "$SEED" commit -am two; git_quiet "$SEED" push origin HEAD:main

before="$(git -C "$KIBAN_DIR" rev-parse HEAD)"

# 1. KONJO_SKIP_UPDATE bypasses everything (no fetch, no sentinel).
( cd "$WORK" && KONJO_SKIP_UPDATE=1 bash "$SELF_UPDATE" )
[ ! -f "$KONJO_HOME/.last_update_check" ] || fail "skip should not write sentinel"
[ "$(git -C "$KIBAN_DIR" rev-parse HEAD)" = "$before" ] || fail "skip should not move HEAD"
pass "KONJO_SKIP_UPDATE bypasses update"

# 2. Unpinned fast-forward: HEAD advances and the sentinel is written.
( cd "$WORK" && KONJO_UPDATE_INTERVAL=0 bash "$SELF_UPDATE" )
[ -f "$KONJO_HOME/.last_update_check" ] || fail "successful check should write sentinel"
[ "$(git -C "$KIBAN_DIR" rev-parse HEAD)" != "$before" ] || fail "ff should advance HEAD"
pass "unpinned fast-forward advances HEAD and stamps sentinel"

# 3. Throttle: with a fresh sentinel and the default interval, no update happens.
echo two > "$SEED/f-extra"; git_quiet "$SEED" add f-extra
git_quiet "$SEED" commit -m three; git_quiet "$SEED" push origin HEAD:main
head_now="$(git -C "$KIBAN_DIR" rev-parse HEAD)"
( cd "$WORK" && bash "$SELF_UPDATE" )  # default interval 3600s, sentinel just written
[ "$(git -C "$KIBAN_DIR" rev-parse HEAD)" = "$head_now" ] || fail "throttle should skip update"
pass "throttle sentinel respected"

# 4. Failure safety: a broken remote must not error or move HEAD.
rm -rf "$REMOTE"
( cd "$WORK" && KONJO_UPDATE_INTERVAL=0 bash "$SELF_UPDATE" ) || fail "must exit 0 on fetch failure"
pass "fetch failure is swallowed, no error"

# 5. Pinning: a .konjo/kiban.ref pins to the first commit instead of main.
#    Rebuild a working remote so fetch succeeds, then pin to the first commit's sha.
git init --quiet --bare "$REMOTE"
git_quiet "$SEED" push origin HEAD:main
first_sha="$(git -C "$SEED" rev-list --max-parents=0 HEAD)"
CONSUMER="$WORK/consumer"
mkdir -p "$CONSUMER/.konjo"
echo "$first_sha" > "$CONSUMER/.konjo/kiban.ref"
( cd "$CONSUMER" && KONJO_UPDATE_INTERVAL=0 bash "$SELF_UPDATE" )
[ "$(git -C "$KIBAN_DIR" rev-parse HEAD)" = "$first_sha" ] || fail "pin should checkout the pinned ref"
pass "pinned ref honored over main"

# 6. C2: unpin-then-update transition. The clone is now detached at first_sha (from the
#    pin above). With the pin removed, an unpinned update must reattach to the default
#    branch and fast-forward, not silently no-op forever in detached HEAD.
#    Make origin/HEAD resolve to the default branch, then advance the remote.
git -C "$KIBAN_DIR" remote set-head origin main >/dev/null 2>&1 || \
  git -C "$KIBAN_DIR" symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main >/dev/null 2>&1 || true
echo four > "$SEED/f"; git_quiet "$SEED" commit -am four; git_quiet "$SEED" push origin HEAD:main
detached_before="$(git -C "$KIBAN_DIR" rev-parse HEAD)"
git -C "$KIBAN_DIR" symbolic-ref --quiet HEAD >/dev/null 2>&1 && fail "precondition: HEAD should be detached after pin"
( cd "$WORK" && KONJO_UPDATE_INTERVAL=0 bash "$SELF_UPDATE" ) || fail "unpin update must exit 0"
git -C "$KIBAN_DIR" symbolic-ref --quiet HEAD >/dev/null 2>&1 || fail "unpin update should reattach HEAD to a branch"
[ "$(git -C "$KIBAN_DIR" rev-parse HEAD)" != "$detached_before" ] || fail "unpin update should fast-forward off the detached pin"
pass "unpin-then-update reattaches and fast-forwards"

echo "ALL self_update tests passed"
