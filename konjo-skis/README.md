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
`lib/cortex.py`). Reachable via the GitHub connector once `konjo-cortex` (a
private repo) exists and this account's claude.ai GitHub connector has read
access to it. See `NEXT_SESSION_PROMPT.md` for the exact create/push commands
-- repo creation was blocked in-session by the GitHub App integration's
permissions (403, no account-level repo-creation scope) and is a manual
follow-up.

## Publishing

These are staged here, in `kiban`, not yet uploaded as claude.ai account
skills -- no tool in this session's toolset can perform that upload; it is a
manual step in claude.ai's own skill settings. Copy `konjo-skis/recall/` and
`konjo-skis/longrun/` there once `konjo-cortex` exists and has been pushed to
at least once, so `recall`'s first real run has something to read.
