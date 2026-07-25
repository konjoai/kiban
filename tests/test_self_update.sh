#!/usr/bin/env bash
# Tests for lib/self_update.sh: throttle, skip bypass, failure-safety, pinning, and
# signature verification (valid-signed applies, unsigned/invalid-signed no-op, pin
# refusal, security-log discoverability). Pure bash + git + ssh-keygen so it can run
# anywhere those are present. Exits nonzero on the first failure.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SELF_UPDATE="$REPO_ROOT/lib/self_update.sh"
SSHKEYGEN="$(command -v ssh-keygen)"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fail() { echo "FAIL: $1"; exit 1; }
pass() { echo "ok: $1"; }

git_quiet() { git -C "$1" "${@:2}" >/dev/null 2>&1; }

# Force real ssh-keygen for signing/verification in these tests, regardless of
# whatever gpg.ssh.program a developer's own global git config points at.
sign_tag() {
  # $1=repo $2=tag $3=sha $4=keyfile $5=principal-email
  git -C "$1" -c gpg.format=ssh -c gpg.ssh.program="$SSHKEYGEN" \
    -c user.signingkey="$4" -c user.email="$5" -c user.name=tagger \
    tag -s -a "$2" -m "$2" "$3"
}

log_has() {
  # $1=log file $2=grep pattern
  grep -q -- "$2" "$1" 2>/dev/null
}

# --- Key material: one trusted (matches allowed_signers) and one attacker key. ---
ssh-keygen -q -t ed25519 -N "" -C "trusted" -f "$WORK/trusted_key"
ssh-keygen -q -t ed25519 -N "" -C "attacker" -f "$WORK/attacker_key"
TRUSTED_PUB="$(awk '{print $1" "$2}' "$WORK/trusted_key.pub")"

# Build a bare "remote" with an initial commit that already carries the trust anchor
# (security/allowed_signers), and a clone one commit behind it.
REMOTE="$WORK/remote.git"
SEED="$WORK/seed"
git init --quiet --bare "$REMOTE"
git -C "$REMOTE" symbolic-ref HEAD refs/heads/main
git init --quiet "$SEED"
git -C "$SEED" config user.email t@t && git -C "$SEED" config user.name t
git -C "$SEED" checkout --quiet -b main
echo one > "$SEED/f"
mkdir -p "$SEED/security"
echo "release@kiban $TRUSTED_PUB" > "$SEED/security/allowed_signers"
git_quiet "$SEED" add f security/allowed_signers
git_quiet "$SEED" commit -m one
git -C "$SEED" remote add origin "$REMOTE"
git_quiet "$SEED" push -u origin main

export KONJO_HOME="$WORK/home"
export KIBAN_DIR="$KONJO_HOME/kiban"
mkdir -p "$KONJO_HOME"
SECURITY_LOG="$KONJO_HOME/security.log"
git clone --quiet "$REMOTE" "$KIBAN_DIR"
git -C "$KIBAN_DIR" config user.email t@t && git -C "$KIBAN_DIR" config user.name t
git -C "$KIBAN_DIR" branch --quiet --set-upstream-to=origin/main main 2>/dev/null || \
  git -C "$KIBAN_DIR" checkout --quiet -b main --track origin/main 2>/dev/null || true

before="$(git -C "$KIBAN_DIR" rev-parse HEAD)"

# 1. KONJO_SKIP_UPDATE bypasses everything (no fetch, no sentinel).
( cd "$WORK" && KONJO_SKIP_UPDATE=1 bash "$SELF_UPDATE" )
[ ! -f "$KONJO_HOME/.last_update_check" ] || fail "skip should not write sentinel"
[ "$(git -C "$KIBAN_DIR" rev-parse HEAD)" = "$before" ] || fail "skip should not move HEAD"
pass "KONJO_SKIP_UPDATE bypasses update"

# 2. Unpinned fast-forward: a validly-signed tag applies and the sentinel is written.
echo two > "$SEED/f"; git_quiet "$SEED" commit -am two
sign_tag "$SEED" v0.0.2 HEAD "$WORK/trusted_key" release@kiban
v002_sha="$(git -C "$SEED" rev-parse v0.0.2^{commit})"
git_quiet "$SEED" push origin HEAD:main
git_quiet "$SEED" push origin v0.0.2
( cd "$WORK" && KONJO_UPDATE_INTERVAL=0 bash "$SELF_UPDATE" )
[ -f "$KONJO_HOME/.last_update_check" ] || fail "successful check should write sentinel"
[ "$(git -C "$KIBAN_DIR" rev-parse HEAD)" = "$v002_sha" ] || fail "valid signed tag should fast-forward HEAD to it"
pass "unpinned fast-forward advances HEAD to the latest signed tag and stamps sentinel"

# 3. Throttle: with a fresh sentinel and the default interval, no update happens even
#    though a newer signed tag exists.
echo three > "$SEED/f"; git_quiet "$SEED" commit -am three
sign_tag "$SEED" v0.0.3 HEAD "$WORK/trusted_key" release@kiban
git_quiet "$SEED" push origin HEAD:main
git_quiet "$SEED" push origin v0.0.3
( cd "$WORK" && bash "$SELF_UPDATE" )  # default interval 3600s, sentinel just written
[ "$(git -C "$KIBAN_DIR" rev-parse HEAD)" = "$v002_sha" ] || fail "throttle should skip update"
pass "throttle sentinel respected"

# 4. Failure safety: a broken remote must not error or move HEAD.
rm -rf "$REMOTE"
( cd "$WORK" && KONJO_UPDATE_INTERVAL=0 bash "$SELF_UPDATE" ) || fail "must exit 0 on fetch failure"
[ "$(git -C "$KIBAN_DIR" rev-parse HEAD)" = "$v002_sha" ] || fail "fetch failure must not move HEAD"
pass "fetch failure is swallowed, no error"

# Rebuild the remote with everything pushed so far (main + tags) for the rest of the run.
git init --quiet --bare "$REMOTE"
git -C "$REMOTE" symbolic-ref HEAD refs/heads/main
git_quiet "$SEED" push origin HEAD:main
git_quiet "$SEED" push origin --tags

# 5. Unsigned tag is a no-op: a lightweight (unsigned) tag, even a newer version than
#    the currently-applied one, must not move HEAD -- and it logs a security event
#    distinguishable from a network failure.
echo four > "$SEED/f"; git_quiet "$SEED" commit -am four
git -C "$SEED" tag v0.0.4 HEAD  # lightweight, unsigned
git_quiet "$SEED" push origin HEAD:main
git_quiet "$SEED" push origin v0.0.4
( cd "$WORK" && KONJO_UPDATE_INTERVAL=0 bash "$SELF_UPDATE" )
[ "$(git -C "$KIBAN_DIR" rev-parse HEAD)" = "$v002_sha" ] || fail "unsigned tag must not move HEAD"
log_has "$SECURITY_LOG" "event=update_skipped ref=v0.0.4 reason=unsigned" \
  || fail "unsigned tag should log a distinguishable security event"
pass "unsigned tag is a no-op and logs reason=unsigned"

# 6. Invalid signature is a no-op: signed by a key that is not in allowed_signers
#    (even with the tagger email spoofed to the trusted principal) must not move HEAD,
#    and must log as invalid_signature -- a stronger tamper signal than "unsigned".
echo five > "$SEED/f"; git_quiet "$SEED" commit -am five
sign_tag "$SEED" v0.0.5 HEAD "$WORK/attacker_key" release@kiban
git_quiet "$SEED" push origin HEAD:main
git_quiet "$SEED" push origin v0.0.5
( cd "$WORK" && KONJO_UPDATE_INTERVAL=0 bash "$SELF_UPDATE" )
[ "$(git -C "$KIBAN_DIR" rev-parse HEAD)" = "$v002_sha" ] || fail "invalidly signed tag must not move HEAD"
log_has "$SECURITY_LOG" "event=update_skipped ref=v0.0.5 reason=invalid_signature" \
  || fail "invalid signature should log reason=invalid_signature, distinct from unsigned"
pass "invalid signature is a no-op and logs reason=invalid_signature (distinct from unsigned)"

# 7. Recovery: once a validly-signed tag supersedes the bad ones, the update resumes.
echo six > "$SEED/f"; git_quiet "$SEED" commit -am six
sign_tag "$SEED" v0.0.6 HEAD "$WORK/trusted_key" release@kiban
v006_sha="$(git -C "$SEED" rev-parse v0.0.6^{commit})"
git_quiet "$SEED" push origin HEAD:main
git_quiet "$SEED" push origin v0.0.6
( cd "$WORK" && KONJO_UPDATE_INTERVAL=0 bash "$SELF_UPDATE" )
[ "$(git -C "$KIBAN_DIR" rev-parse HEAD)" = "$v006_sha" ] || fail "valid signed tag should resume updates"
pass "a subsequent valid signed tag resumes updates past the unsigned/invalid ones"

# 8. Pinning: a pin to a signed tag verifies and checks out.
CONSUMER="$WORK/consumer"
mkdir -p "$CONSUMER/.konjo"
echo "v0.0.2" > "$CONSUMER/.konjo/kiban.ref"
( cd "$CONSUMER" && KONJO_UPDATE_INTERVAL=0 bash "$SELF_UPDATE" )
[ "$(git -C "$KIBAN_DIR" rev-parse HEAD)" = "$v002_sha" ] || fail "pin to a signed tag should check it out"
pass "pin to a signed tag verifies and checks out"

# 9. Pinning to an unsigned tag refuses rather than applying blindly.
pinned_before="$(git -C "$KIBAN_DIR" rev-parse HEAD)"
echo "v0.0.4" > "$CONSUMER/.konjo/kiban.ref"
( cd "$CONSUMER" && KONJO_UPDATE_INTERVAL=0 bash "$SELF_UPDATE" )
[ "$(git -C "$KIBAN_DIR" rev-parse HEAD)" = "$pinned_before" ] || fail "pin to an unsigned tag must refuse, not apply"
log_has "$SECURITY_LOG" "event=pin_refused ref=v0.0.4 reason=unsigned" \
  || fail "refused pin should log reason=unsigned"
pass "pin to an unsigned tag refuses to update and logs the refusal"

# 10. Pinning to a mutable ref (a branch) refuses too -- it carries none of a tag's
#     signing guarantee, so it must not be treated as equivalent to a signed pin.
#     git's own ref resolution finds refs/heads/main directly (it is unambiguous) and
#     reports it as a non-tag object -- the same message a lightweight tag gets -- so
#     this lands in the "unsigned" bucket too: either way, there is no tag signature
#     to check, and the pin is refused rather than applied.
echo "main" > "$CONSUMER/.konjo/kiban.ref"
( cd "$CONSUMER" && KONJO_UPDATE_INTERVAL=0 bash "$SELF_UPDATE" )
[ "$(git -C "$KIBAN_DIR" rev-parse HEAD)" = "$pinned_before" ] || fail "pin to a branch must refuse, not apply"
log_has "$SECURITY_LOG" "event=pin_refused ref=main reason=unsigned" \
  || fail "pin to a branch should log a refusal distinguishing it from a signed-tag pin"
pass "pin to a mutable branch refuses (distinguishable from a signed-tag pin)"

# 11. C2: unpin-then-update transition still works once verification is in play. The
#     clone is detached at v0.0.2 (from test 8). With the pin removed, an unpinned
#     update must reattach to the default branch and fast-forward to the newest
#     signed tag (v0.0.6), not silently no-op forever in detached HEAD.
rm -f "$CONSUMER/.konjo/kiban.ref"
git -C "$KIBAN_DIR" remote set-head origin main >/dev/null 2>&1 || \
  git -C "$KIBAN_DIR" symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main >/dev/null 2>&1 || true
detached_before="$(git -C "$KIBAN_DIR" rev-parse HEAD)"
git -C "$KIBAN_DIR" symbolic-ref --quiet HEAD >/dev/null 2>&1 && fail "precondition: HEAD should be detached after pin"
( cd "$CONSUMER" && KONJO_UPDATE_INTERVAL=0 bash "$SELF_UPDATE" ) || fail "unpin update must exit 0"
git -C "$KIBAN_DIR" symbolic-ref --quiet HEAD >/dev/null 2>&1 || fail "unpin update should reattach HEAD to a branch"
[ "$(git -C "$KIBAN_DIR" rev-parse HEAD)" = "$v006_sha" ] || fail "unpin update should fast-forward to the latest signed tag"
[ "$(git -C "$KIBAN_DIR" rev-parse HEAD)" != "$detached_before" ] || fail "unpin update should have moved off the detached pin"
pass "unpin-then-update reattaches and fast-forwards to the latest signed tag"

echo "ALL self_update tests passed"
