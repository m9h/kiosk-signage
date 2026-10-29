#!/usr/bin/env bash
# Push the Frontier Tower header page to one or more kiosks over ADB.
# The page (web/kiosk.html) is a header band + a live Luma calendar iframe,
# delivered as a data: URL so the installed kiosk APK needs no change.
#
# Usage: scripts/push-header.sh <ip-or-serial> [<ip-or-serial> ...]
#        scripts/push-header.sh --revert <ip-or-serial> ...   # back to the bare embed
set -euo pipefail
cd "$(dirname "$0")/.."

EMBED='https://luma.com/embed/calendar/cal-Sl7q1nHTRXQzjP2/events?lt=dark'
ROT=270

if [ "${1:-}" = "--revert" ]; then
  shift; URL="$EMBED"
else
  URL="data:text/html;base64,$(base64 -w0 web/kiosk.html)"
fi
[ "$#" -ge 1 ] || { echo "usage: $0 <ip-or-serial> ..." >&2; exit 2; }

for DEV in "$@"; do
  case "$DEV" in *.*.*.*) adb connect "$DEV:5555" >/dev/null 2>&1 || true; T="$DEV:5555";; *) T="$DEV";; esac
  echo "== $T"
  adb -s "$T" shell am force-stop org.mhough.kiosk
  sleep 1
  adb -s "$T" shell "am start -n org.mhough.kiosk/.KioskActivity --es url '$URL' --ei rotation $ROT" | tail -1
done
