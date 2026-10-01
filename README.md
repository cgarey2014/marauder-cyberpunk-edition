<div align="center">

<img src="assets/header.svg" alt="Marauder Mini v3 — Cyberpunk Edition" width="100%">

### A neon retheme and 128 px text-fitting rebuild of **ESP32 Marauder**, for the Marauder Mini v3.

[![Upstream](https://img.shields.io/badge/upstream-ESP32Marauder-4FE3EE?style=for-the-badge&labelColor=140B2B)](https://github.com/justcallmekoko/ESP32Marauder)
[![Board](https://img.shields.io/badge/board-Mini%20v3%20%C2%B7%20ESP32--C5-4DFF7A?style=for-the-badge&labelColor=140B2B)](#what-this-is)
[![Base](https://img.shields.io/badge/base-v1.17.0-FFE633?style=for-the-badge&labelColor=140B2B)](#what-changed)
[![License](https://img.shields.io/badge/license-MIT-ED4FD0?style=for-the-badge&labelColor=140B2B)](LICENSE)

**Flash it from your browser** → [open the web flasher](https://cgarey2014.github.io/marauder-cyberpunk-edition/web-flasher/)

</div>

---

## What this is

A personal build of [justcallmekoko's ESP32 Marauder](https://github.com/justcallmekoko/ESP32Marauder) for **one board**: the **Marauder Mini v3**, the ESP32-C5 generation with a 128 × 128 ST7735 panel.

It exists because the stock firmware targets that panel without quite fitting it — long values were clipped mid-string, and the interface is monochrome enough that a screen of data is hard to read at a glance. This build fixes the fitting, gives the UI a neon cyberpunk palette derived from a reference image, and makes colour mean something.

**Everything that makes the Marauder work is upstream's.** The WiFi and Bluetooth tooling, the CLI, the wardriving upload, the Evil Portal, the GPS stack, the drivers — none of that is mine. See [Attribution](#attribution). What is different is listed below, in full, and the changes are also in [`patches/`](patches/) as a diff against upstream v1.17.0.

## What changed

| area | change |
|---|---|
| **Text fitting** | On a 128 px panel a row holds 21 characters, and upstream clipped anything longer. Long values now wrap onto the rows below instead of vanishing, screen titles drop to a smaller font when they would overrun, and the Follow list shows the whole MAC instead of only its second half. |
| **GPS screens** | The date/time and UTC stamps (23–24 chars) were being cut off. Every GPS line wraps now, the row budget is asserted by a test, and the raw NMEA screen wraps its 60–80 character sentences instead of clipping them at 21. |
| **Colouring** | Menus colour by *what an item is* — tags one colour, Bluetooth another, passive monitors another, attacks another — so like items match and no submenu is monochrome. Data screens dim the field name and colour the value by its kind. |
| **Palette** | Neon cyberpunk, built from a reference image: cyan, hacker green, orange, cyberpunk red, magenta, yellow, periwinkle, lime, purple on black, with a deep indigo status bar. |
| **Boot splash** | A synthwave sunset with the **CYBERPUNK EDITION** wordmark and a "Jacking in..." tagline. |
| **Brightness** | Backlight level in **Device → Brightness**, using the 5-way switch, saved to NVS. |
| **Status bar** | GPS in three states (no module / no fix / fix) and SD green-or-red, so a failure is obvious before it bites. |

### The palette, and the two rules behind it

Both rules are enforced by the generator (`tools/generate_neon_palette.py`) rather than by eye, because both were learned the hard way:

1. **Every colour must be readable as text.** The firmware hands these colours to *menu labels*, so each one is drawn colour-on-black when unselected and black-on-colour when selected — which means a single contrast floor covers both. A colour that looked like a harmless dark fill turned out to be the text colour for a menu, and shipped invisible.
2. **Saturated colours must be far apart in hue.** Two entries ten degrees apart read as one colour on a small panel. Nothing in the palette is within 30° of anything else.

| role | colour | contrast on black |
|---|---|---|
| body / menu text | `#EAF7FF` | 19.4:1 |
| accent — scanners, WiFi | `#4FE3EE` | 13.5:1 |
| success — WiFi frames, GPS | `#4DFF7A` | 15.9:1 |
| warning — files, SD, uploads | `#FF8C55` | 9.2:1 |
| attacks, errors | `#FF3355` | 5.8:1 |
| highlights, recon | `#ED4FD0` | 6.7:1 |
| attention, choices | `#FFE633` | 16.7:1 |
| info, wardriving | `#7FA8FF` | 9.0:1 |
| fox hunt, geofences | `#A6F53C` | 16.0:1 |
| Bluetooth | `#B071F0` | 6.7:1 |
| configuration | `#CFDCEE` | 15.4:1 |
| Back / exit rows | `#93A2C0` | 8.2:1 |

## Flash it

**[Open the web flasher](https://cgarey2014.github.io/marauder-cyberpunk-edition/web-flasher/)** in Chrome or Edge (Web Serial needs a Chromium browser), plug the board in over USB-C, and pick the port.

- **Application update** — replaces the app only. **Keeps your settings**, saved WiFi, and Evil Portal templates. Use this one.
- **Full install (factory image)** — writes the whole 8 MB flash. For a blank or unknown board; wipes settings.

If no port appears, unplug and hold **BOOT** while plugging back in.

**The flash layout is byte-identical to the official v1.17.0 Mini v3 release** — same bootloader, same partition table, same OTA data — so the [official JCMK installer](https://justcallmekoko.github.io/MarauderInstaller/) remains a valid recovery path at any time.

## Build it

Requires `arduino-cli` with the `esp32:esp32@3.3.4` core, and Rosetta 2 on Apple silicon (the bundled `ctags` is x86_64-only; substituting a native one corrupts `.ino` prototype generation).

```bash
tools/build_mini_v3.sh              # writes ../miniv3-build/out
python3 tools/package_mini_v3_flasher.py --build-dir ../miniv3-build/out
~/myrepos/espvenv/bin/pio test -e native    # 127 host tests
```

The host tests cover the text-fitting helpers, the palette rules, the GPS screen row budget, and the splash layout — the things that are easy to get wrong and invisible until they are on a device.

Reverting is as easy as not using it: every change is confined to the `MARAUDER_MINI_V3` target or gated behind a macro that expands to the upstream value elsewhere, so other boards build and behave exactly as upstream does.

## Attribution

This is a derivative work. It would not exist without:

- **[ESP32 Marauder](https://github.com/justcallmekoko/ESP32Marauder)** by **[justcallmekoko](https://github.com/justcallmekoko)** — the firmware, drivers, CLI, and every tool in it. MIT licensed; the original copyright notice is preserved in [`LICENSE`](LICENSE).
- **Marauder Mini v3** hardware, also by justcallmekoko / JCMK LLC. Not affiliated with, endorsed by, or supported by him. **Do not report problems with this build upstream.**
- The **neon palette** is derived from a colour reference image supplied by the device owner. No third-party artwork is redistributed here; the SVG header and the palette are original to this repo.

Modifications copyright © 2026 [cgarey2014](https://github.com/cgarey2014), released under the same MIT terms.

## Disclaimer

ESP32 Marauder is an **offensive security tool**. Deauthentication, beacon spam, handshake capture and the like are illegal to use against networks you do not own or lack written permission to test. Laws vary by country and by state.

This repository is a **UI fork** — it changes how the firmware looks and fits, not what it does. Nothing here adds capability. Use it on your own hardware and your own networks, or in a lab you are authorised to test.

The authors and contributors accept no liability for misuse or for any damage arising from it.
