---
decays: reference
---

# konjo-skis

Portable, CLI-free variants of a subset of `kiban`'s `plugins/konjo/skills/`
family -- the skills that still deliver real value on a surface with no
`~/.konjo` and no `konjo-*` binary: the phone, a cloud routine, any claude.ai
account-skill surface. Built Sprint K1, gated on KT-4
(`.konjo/killtests/CortexSkis/KT-4.md`) actually passing before this directory
was allowed to exist.

## Why a separate plane, not a flag on the existing skills

`plugins/konjo/skills/` is the Claude Code plane -- authoritative for anything
that shells out to a `konjo-*` binary or reads `$HOME/.konjo`. `konjo-skis` is
a distinct, smaller set with the CLI/HOME dependency designed out, not toggled
off. Duplicating one `SKILL.md` with an `if-cli-available` branch would mean
every future edit has to remember to update both paths in lockstep with no
mechanism enforcing it -- exactly the drift `Doc-Integrity-Gate-1`
(`LEDGER.md`) already found and fixed once for the `konjo-ship` family, the
hard way. Two files, two names, two purposes: `plugins/konjo/skills/recall`
shells out to `konjo-decision search`; `konjo-skis/recall` reads a Cortex page.
Neither silently degrades into the other.

## What's here, and what stayed behind, and why

| skill | CLI-ref count (Phase 0 audit) | ported? |
|---|---|---|
| `recall` | 7 | **yes** -- KT-4-validated, 25/30 on the KT-1 sweep, 100% on the literal no-CLI subprocess proof |
| `longrun` | 1 | **yes** -- after the preamble line, it was already pure code-authoring guidance with no runtime CLI dependency |
| `decide` | 2 | **no**, deliberately -- see below |
| `konjo-ship`, `correct`, `craft`, `mutation-hunt`, `konjo` | 6, 6, 6, 2, 4 | no -- code-work skills that need gates, and gates need the machine (Phase 3 non-goal, stated in the sprint brief) |

**`decide` was NOT ported despite its low CLI-ref count, and that count is
misleading for this one skill.** `decide`'s entire function is a *write* to
the Ledger (`konjo-decision decide`), and this sprint's own stated,
deliberately-unsolved constraint is that writes are laptop-only -- a decision
made from the phone cannot be logged from the phone, full stop, no server, not
this sprint. A CLI-ref count ranks *how much text mentions a binary*, not
*whether the skill's core function survives losing it* -- for `recall` losing
the CLI means "read markdown instead of running a search command," a real
substitute; for `decide` losing the CLI means the skill cannot do the one
thing it exists to do. Porting it would produce a skill that fails on every
surface it was built for, exactly the "silently degrades" failure mode risk
#4 warned about, just with a louder and more obvious failure than the
recall/embedding tradeoff had.

## Prerequisite

Every skill here reads a Cortex page -- the projected markdown read model
folded from the Konjo Ledger event stream (`ledger/schema.md`,
`lib/cortex.py`). Reachable once `konjo-cortex` (a private repo,
`wesleyscholl/konjo-cortex`) exists and whatever surface is running the
skill has a GitHub repository integration granting read access to it. **Not
a claude.ai connector** -- `LEDGER.md`'s `Skis-Contract-1` entry (Finding 1)
corrects an earlier sprint's misuse of that term: cloud sessions reach a
private repo through an account-level GitHub App installation or personal
access token, configured directly against the session or routine (a
routine's own Repositories field, or `create_session`'s `source_url`), never
through the connector plane Canva/Gmail/Drive/Trello live on. See
`.konjo/killtests/CortexSkis/KT-7.md` (reachability proven via
`source_url`) and `KT-3.md` (the taxonomy correction in full, closed
INVALID PREMISE).

## Location and visibility (Sprint K3)

`konjo-skis` is public (`konjoai/kiban` is public) and this is the first
sprint treating it as a shipping artifact rather than a staging directory,
so the location and visibility calls get logged here rather than left as
an unexamined default:

- **Stays in `kiban`, not a separate repo.** `recall`'s two variants share
  Phase 1's consistency requirement (`konjo-skis/CONTRACT.yml`,
  `bin/konjo-skis-check`), and a gate cannot enforce across a repo boundary
  without new machinery this sprint isn't building. Splitting `konjo-skis`
  out would either lose that enforcement or require duplicating it.
- **Public, on purpose.** Procedures are public; data is private. A skill
  file contains no facts about any repo's actual decisions -- only how to
  read a Cortex page once you're holding one. The private data
  (`wesleyscholl/konjo-cortex`'s content) and the public procedure for
  reading it are different things, and only the second lives here.
- **Org (`konjoai`), not personal.** Nothing pushes `konjo-skis` toward a
  personal account the way `konjo-cortex` was pushed there (`Cortex-Projection-1`'s
  private-repo choice was about data; this is procedure).
- **Split-out triggers, any one sufficient to revisit this:** a
  non-code-work skill lands here that stretches `kiban`'s own scope; an
  external consumer wants `konjo-skis` without `kiban`'s gates and language
  packages; or `konjo-skis` needs a release cadence that breaks
  one-sprint-one-`VERSION`.

**`konjo-skis/README.md` naming `wesleyscholl/konjo-cortex`, a private repo,
in this public file: logged as a decision, not an oversight.** A repo name
alone grants no access -- reaching it still requires the GitHub repository
integration `Finding 1` (`LEDGER.md`'s `Skis-Contract-1` entry) describes,
which is account-scoped and not something knowing the name confers. Kept
for the same reason any of this file names it: a reader following this
skill needs to know which repo to point their own integration at.

**Exposure scan, this sprint:** `konjo-skis/` and `plugins/konjo/skills/`
scanned for internal hostnames, private-repo paths beyond the one named
above, and org-internal vocabulary (personal names/emails, the `M3`
laptop nickname used in `LEDGER.md`'s own prose) -- none found.
`lib/redact.py`'s `scan_paths` (the same secret-scanning mechanism behind
`konjo-secrets` and CI's `gate_secrets`) run directly over both trees'
files (not diff-based, since there's no diff to scan against for a
point-in-time sweep): 12 files, 0 findings.

## Publishing

These are staged here, in `kiban`, not yet uploaded as claude.ai account
skills -- no tool in this session's toolset can perform that upload; it is a
manual step in claude.ai's own skill settings. Copy `konjo-skis/recall/` and
`konjo-skis/longrun/` there once `konjo-cortex` exists and has been pushed to
at least once, so `recall`'s first real run has something to read.
