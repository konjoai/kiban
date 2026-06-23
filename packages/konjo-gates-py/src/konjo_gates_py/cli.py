"""konjo-gates console entry point.

STUB (phase 1). The working runner installs the same lib/ engine kiban ships and runs
the consuming repo's profile gates in CI. The CI plane is fully self-contained: it never
reads ~/.konjo, so the gate logic is the pinned, installed package, not the global clone.

Contract for the phase-1 implementation:
  konjo-gates --profile .konjo/profile.yml
    - load the profile, select gates by diff_scope, run each gate
    - emit a structured report, exit nonzero on any blocking failure
    - run the meta-gate self-test against the eval corpus

This stub prints "phase 1" and exits 0 so the CI wiring can be validated before the
runner exists.
"""

from __future__ import annotations

import sys

# TODO(phase-1): load profile, run gates, compare against prove baseline.


def main() -> int:
    print("konjo-gates: phase 1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
