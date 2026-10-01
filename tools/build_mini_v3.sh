#!/usr/bin/env bash
#
# Build the ESP32 Marauder firmware for the Marauder Mini v3 (ESP32-C5).
#
# This mirrors .github/workflows/build_parallel.yml, which is the only place the
# project records how a target is assembled: same Arduino ESP32 core, same pinned
# library revisions, and the same TFT_eSPI configuration step. The Mini v3 build
# itself lives in a private TFT repository upstream, so the panel setup file
# (User_Setup_marauder_mini_v3.h) is carried in this repository instead.
#
# Usage:  tools/build_mini_v3.sh [work-dir]
#
# Produces <work-dir>/out/esp32_marauder.ino.bin (application image, links at
# 0x10000) plus the bootloader and partition table needed for a factory image.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
WORK_DIR="${1:-${REPO_DIR}/../miniv3-build}"
LIB_DIR="${WORK_DIR}/libs"
OUT_DIR="${WORK_DIR}/out"
SKETCH_DIR="${REPO_DIR}/esp32_marauder"

FQBN="esp32:esp32:esp32c5:FlashSize=8M,PartitionScheme=default_8MB,PSRAM=enabled"
CORE_VERSION="3.3.4"
APPLICATION_LIMIT=$((0x330000))

# TFT_eSPI needs the ESP32-C5 port; the upstream Bodmer release has no C5 support.
TFT_REPO="https://github.com/H4W9/TFT_eSPI.git"
TFT_REF="ESP32-C5"

if [[ -n "${ARDUINO_CLI_BIN:-}" ]]; then
  ARDUINO_CLI="${ARDUINO_CLI_BIN}"
elif command -v arduino-cli >/dev/null 2>&1; then
  ARDUINO_CLI="$(command -v arduino-cli)"
elif [[ -x "${HOME}/bin/arduino-cli" ]]; then
  ARDUINO_CLI="${HOME}/bin/arduino-cli"
else
  echo "arduino-cli not found; install it or set ARDUINO_CLI_BIN" >&2
  exit 1
fi

installed_core="$("${ARDUINO_CLI}" core list | awk '$1 == "esp32:esp32" {print $2}')"
if [[ "${installed_core}" != "${CORE_VERSION}" ]]; then
  echo "ESP32 Arduino core ${CORE_VERSION} required; found ${installed_core:-none}" >&2
  echo "Install it with: ${ARDUINO_CLI} core install esp32:esp32@${CORE_VERSION}" >&2
  exit 1
fi

# arduino-cli generates function prototypes for .ino sketches with its own
# bundled ctags, which is an x86_64 binary. On Apple silicon it needs Rosetta 2;
# without it the build aborts before compiling anything with
# "bad CPU type in executable".
#
# Do NOT substitute a native ctags build here. arduino-cli parses ctags output
# with a parser written against Exuberant Ctags 5.8, and a current Universal
# Ctags emits slightly different fields - the prototypes it generates then
# corrupt the sketch (stray tokens reported inside unrelated #ifdefs). Install
# Rosetta instead:
#
#   softwareupdate --install-rosetta --agree-to-license
if [[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]]; then
  bundled_ctags="${HOME}/Library/Arduino15/packages/builtin/tools/ctags/5.8-arduino11/ctags"
  if [[ -f "${bundled_ctags}" ]] && ! "${bundled_ctags}" --version >/dev/null 2>&1; then
    echo "arduino-cli's bundled ctags (x86_64) cannot run on this machine." >&2
    echo "Install Rosetta 2 and retry:" >&2
    echo "  softwareupdate --install-rosetta --agree-to-license" >&2
    exit 1
  fi
fi

mkdir -p "${LIB_DIR}" "${OUT_DIR}"

clone_pinned() {
  local name="$1" url="$2" ref="$3"
  if [[ -d "${LIB_DIR}/${name}/.git" ]]; then
    return
  fi
  rm -rf "${LIB_DIR}/${name}"
  echo "fetching ${name} @ ${ref}"
  git clone --depth 1 --branch "${ref}" "${url}" "${LIB_DIR}/${name}"
}

clone_pinned AsyncTCP         https://github.com/ESP32Async/AsyncTCP.git        v3.4.8
clone_pinned ESPAsyncWebServer https://github.com/ESP32Async/ESPAsyncWebServer.git v3.8.1
clone_pinned ESP32Ping        https://github.com/marian-craciunescu/ESP32Ping.git 1.6
clone_pinned MicroNMEA        https://github.com/stevemarple/MicroNMEA.git      v2.0.6
clone_pinned NimBLE-Arduino   https://github.com/h2zero/NimBLE-Arduino.git      2.3.8
clone_pinned ArduinoJson      https://github.com/bblanchon/ArduinoJson.git      v7.4.2
clone_pinned LinkedList       https://github.com/ivanseidel/LinkedList.git      master
clone_pinned EspSoftwareSerial https://github.com/plerup/espsoftwareserial.git  8.1.0

# Adafruit_TCA8418 is carried in this repository and is not on GitHub under a
# pinnable revision.
rm -rf "${LIB_DIR}/Adafruit_TCA8418"
cp -r "${REPO_DIR}/libraries/Adafruit_TCA8418" "${LIB_DIR}/Adafruit_TCA8418"

# TFT_eSPI is cloned into its own folder and configured here so the build never
# edits a shared checkout.
if [[ ! -d "${LIB_DIR}/TFT_eSPI/.git" ]]; then
  rm -rf "${LIB_DIR}/TFT_eSPI"
  git clone --depth 1 --branch "${TFT_REF}" "${TFT_REPO}" "${LIB_DIR}/TFT_eSPI"
fi

# Same configuration step the release workflow performs.
rm -f "${LIB_DIR}/TFT_eSPI/User_Setup_Select.h"
cp "${REPO_DIR}"/User*.h "${LIB_DIR}/TFT_eSPI/"
sed -i.bak \
  's|^//#include <User_Setup_marauder_mini_v3.h>|#include <User_Setup_marauder_mini_v3.h>|' \
  "${LIB_DIR}/TFT_eSPI/User_Setup_Select.h"
rm -f "${LIB_DIR}/TFT_eSPI/User_Setup_Select.h.bak"

if ! grep -q '^#include <User_Setup_marauder_mini_v3.h>' \
    "${LIB_DIR}/TFT_eSPI/User_Setup_Select.h"; then
  echo "failed to select the Mini v3 TFT_eSPI setup" >&2
  exit 1
fi

# Core 3.3.4 needs the same two adjustments the release workflow applies:
# -zmuldefs for the duplicated C symbols in the ESP32 Arduino libraries, and no
# exceptions so the firmware stays inside its size budget.
CORE_DIR="${HOME}/Library/Arduino15/packages/esp32/hardware/esp32/${CORE_VERSION}"
if [[ ! -d "${CORE_DIR}" ]]; then
  CORE_DIR="${HOME}/.arduino15/packages/esp32/hardware/esp32/${CORE_VERSION}"
fi
if [[ ! -d "${CORE_DIR}" ]]; then
  echo "could not locate the installed esp32 core directory" >&2
  exit 1
fi

if [[ "$(uname -s)" == "Darwin" ]]; then
  SED_INPLACE=(sed -i.bak)
else
  SED_INPLACE=(sed -i.bak)
fi

"${SED_INPLACE[@]}" 's|^compiler.c.elf.extra_flags=.*|compiler.c.elf.extra_flags=-Wl,-zmuldefs |' \
  "${CORE_DIR}/platform.txt"
rm -f "${CORE_DIR}/platform.txt.bak"

# The bundled Arduino libraries are built by a separate step; drop C++ exceptions
# there too so the final link does not pull the exception machinery back in.
find "${HOME}/.arduino15" "${HOME}/Library/Arduino15" \
  -path "*esp32-arduino-libs*" -name cpp_flags -print0 2>/dev/null \
  | xargs -0 -r "${SED_INPLACE[@]}" 's|-fexceptions|-fno-exceptions|g' 2>/dev/null || true
find "${HOME}/.arduino15" "${HOME}/Library/Arduino15" \
  -path "*esp32-arduino-libs*" -name 'cpp_flags.bak' -delete 2>/dev/null || true

echo "compiling ${FQBN}"
"${ARDUINO_CLI}" compile \
  --fqbn "${FQBN}" \
  --libraries "${LIB_DIR}" \
  --warnings none \
  --build-property "compiler.cpp.extra_flags=-DMARAUDER_MINI_V3" \
  --build-property "compiler.c.extra_flags=-DMARAUDER_MINI_V3" \
  --output-dir "${OUT_DIR}" \
  "${SKETCH_DIR}"

APP_IMAGE="${OUT_DIR}/esp32_marauder.ino.bin"
if [[ ! -f "${APP_IMAGE}" ]]; then
  echo "expected ${APP_IMAGE} to exist" >&2
  exit 1
fi

app_size="$(stat -f '%z' "${APP_IMAGE}" 2>/dev/null || stat -c '%s' "${APP_IMAGE}")"
if (( app_size > APPLICATION_LIMIT )); then
  echo "application is ${app_size} bytes and exceeds the ${APPLICATION_LIMIT}-byte slot" >&2
  exit 1
fi

echo "build complete: ${APP_IMAGE} (${app_size}/${APPLICATION_LIMIT} bytes)"
