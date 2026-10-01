# tools

Scripts used to build and package this firmware. They operate on a checkout of
[ESP32 Marauder](https://github.com/justcallmekoko/ESP32Marauder) with the changes from
[`patches/cyberpunk-edition.patch`](../patches/cyberpunk-edition.patch) applied.

| file | what it does |
|---|---|
| `build_mini_v3.sh` | Builds the Mini v3 target with `arduino-cli` and the `esp32:esp32@3.3.4` core, pinned library versions, `-zmuldefs` and exceptions off. Writes to `../miniv3-build/out`. |
| `package_mini_v3_flasher.py` | Turns the build output into the web flasher: copies the segments, writes both manifests and a checksum list, builds the merged 8 MB factory image, and checks the whole thing against the official `firmware-manifest.json` so the flash layout cannot drift. |
| `generate_neon_palette.py` | Generates `NeonPalette.h`. **Refuses to emit a palette** that breaks either rule: every colour must clear a contrast floor against black, and no two saturated entries may sit within 30° of hue. Failing loudly is the point — both rules were learned from a build that shipped unreadable text and two indistinguishable colours. |
| `generate_boot_scene.py` | Generates `BootSceneBitmap.h`, the synthwave sunset on the boot splash, as a table of horizontal runs (about 1.7 KB rather than an 18 KB pixel buffer). |
| `User_Setup_marauder_mini_v3.h` | The TFT_eSPI panel configuration for this board: 128 × 128 ST7735, BGR order, green tab 3, backlight active low, 20 MHz SPI. |

## Apple silicon note

The `ctags` bundled with `arduino-cli` is x86_64-only, so Rosetta 2 is required
(`softwareupdate --install-rosetta --agree-to-license`). Substituting a native `ctags`
build breaks `.ino` prototype generation in a way that surfaces as unrelated errors.
