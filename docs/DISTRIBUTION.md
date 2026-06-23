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

## State lives outside the clone

Ledger state lives in `~/.konjo/state`, not inside `~/.konjo/kiban`. An update touches
the clone, never the state, so there is no way for a self-update to corrupt or lose the
lab notebook.

State syncs across machines through a separate private repo. It is redact-scanned
(`lib/redact.py`) before every push: HIGH-tier secrets block the push. The kiban repo
itself carries no state.

## Per-repo version pinning

A consuming repo pins a kiban ref two ways:

- `.konjo/kiban.ref` in the repo (session plane): the self-update checks out that ref
  instead of pulling main.
- `KIBAN_REF` in CI (CI plane): the installed gate package is pinned to that tag or sha.

Pinning is the rollout control. A master change lands repo by repo on a deliberate
schedule by bumping each repo's pin, never all repos at once.
