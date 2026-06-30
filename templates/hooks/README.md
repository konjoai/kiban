# Konjo lifecycle hooks (Phase 11)

Two optional hooks a consuming repo can drop in, both tied to verification. Hooks and
preamble logic are where bloat accumulates, so two narrow hooks is the ceiling; do not add
more.

## What they do

- `stop-verify.sh` (Stop hook): runs the repo's `verify_cmd` when the agent ends a turn, so a
  long autonomous run cannot end on a red state silently. A failed verify blocks the stop
  (exit 2) and feeds the failure back to the agent.
- `posttooluse-format.sh` (PostToolUse hook): runs the repo's `format_cmd` after an edit, so a
  formatting slip never reaches CI. Formatting is convenience; this hook never blocks.

Both read the repo profile (`.konjo/profile.yml`, override with `KONJO_PROFILE`) via
`konjo-profile-get`. Each no-ops when its field is absent or an honest TODO/UNVERIFIED
placeholder, so dropping either in is always safe.

## Install

1. Declare the commands in `.konjo/profile.yml`:

   ```yaml
   verify_cmd: "pytest"          # the test/bench/browser path that proves a change works
   format_cmd: "ruff format ."   # the repo's formatter
   ```

2. Copy the hook scripts into the repo:

   ```bash
   mkdir -p .konjo/hooks
   cp "$HOME/.konjo/kiban/templates/hooks/stop-verify.sh" .konjo/hooks/
   cp "$HOME/.konjo/kiban/templates/hooks/posttooluse-format.sh" .konjo/hooks/
   chmod +x .konjo/hooks/*.sh
   ```

3. Merge the `hooks` block from `settings.snippet.json` into `.claude/settings.json`.

## Headless host

For automation (a CI step, a background agent, the `claude -p` path), use `konjo-headless`,
which bakes `--bare` (fast start) and `--output-format stream-json --verbose` (a realtime
event stream) into one invocation:

```bash
konjo-headless "summarize the diff"     # stream-json events on stdout
konjo-headless --dry-run "x"            # print the argv a host should exec, run nothing
```
