#!/usr/bin/env bash
# Build the kiosk rotation page (scripts/build-kiosk.py) and deploy it to one or
# more Fire TV sticks over ADB as a data: URL (no APK change, reversible).
#
# Usage: scripts/push-cycle.sh <ip-or-serial> [<ip-or-serial> ...]
#        scripts/push-cycle.sh --revert <ip-or-serial> ...   # back to the bare Luma embed
#        PY=/path/to/python scripts/push-cycle.sh <ip> ...    # python that has segno
set -euo pipefail
cd "$(dirname "$0")/.."

ROT=270
EMBED='https://luma.com/embed/calendar/cal-Sl7q1nHTRXQzjP2/events?lt=dark'
PY="${PY:-python3}"

if [ "${1:-}" = "--revert" ]; then
  shift; URL="$EMBED"
else
  "$PY" scripts/build-kiosk.py >&2
  URL="data:text/html;base64,$(base64 -w0 web/kiosk-cycle.html)"
  echo "payload: ${#URL} bytes" >&2
fi
[ "$#" -ge 1 ] || { echo "usage: $0 <ip-or-serial> ..." >&2; exit 2; }

# The URL goes to the stick as a script file rather than an adb shell argument:
# Android 9 sticks (3rd gen) drop an adb command over ~64 KB ("error: closed"),
# while a single argument on the device itself may be up to 128 KB.
CMD=$(mktemp); trap 'rm -f "$CMD"' EXIT
printf "am start -n org.mhough.kiosk/.KioskActivity --es url '%s' --ei rotation %s\n" "$URL" "$ROT" > "$CMD"

for DEV in "$@"; do
  case "$DEV" in *.*.*.*) adb connect "$DEV:5555" >/dev/null 2>&1 || true; T="$DEV:5555";; *) T="$DEV";; esac
  echo "== $T"
  adb -s "$T" push "$CMD" /data/local/tmp/kiosk-start.sh >/dev/null
  adb -s "$T" shell am force-stop org.mhough.kiosk
  sleep 1
  adb -s "$T" shell sh /data/local/tmp/kiosk-start.sh | tail -1
done
