#!/bin/bash
# schedule.sh — Install or uninstall the Oppo Research daily launchd job (macOS)
# Usage:
#   bash schedule.sh install    # Runs agent.py every morning at 8:00am
#   bash schedule.sh uninstall  # Removes the scheduled job

PLIST_LABEL="com.opporesearch.agent"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"
AGENT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$AGENT_DIR/logs"
PYTHON_BIN="$(which python3)"

case "${1:-}" in
  install)
    echo "Installing Oppo Research daily job..."
    mkdir -p "$LOG_DIR"

    cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$PLIST_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_BIN</string>
    <string>$AGENT_DIR/agent.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$AGENT_DIR</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>8</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/oppo-research.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/oppo-research.error.log</string>
  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
PLIST

    launchctl load "$PLIST_PATH"
    echo "Done. Oppo Research will run every morning at 8:00am."
    echo "Logs: $LOG_DIR/oppo-research.log"
    echo ""
    echo "To verify: launchctl list | grep opporesearch"
    echo "To run now: python3 $AGENT_DIR/agent.py --dry-run"
    ;;

  uninstall)
    if [ -f "$PLIST_PATH" ]; then
      launchctl unload "$PLIST_PATH"
      rm "$PLIST_PATH"
      echo "Oppo Research daily job removed."
    else
      echo "No scheduled job found at $PLIST_PATH"
    fi
    ;;

  *)
    echo "Usage: bash schedule.sh [install|uninstall]"
    exit 1
    ;;
esac
