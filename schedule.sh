#!/bin/bash
# schedule.sh — Install or uninstall the Wise Glade daily launchd job (macOS)
# Usage:
#   bash schedule.sh install    # Runs agent.py every morning at 8:00am
#   bash schedule.sh uninstall  # Removes the scheduled job

PLIST_LABEL="com.wiseglade.agent"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"
AGENT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$AGENT_DIR/logs"
PYTHON_BIN="$(which python3)"

case "${1:-}" in
  install)
    echo "Installing Wise Glade daily job..."
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
  <string>$LOG_DIR/wise-glade.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/wise-glade.error.log</string>
  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
PLIST

    launchctl load "$PLIST_PATH"
    echo "Done. Wise Glade will run every morning at 8:00am."
    echo "Logs: $LOG_DIR/wise-glade.log"
    echo ""
    echo "To verify: launchctl list | grep wiseglade"
    echo "To run now: python3 $AGENT_DIR/agent.py --dry-run"
    ;;

  uninstall)
    if [ -f "$PLIST_PATH" ]; then
      launchctl unload "$PLIST_PATH"
      rm "$PLIST_PATH"
      echo "Wise Glade daily job removed."
    else
      echo "No scheduled job found at $PLIST_PATH"
    fi
    ;;

  *)
    echo "Usage: bash schedule.sh [install|uninstall]"
    exit 1
    ;;
esac
