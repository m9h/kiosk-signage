#!/bin/bash
# Builds kiosk.apk with the bare Android build tools (no Gradle).
# SDK: build-tools 35.0.1 + platform 35 unpacked under $SDK (see README).
set -euo pipefail
SDK=${SDK:-$HOME/.local/share/android-sdk-min}
BT=$(echo "$SDK"/bt/*/)
JAR=$(echo "$SDK"/pf/*/android.jar)
cd "$(dirname "$0")"
rm -rf out && mkdir -p out/gen out/classes out/dex
"$BT"aapt2 compile --dir res -o out/res.zip
"$BT"aapt2 link -o out/unsigned.apk -I "$JAR" --manifest AndroidManifest.xml \
    --java out/gen out/res.zip
javac --release 11 -Xlint:-options -classpath "$JAR" -d out/classes \
    $(find src out/gen -name '*.java')
"$BT"d8 --min-api 25 --lib "$JAR" --output out/dex $(find out/classes -name '*.class')
(cd out/dex && zip -qj ../unsigned.apk classes.dex)
"$BT"zipalign -f -p 4 out/unsigned.apk out/aligned.apk
KS=${KS:-$HOME/.android/kiosk.keystore}
if [ ! -f "$KS" ]; then
    mkdir -p "$(dirname "$KS")"
    keytool -genkeypair -keystore "$KS" -storepass kiosk-local -keypass kiosk-local \
        -alias kiosk -keyalg RSA -keysize 2048 -validity 10000 -dname CN=kiosk >/dev/null
fi
"$BT"apksigner sign --ks "$KS" --ks-pass pass:kiosk-local --out kiosk.apk out/aligned.apk
"$BT"apksigner verify kiosk.apk
echo "built $(pwd)/kiosk.apk"
