# Distribution model

kiban uses a gstack-style distribution: one plain git clone per machine, self-updating,
no plugin marketplace. This page is the reference for how it ships and how a change rolls
out.

## One clone per machine

`install.sh` clones `konjoai/kiban` to `~/.konjo/kiban`. That is it. No marketplace, no
plugin cache, no per-project copy. Re-running `install.sh` is safe and runs the
self-update path instead of re-cloning.

## Two planes

The repo serves two separate consumers.

**Session plane**: skills, hooks, and CLAUDE.md rules. These read from the global clone
at `~/.konjo/kiban`. Each skill runs the self-update preamble first so the session plane
stays current.

**CI plane**: the actual blocking gates. These ship as pinned, installable packages
(`packages/konjo-gates-py`, `-rs`, `-js`). A consuming repo's CI installs the pinned
package and runs it. The CI plane never reads `~/.konjo`; the gate logic is the installed
package, so CI is reproducible and does not depend on a developer's local clone state.

## Self-update

`lib/self_update.sh` runs on every skill invocation but is throttled and failure-safe:

- Throttled by `~/.konjo/.last_update_check` (interval `KONJO_UPDATE_INTERVAL`, default
  3600s).
- Bypassed entirely by `KONJO_SKIP_UPDATE=1`.
- Fast-forward only. It fetches then `merge --ff-only`. It never auto-merges a
  divergence.
- Any network or git failure is swallowed silently and never blocks or errors a session.
  The sentinel is stamped only on a successful check.

### Signature verification

Fast-forward-only stops a *divergent* history, but does nothing against a malicious,
fast-forwardable commit pushed straight to the tracked upstream. `self_update.sh`
closes that gap: it verifies a signed-tag signature before applying anything, using
`security/allowed_signers` (git's native ssh-signing verification, `git verify-tag`) as
the trust anchor. That file is read from the working tree as it stands *before* the
update is applied, never from the newly fetched ref, so a compromised push cannot
rewrite its own trust anchor and pass.

- **Unpinned.** The update unit is the newest signed release tag reachable from the
  tracking branch (`git tag --list --merged @{u} --sort=-v:refname`), not the raw
  branch tip -- verifying every commit on `main` would mean signing every commit,
  which this project deliberately does not do (see `LEDGER.md`). If that tag's
  signature doesn't verify, or no signed tag is reachable yet, the update is a silent
  no-op: exactly as failure-safe as a network miss, never a block.
- **Pinned.** The pin is expected to name a signed tag. A pin that doesn't verify --
  unsigned, invalidly signed, or a mutable ref like a branch -- is refused rather than
  applied. This is deliberately stricter than the unpinned path: a pin is an explicit
  operator choice, so a pin that stops verifying is worth surfacing every time, not
  just discovering once.
- **Discoverability.** A verification failure (as opposed to a network/fetch failure,
  which is never logged) is appended to `~/.konjo/security.log` with a reason:
  `unsigned`, `invalid_signature` (signed, but not by a trusted key -- the strongest
  tamper signal), `unresolvable_ref`, or `unverifiable`. Silent-to-the-session is
  correct for failure-safety; invisible-forever is not, so a repeated failure
  accumulates there for an operator who looks.

## State lives outside the clone

Ledger state lives in `~/.konjo/state`, not inside `~/.konjo/kiban`. An update touches
the clone, never the state, so there is no way for a self-update to corrupt or lose the
lab notebook.

State syncs across machines through a separate private repo. It is redact-scanned
(`lib/redact.py`) before every push: HIGH-tier secrets block the push. The kiban repo
itself carries no state.

## The konjo-* skill family (absorbed into the session plane)

Before the Doc Integrity sprint, `konjo-boot`, `konjo-philosophy`, `konjo-quality`,
`konjo-retrofit`, and `konjo-ship` lived only as hand-copied `.claude/skills/` files
inside consuming repos (`lopi`, `miru`), with no canonical source anywhere and no
distribution mechanism — `self_update.sh` only ever fast-forwards the global clone
itself, never a consuming repo's `.claude/skills/`. The copies drifted: `konjo-ship`'s
Sprint Completion Checklist was byte-identical between `lopi` and `miru` (a hand-copy
that had never been re-synced), and it enumerated three filenames as the definition of
"sprint complete," which is exactly the kind of claim this sprint's `decays:`
convention exists to keep from going stale unnoticed. See `LEDGER.md` for the decision
record.

`konjo-ship` is the first of the family moved into `plugins/konjo/skills/` here: one
canonical file, distributed the same way `craft` and `decide` already are, rather than
N per-repo copies to keep in sync by hand. The other four (`konjo-boot`,
`konjo-philosophy`, `konjo-quality`, `konjo-retrofit`) are not migrated by this sprint —
`konjo-quality`/`konjo-retrofit` in particular are Rust-quality-framework specific and
need real generalization work, not a file move. See `NEXT_SESSION_PROMPT.md`.

**Override path.** A consuming repo that needs a genuinely different version of a
global skill keeps a repo-scoped `.claude/skills/<name>/SKILL.md`. Skill resolution
already prefers the more specific match when both a repo-scoped and an unscoped
(global) skill share a name, so the repo-local copy wins there with no extra plumbing.
This is deliberately visible, not silent: an override is a file that exists and can be
diffed against the global version, not a fork nobody remembers making.

## Per-repo version pinning

A consuming repo pins a kiban ref two ways:

- `.konjo/kiban.ref` in the repo (session plane): the self-update checks out that ref
  instead of pulling main.
- `KIBAN_REF` in CI (CI plane): the installed gate package is pinned to that tag or sha.

Pinning is the rollout control. A master change lands repo by repo on a deliberate
schedule by bumping each repo's pin, never all repos at once.

**Pin to a signed release tag (`vX.Y.Z`), never to `main` or any other branch.** A
branch pin carries none of a tag's signing guarantee -- `self_update.sh` now refuses it
outright (see Signature verification, above) rather than silently applying it. `KIBAN_REF`
in CI should likewise name a signed tag, not a branch or an unpinned floating ref.

### Cutting a signed release (maintainer)

`.github/workflows/release.yml` does this automatically on a `VERSION` bump landing on
`main`: it creates a signed, annotated tag (`git tag -s -a`, ssh format) using the
`RELEASE_SIGNING_KEY` repo secret, pushes the tag, then creates the GitHub release
against it. The tagger identity is `release@kiban`, which must match the principal in
`security/allowed_signers` -- that is what git's ssh verification matches against, not
the key's comment.

To cut a release by hand (bypassing the workflow) or to rotate the signing key:

```bash
git config user.email release@kiban
git config gpg.format ssh
git config user.signingkey /path/to/release_signing_key   # the private half
git tag -s -a vX.Y.Z -m vX.Y.Z <commit>
git push origin vX.Y.Z
```

Rotating the key: add the new public key as a new line in `security/allowed_signers`,
commit it, and sign *that* commit's release tag with the *old* key -- consuming clones
read `allowed_signers` from their pre-update working tree, so the new key only becomes
trusted once a release signed under the current trust anchor has been accepted. Never
remove the last working line without a verified replacement already in place.
