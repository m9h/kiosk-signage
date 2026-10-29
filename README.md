# Fire TV kiosk

A single-purpose WebView kiosk for Fire TV Sticks, plus a small build pipeline
that turns a list of events into a rotating portrait signage page. Used to drive
the Frontier Tower floor kiosks (the live device inventory is kept out of this
repo — see [Inventory](#inventory)).

The app is built with the bare Android build tools (`./build.sh`; SDK pieces:
build-tools 35.0.1 + platform 35, unpacked under
`~/.local/share/android-sdk-min/{bt,pf}`).

**App behaviour:** full screen, screen kept on, reloads the page every 15 min,
retries 30 s after a failed load. It starts ~5 min after boot (a 3-min exact
alarm after Fire OS's late `BOOT_COMPLETED`, so it never covers the "Allow USB
debugging?" prompt) and **persists the last URL**, so a rebooted stick comes back
to whatever page it was showing. A single Back does nothing; **Back 3× within 2 s
leaves the kiosk**; Home leaves it too.

## The slide rotation

The page shown on the sticks is a rotation of full-screen portrait slides, built
from a config file. Slide types: `home` (a Frontier Tower hero), `event`
(a featured event), `calendar` (the live Luma calendar embed) and `brand`.

```
web/kiosk-cycle.conf.json   # the rotation: one entry per slide
        │  scripts/build-kiosk.py
        ▼
web/kiosk-cycle.html        # assembled page (data: URL at deploy time)
```

`scripts/build-kiosk.py` reads the conf and, for each `event`, fetches the Luma
event page, parses its embedded `__NEXT_DATA__`, and derives the title, subtitle,
membership badge, date/time, venue and host, pulls the cover image, and generates
the RSVP QR. So **adding a featured event is one line** in the conf:

```json
{ "type": "event", "ms": 16000, "url": "https://luma.com/your-event-slug" }
```

Optional per-event overrides: `title`, `subtitle`, `badge`, `tagline`, `cover`.
Requires `segno` (`pip install segno`).

The homepage hero is rebuilt locally rather than framing frontiertower.io, which
sends `X-Frame-Options: DENY` and is a scroll-pinned animation that cannot be
paged into a static slide.

## Deploying

`scripts/push-cycle.sh` builds the page and pushes it to one or more sticks over
ADB as a `data:` URL — no APK change, reversible:

```
scripts/push-cycle.sh <ip-or-serial> [<ip-or-serial> ...]
scripts/push-cycle.sh --revert <ip> ...     # back to the bare calendar embed
PY=/path/to/python scripts/push-cycle.sh ... # a python that has segno
```

Under the hood each deploy is:

```
adb connect <ip>:5555                         # ADB over Wi-Fi; adbd listens on 5555
adb shell am start -n org.mhough.kiosk/.KioskActivity --es url <URL> --ei rotation 270
adb exec-out screencap -p > shot.png          # see what is on screen
adb install -r kiosk.apk                       # update the app (keeps the URL)
```

After a first install, allow the boot start (Android 10+ blocks activity starts
from a boot receiver otherwise):

```
adb shell appops set org.mhough.kiosk SYSTEM_ALERT_WINDOW allow
```

## Portrait rotation

Rotate **inside the kiosk**, never the whole display. `wm user-rotation` /
`settings put system user_rotation` looks right in a screenshot but scrambles the
stick's HDMI output (vertical stripes, nothing readable, including the ADB
prompt). The kiosk turns the page itself and keeps the setting:

```
adb shell am start -n org.mhough.kiosk/.KioskActivity --ei rotation 270   # 90 / 270 portrait; 0 = landscape
```

If the display was rotated anyway, undo it with
`adb shell settings put system user_rotation 0` and
`adb shell wm set-fix-to-user-rotation disabled`.

## Setting up a new stick

1. Developer options → ADB debugging on.
2. Stop the adb server (`adb kill-server`), plug the stick into the laptop, wait
   for the home screen, then `adb start-server` — a prompt raised during boot
   gets hidden behind the launcher and cannot be answered.
3. Authorize prompt: focus starts on "Always allow" — Select (tick), Down (Allow,
   the LEFT button), Select. The first Wi-Fi connect may raise a second prompt.
4. Time zone, if it came up on GMT:
   `adb shell settings put global auto_time_zone 0; adb shell cmd alarm set-timezone America/Los_Angeles`.
5. `adb install -r kiosk.apk`,
   `adb shell appops set org.mhough.kiosk SYSTEM_ALERT_WINDOW allow`, deploy a
   page, then reboot over Wi-Fi and reconnect — no prompt means the approval stuck.

**Wi-Fi MACs:** use the MAC the network sees (`ping -c1 <ip>; ip neigh show <ip>`).
These sticks put their fixed hardware MAC on the air; Fire OS 8's `dumpsys wifi`
lists a per-SSID randomized MAC that is not actually used here. To read a saved
network's MAC: `adb shell dumpsys wifi | grep -E '^ID:|mRandomizedMacAddress'`.

## Inventory

The live device inventory (per-floor serials, MACs, IPs, ADB key fingerprint and
Amazon account names) is **not** in this repo — it is kept locally in
`INVENTORY.md` / `inventory.csv` (gitignored). Keep it on the managing host; it is
site-specific and need not be published. Find a stick by MAC: ping-sweep the /24,
then `ip neigh | grep <mac>`.

Rename sticks on the Amazon account (amazon.com → Content & Devices → Devices):
Fire OS restores `device_name` from the account at every boot, so `settings put`
does not last.
