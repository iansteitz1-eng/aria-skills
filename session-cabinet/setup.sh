#!/usr/bin/env bash
# setup.sh — install the session-cabinet launchd agent (macOS)
#
# Idempotent: safe to re-run. Unloads the old agent if present, writes a
# fresh plist, then loads it.
#
# Label: io.ariacode.session-cabinet
# Schedule: every hour (3600 seconds)
# Log: ~/Library/Logs/session-cabinet.log
#
# Usage:
#   bash setup.sh
#   bash setup.sh --uninstall

set -euo pipefail

LABEL="io.ariacode.session-cabinet"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$SCRIPT_DIR/session_cabinet.py"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$PLIST_DIR/${LABEL}.plist"
LOG_PATH="$HOME/Library/Logs/session-cabinet.log"
PYTHON="$(command -v python3 || echo /usr/bin/python3)"

# ---------------------------------------------------------------------------
# Uninstall path
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--uninstall" ]]; then
  echo "Uninstalling $LABEL ..."
  if launchctl list | grep -q "$LABEL"; then
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    echo "  Agent unloaded."
  fi
  if [[ -f "$PLIST_PATH" ]]; then
    rm "$PLIST_PATH"
    echo "  Plist removed: $PLIST_PATH"
  fi
  echo "Done. The Cabinet archive itself is untouched."
  exit 0
fi

# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------
if [[ ! -f "$SCRIPT" ]]; then
  echo "ERROR: session_cabinet.py not found at $SCRIPT" >&2
  echo "Run this script from inside the session-cabinet/ directory." >&2
  exit 1
fi

if [[ "$(uname)" != "Darwin" ]]; then
  echo "NOTE: launchd is macOS-only."
  echo ""
  echo "On Linux / other systems, add this cron line instead:"
  echo "  0 * * * * $PYTHON $SCRIPT >> $LOG_PATH 2>&1"
  echo ""
  echo "Or run it manually:"
  echo "  python3 $SCRIPT"
  exit 0
fi

# ---------------------------------------------------------------------------
# Unload existing agent (if any) before writing a new plist
# ---------------------------------------------------------------------------
if launchctl list 2>/dev/null | grep -q "$LABEL"; then
  echo "Unloading existing agent..."
  launchctl unload "$PLIST_PATH" 2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# Write plist
# ---------------------------------------------------------------------------
mkdir -p "$PLIST_DIR"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>

  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON}</string>
    <string>${SCRIPT}</string>
  </array>

  <key>StartInterval</key>
  <integer>3600</integer>

  <key>RunAtLoad</key>
  <false/>

  <key>StandardOutPath</key>
  <string>${LOG_PATH}</string>

  <key>StandardErrorPath</key>
  <string>${LOG_PATH}</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
</dict>
</plist>
PLIST

echo "Wrote plist: $PLIST_PATH"

# ---------------------------------------------------------------------------
# Load agent
# ---------------------------------------------------------------------------
launchctl load "$PLIST_PATH"
echo "Loaded agent: $LABEL"

# ---------------------------------------------------------------------------
# Next steps
# ---------------------------------------------------------------------------
echo ""
echo "Session Cabinet is now scheduled to run every hour."
echo ""
echo "  Check status:   launchctl list | grep session-cabinet"
echo "  View log:       tail -f $LOG_PATH"
echo "  Run now:        python3 $SCRIPT"
echo "  Dry-run first:  python3 $SCRIPT --dry-run"
echo "  Uninstall:      bash setup.sh --uninstall"
echo ""
echo "Archive location (default): ~/Desktop/Claude Code Sessions/"
echo "Override:  python3 $SCRIPT --cabinet <path>"
echo "           or set CC_CABINET_DIR env var in the plist."
