"""The headless host helper: one place that builds the `claude -p` invocation.

Every repo's automation (a CI step, a background agent, lopi's `claude_stream` path) should
start fast and emit structured events. Two flags do that, and they are easy to get subtly
wrong, so they live here once:

  --bare                 the SDK skips CLAUDE.md / MCP / plugin discovery, keychain reads,
                         and auto-memory: up to ~10x faster startup for a headless call.
  --output-format        "stream-json" emits a realtime event stream (init / assistant /
                         result) instead of one blob, so a host can render progress.

The non-obvious part the CLI enforces: in `--print` mode, `--output-format=stream-json`
requires `--verbose`. This helper adds it automatically, so a caller cannot forget it (the
exact omission behind the lopi `claude_stream.rs` gap). Verified against the installed
`claude` CLI, not assumed.
"""

from __future__ import annotations

import subprocess


def headless_argv(
    prompt: str,
    *,
    model: str | None = None,
    bare: bool = True,
    stream_json: bool = True,
    extra: list[str] | None = None,
) -> list[str]:
    """Build the argv for a fast, structured headless `claude -p` call.

    `bare` skips discovery for a faster start. `stream_json` selects the realtime event
    stream and forces the `--verbose` the CLI requires alongside it; set it False for a plain
    text reply. `extra` is appended verbatim for caller-specific flags (e.g. --model is
    handled here, but --max-turns or --allowedTools are not).
    """
    argv = ["claude", "-p", prompt]
    if bare:
        argv.append("--bare")
    if stream_json:
        # --output-format=stream-json requires --verbose in --print mode (CLI-enforced).
        argv += ["--output-format", "stream-json", "--verbose"]
    else:
        argv += ["--output-format", "text"]
    if model:
        argv += ["--model", model]
    if extra:
        argv += list(extra)
    return argv


def run_headless(
    prompt: str,
    *,
    model: str | None = None,
    bare: bool = True,
    stream_json: bool = True,
    extra: list[str] | None = None,
    timeout: int = 600,
) -> subprocess.CompletedProcess[str]:
    """Run a headless call and return the completed process (stdout is the event stream).

    Captures output as text. The caller decides how to parse it: stream-json yields one JSON
    object per line; text yields the plain reply. Never raises on a nonzero exit; inspect
    `returncode`.
    """
    argv = headless_argv(
        prompt, model=model, bare=bare, stream_json=stream_json, extra=extra
    )
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
