#!/usr/bin/env python3
"""Assemble the Marauder Mini v3 web-flasher assets from a build.

Reads the Arduino output for the Mini v3 build and writes a self-contained
web-flasher directory:

    web-flasher/index.html              (checked in, not generated here)
    web-flasher/firmware/*.bin          flash segments
    web-flasher/manifest-factory.json   full install: bootloader + table + app
    web-flasher/manifest-update.json    application slot only, keeps settings
    web-flasher/SHA256SUMS

The offsets are not guessed. They are the ones the upstream installer manifest
publishes for `marauder-mini-v3` (project `firmware-manifest.json`, channel
stable): bootloader 0x2000, partition table 0x8000, OTA data 0xE000, application
0x10000. Pass --official-manifest to assert that this build still agrees with
that published layout before anything is written.

Usage:
    tools/package_mini_v3_flasher.py --build-dir <arduino-out> [--core-dir <dir>]
"""

import argparse
import glob
import hashlib
import json
import os
import shutil
import sys

FLASH_SIZE = 8 * 1024 * 1024
CHIP_FAMILY = "ESP32-C5"

SEGMENTS = (
    # role,                offset,   input file name in the Arduino output
    ("bootloader", 0x2000, "esp32_marauder.ino.bootloader.bin"),
    ("partition-table", 0x8000, "esp32_marauder.ino.partitions.bin"),
    ("ota-data", 0xE000, None),  # copied out of the core, name set below
    ("application", 0x10000, "esp32_marauder.ino.bin"),
)
OTA_DATA_NAME = "boot_app0.bin"


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_core_dir(explicit):
    if explicit:
        return explicit
    candidates = [
        os.path.expanduser(
            "~/Library/Arduino15/packages/esp32/hardware/esp32/3.3.4"),
        os.path.expanduser("~/.arduino15/packages/esp32/hardware/esp32/3.3.4"),
    ]
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    sys.exit("could not find the esp32 3.3.4 core; pass --core-dir")


def verify_official_layout(path):
    """Assert this build uses the layout upstream publishes for this target."""
    with open(path) as handle:
        manifest = json.load(handle)

    target = None
    for entry in manifest.get("targets", []):
        if entry.get("id") == "marauder-mini-v3":
            target = entry
            break
    if target is None:
        sys.exit(f"{path} has no marauder-mini-v3 entry")

    published = {
        segment["role"]: segment["offset"]
        for segment in target["flash"]["factory"]["segments"]
    }
    expected = {role: offset for role, offset, _ in SEGMENTS}
    if published != expected:
        sys.exit(f"published layout {published} does not match {expected}")

    print(f"confirmed published layout against {os.path.basename(path)}: "
          + ", ".join(f"{r}=0x{o:X}" for r, o in sorted(published.items())))
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", required=True,
                        help="arduino-cli --output-dir for the Mini v3 build")
    parser.add_argument("--core-dir", default=None,
                        help="esp32 core directory holding tools/partitions")
    parser.add_argument("--out-dir", default=None,
                        help="destination (default: <repo>/web-flasher)")
    parser.add_argument("--official-manifest", default=None,
                        help="upstream firmware-manifest.json to cross-check")
    parser.add_argument("--version", default=None,
                        help="version string for the manifests")
    args = parser.parse_args()

    repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = args.out_dir or os.path.join(repo_dir, "web-flasher")
    firmware_dir = os.path.join(out_dir, "firmware")

    if args.official_manifest:
        verify_official_layout(args.official_manifest)

    core_dir = find_core_dir(args.core_dir)
    ota_source = os.path.join(core_dir, "tools", "partitions", OTA_DATA_NAME)
    if not os.path.isfile(ota_source):
        sys.exit(f"missing {ota_source}")

    version = args.version
    if not version:
        configs = os.path.join(repo_dir, "esp32_marauder", "configs.h")
        with open(configs) as handle:
            for line in handle:
                if line.startswith("#define MARAUDER_VERSION"):
                    version = line.split('"')[1]
                    break
    if not version:
        sys.exit("could not determine the firmware version")
    version = f"{version}-cyberpunk-edition"

    os.makedirs(firmware_dir, exist_ok=True)

    segments = []
    for role, offset, name in SEGMENTS:
        source = ota_source if name is None else os.path.join(args.build_dir, name)
        if not os.path.isfile(source):
            sys.exit(f"missing build artifact for {role}: {source}")
        destination_name = (
            f"marauder-mini-v3-{version}-{role}.bin"
        )
        destination = os.path.join(firmware_dir, destination_name)
        shutil.copyfile(source, destination)
        segments.append({
            "role": role,
            "offset": offset,
            "path": f"firmware/{destination_name}",
            "size": os.path.getsize(destination),
            "sha256": sha256(destination),
        })
        print(f"{role:<16} 0x{offset:05X} {segments[-1]['size']:>9} bytes "
              f"{segments[-1]['sha256'][:16]}...")

    # The application image needs to be flashed at 0x10000 by esp-web-tools, and
    # it must actually be an ESP32 image.
    app = next(s for s in segments if s["role"] == "application")
    with open(os.path.join(out_dir, app["path"]), "rb") as handle:
        if handle.read(1) != b"\xE9":
            sys.exit("application image does not start with the ESP32 magic byte")

    # Merged single-file image, for the desktop flash tools and for anyone who
    # would rather write one file at 0x0. Unwritten space stays 0xFF, matching an
    # erased flash and what `esptool merge_bin --fill-flash-size` emits.
    merged = bytearray(b"\xFF" * FLASH_SIZE)
    for segment in segments:
        with open(os.path.join(out_dir, segment["path"]), "rb") as handle:
            payload = handle.read()
        start = segment["offset"]
        if start + len(payload) > FLASH_SIZE:
            sys.exit(f"{segment['role']} does not fit in {FLASH_SIZE} bytes")
        if merged[start:start + len(payload)] != b"\xFF" * len(payload):
            sys.exit(f"{segment['role']} overlaps another segment at 0x{start:X}")
        merged[start:start + len(payload)] = payload

    merged_name = f"marauder-mini-v3-{version}-factory-8MB.bin"
    merged_path = os.path.join(firmware_dir, merged_name)
    with open(merged_path, "wb") as handle:
        handle.write(merged)

    with open(merged_path, "rb") as handle:
        merged_bytes = handle.read()

    if len(merged_bytes) != FLASH_SIZE:
        sys.exit("merged image is not flash sized")

    # The whole point of the factory image: the same bytes land at the same
    # offsets, and the application really is at 0x10000.
    with open(os.path.join(out_dir, app["path"]), "rb") as handle:
        app_bytes = handle.read()
    app_offset = app["offset"]
    if merged_bytes[app_offset:app_offset + len(app_bytes)] != app_bytes:
        sys.exit("merged image does not carry the application at 0x10000")
    if merged_bytes[app_offset] != 0xE9:
        sys.exit("merged image has no ESP32 application header at 0x10000")

    merged_entry = {
        "role": "merged-factory",
        "offset": 0,
        "path": f"firmware/{merged_name}",
        "size": os.path.getsize(merged_path),
        "sha256": sha256(merged_path),
    }
    print(f"{merged_entry['role']:<16} 0x00000 {merged_entry['size']:>9} bytes "
          f"{merged_entry['sha256'][:16]}...")

    def build_manifest(name, parts, erase_prompt):
        return {
            "name": name,
            "version": version,
            "new_install_prompt_erase": erase_prompt,
            "builds": [{
                "chipFamily": CHIP_FAMILY,
                "parts": [{"path": p["path"], "offset": p["offset"]}
                          for p in parts],
            }],
        }

    factory_parts = [{"path": s["path"], "offset": s["offset"]}
                     for s in segments]

    # The application-only update also rewrites the OTA data segment. Without it
    # a device whose boot slot currently points at app1 (0x340000) would keep
    # booting whatever is in that slot, and the freshly written app at 0x10000
    # would appear to do nothing. The OTA data image points the bootloader at
    # app0; NVS lives at 0x9000 and is untouched, so settings survive.
    ota_data = next(s for s in segments if s["role"] == "ota-data")
    update_parts = [
        {"path": ota_data["path"], "offset": ota_data["offset"]},
        {"path": app["path"], "offset": app["offset"]},
    ]

    manifests = {
        "manifest-factory.json": build_manifest(
            "ESP32 Marauder Mini v3 - Cyberpunk Edition (full install)",
            factory_parts, True),
        "manifest-update.json": build_manifest(
            "ESP32 Marauder Mini v3 - Cyberpunk Edition (application update)",
            update_parts, False),
    }
    for filename, payload in manifests.items():
        with open(os.path.join(out_dir, filename), "w") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
        print(f"wrote {filename}")

    with open(os.path.join(out_dir, "SHA256SUMS"), "w") as handle:
        for entry in segments + [merged_entry]:
            handle.write(f"{entry['sha256']}  {entry['path']}\n")
    print("wrote SHA256SUMS")

    # The flasher page reads this to render its file table, so the sizes and
    # offsets it shows always come from the packaging step rather than being
    # duplicated in the HTML.
    with open(os.path.join(out_dir, "files.json"), "w") as handle:
        json.dump({
            "version": version,
            "chipFamily": CHIP_FAMILY,
            "flashSize": FLASH_SIZE,
            "files": segments + [merged_entry],
        }, handle, indent=2)
        handle.write("\n")
    print("wrote files.json")

    print(f"\nassets in {out_dir}")


if __name__ == "__main__":
    main()
