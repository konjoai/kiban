"""Tests for the headless host helper (lib/headless).

The load-bearing detail: stream-json in --print mode requires --verbose, and the helper must
add it automatically. These pin the argv shape so a host cannot regress that.
"""

from __future__ import annotations

from lib import headless


def test_default_argv_is_bare_streamjson_verbose() -> None:
    argv = headless.headless_argv("do a thing")
    assert argv[:3] == ["claude", "-p", "do a thing"]
    assert "--bare" in argv
    # stream-json must always be accompanied by --verbose (CLI-enforced in --print mode).
    assert "--output-format" in argv
    i = argv.index("--output-format")
    assert argv[i + 1] == "stream-json"
    assert "--verbose" in argv


def test_text_mode_drops_streamjson_and_verbose() -> None:
    argv = headless.headless_argv("x", stream_json=False)
    i = argv.index("--output-format")
    assert argv[i + 1] == "text"
    assert "--verbose" not in argv


def test_no_bare_omits_bare() -> None:
    assert "--bare" not in headless.headless_argv("x", bare=False)


def test_model_and_extra_are_appended() -> None:
    argv = headless.headless_argv("x", model="claude-opus-4-8", extra=["--max-turns", "3"])
    assert "--model" in argv and argv[argv.index("--model") + 1] == "claude-opus-4-8"
    assert argv[-2:] == ["--max-turns", "3"]


def test_prompt_is_passed_verbatim() -> None:
    # A prompt with spaces and flags-looking text stays one argv element after -p.
    argv = headless.headless_argv("--not-a-flag and spaces")
    assert argv[1] == "-p" and argv[2] == "--not-a-flag and spaces"
