# Marauder Mini v3 web flasher

Flashing happens over USB from the browser using ESP Web Tools (vendored in
`vendor/`, so it works offline).

## Run it

Web Serial is only available in a secure context, which includes
`http://localhost`. Opening `index.html` from Finder will not work.

```sh
cd web-flasher
python3 -m http.server 8000
```

Then open <http://localhost:8000/> in **Chrome** or **Edge** on a desktop.

1. Plug the Mini v3 in with a data-capable USB-C cable.
2. Pick an install button and select the board's serial port.
3. If no port appears, hold **BOOT** while plugging the board in.

**Application update** preserves settings. **Full install** rewrites the
bootloader, partition table and OTA data as well, and replaces everything on the
flash.

## Contents

| file | what it is |
|---|---|
| `manifest-update.json` | OTA data + application. Keeps settings. |
| `manifest-factory.json` | bootloader + partition table + OTA data + application. |
| `files.json` | sizes, offsets and hashes, rendered by the page. |
| `SHA256SUMS` | the same hashes for `shasum -a 256 -c`. |
| `firmware/*.bin` | the flash segments. |
| `firmware/*-factory-8MB.bin` | merged 8 MB image for `esptool` / Flash Download Tool. |

Regenerate after a build:

```sh
python3 tools/package_mini_v3_flasher.py \
  --build-dir ../miniv3-build/out \
  --official-manifest /path/to/upstream/firmware-manifest.json
```

Passing `--official-manifest` makes the script assert the offsets it is about to
use against the layout upstream publishes for this target, and fail if they
differ.

See `../docs/build-notes.md` for what this firmware changes and what is not verified.
