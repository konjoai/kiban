#!/usr/bin/env bash
# install.sh: set up the kiban foundation on this machine.
#
# gstack-style: a plain git clone to ~/.konjo/kiban, no plugin marketplace. Idempotent
# and safe to re-run. Ledger state lives in ~/.konjo/state, outside the clone, so an
# update never touches it.
#
# What it does:
#   - clone konjoai/kiban into ~/.konjo/kiban if absent; otherwise run the self-update.
#   - create ~/.konjo/state if absent (never overwrite it).
#   - print (does not auto-edit your rc) the line to add bin/ to PATH.

set -euo pipefail

KONJO_HOME="${KONJO_HOME:-$HOME/.konjo}"
KIBAN_DIR="${KIBAN_DIR:-$KONJO_HOME/kiban}"
STATE_DIR="${KONJO_STATE_DIR:-$KONJO_HOME/state}"
REPO_URL="${KIBAN_REPO_URL:-https://github.com/konjoai/kiban.git}"

mkdir -p "$KONJO_HOME"

if [ -d "$KIBAN_DIR/.git" ]; then
  echo "kiban present at $KIBAN_DIR; running self-update check"
  # Source the self-update from the existing clone so a re-run stays current.
  if [ -f "$KIBAN_DIR/lib/self_update.sh" ]; then
    # shellcheck source=/dev/null
    . "$KIBAN_DIR/lib/self_update.sh"
    konjo_self_update || true
  fi
else
  echo "cloning kiban into $KIBAN_DIR"
  git clone --quiet "$REPO_URL" "$KIBAN_DIR"
fi

# State dir is created once and never overwritten on re-run.
if [ ! -d "$STATE_DIR" ]; then
  mkdir -p "$STATE_DIR/ledger"
  echo "created state dir at $STATE_DIR"
else
  echo "state dir already present at $STATE_DIR (left untouched)"
fi

# Make the shipped CLIs executable (no-op if already set).
chmod +x "$KIBAN_DIR/bin/"* 2>/dev/null || true

BIN_DIR="$KIBAN_DIR/bin"
echo
echo "kiban installed."
echo "Add the CLIs to your PATH by adding this line to your shell rc:"
echo
echo "    export PATH=\"$BIN_DIR:\$PATH\""
echo
echo "Then 'konjo-prose' and 'konjo-decision' work from any directory."
