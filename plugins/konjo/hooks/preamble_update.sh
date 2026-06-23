#!/usr/bin/env bash
# preamble_update.sh: the hook every skill preamble runs first.
#
# It calls the throttled, failure-safe self-update so the session plane stays current
# against the global clone without a marketplace. It can never block or error a
# session: lib/self_update.sh swallows every failure.

set -u

KONJO_HOME="${KONJO_HOME:-$HOME/.konjo}"
KIBAN_DIR="${KIBAN_DIR:-$KONJO_HOME/kiban}"

if [ -f "$KIBAN_DIR/lib/self_update.sh" ]; then
  # shellcheck source=/dev/null
  . "$KIBAN_DIR/lib/self_update.sh"
  konjo_self_update || true
fi

exit 0
