"""progress: timestamped heartbeat logging for the CI plane.

konjo-gates runs ~a dozen gates back to back, several of which shell a scanner out
twice (once at HEAD, once at the base ref in a throwaway worktree) with the child's
output captured, not streamed. A compiling or mutation gate (clippy, cargo-mutants,
mutmut, stryker) can therefore burn many minutes producing no output at all, and the
per-gate result table is only printed once every gate has finished. To an operator
watching the CI log that reads as a job hung in silence for twenty minutes and then
failing with no clue which gate was to blame.

This module is the single source of truth for that missing signal. It emits to stderr,
line-buffered and flushed, so a heartbeat lands in the CI log the instant it is written
rather than at process exit. Two levels:

  * log(msg)  -- an always-on heartbeat. konjo-gates prints one when each gate starts
                 and one when it finishes with the gate's elapsed time, so the log shows
                 which gate is running and where the wall-clock is going, with no CI
                 change required by the consuming repo.
  * vlog(msg) -- verbose detail (the exact scanner argv, the two HEAD/base scan passes
                 and each pass's duration). Off by default; enabled by `--verbose`/`-v`
                 on konjo-gates or by exporting KONJO_GATES_VERBOSE=1 in the environment,
                 which also reaches child modules and any subprocess.

stderr, not stdout, keeps the heartbeat out of the gate result table (which konjo-gates
writes to stdout and which other tools may parse); GitHub Actions interleaves the two
streams by timestamp in the rendered log, which is exactly what an operator wants.
"""

from __future__ import annotations

import os
import sys
import time

_VERBOSE_ENV = "KONJO_GATES_VERBOSE"
_TRUTHY = {"1", "true", "yes", "on"}

_PREFIX = "konjo-gates |"


def _env_verbose() -> bool:
    return os.environ.get(_VERBOSE_ENV, "").strip().lower() in _TRUTHY


# Read the environment once at import so a subprocess launched with KONJO_GATES_VERBOSE
# set inherits verbosity without any code passing the flag through. set_verbose() can
# still flip it at runtime (e.g. from the --verbose CLI flag).
_verbose = _env_verbose()


def set_verbose(on: bool) -> None:
    """Turn verbose detail on or off, and propagate it to child processes.

    Writing the env var back means a scanner konjo-gates shells out to -- or the
    lib.newonly engine it imports -- sees the same verbosity the CLI flag asked for,
    with nothing threaded through by hand.
    """
    global _verbose
    _verbose = on
    os.environ[_VERBOSE_ENV] = "1" if on else "0"


def is_verbose() -> bool:
    return _verbose


def _emit(msg: str) -> None:
    # Timestamp each line so a long gap between two heartbeats is legible as elapsed
    # wall-clock even when the CI runner does not stamp its own log lines.
    stamp = time.strftime("%H:%M:%S")
    print(f"{_PREFIX} {stamp} {msg}", file=sys.stderr, flush=True)


def log(msg: str) -> None:
    """Always-on heartbeat to stderr. Use for the signal every operator needs."""
    _emit(msg)


def vlog(msg: str) -> None:
    """Verbose detail to stderr; a no-op unless verbose is on."""
    if _verbose:
        _emit(msg)


def fmt_elapsed(seconds: float) -> str:
    """Human elapsed: `0.4s`, `12.9s`, `3m04s` -- so a 20-minute gate reads at a glance."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m{secs:02d}s"
