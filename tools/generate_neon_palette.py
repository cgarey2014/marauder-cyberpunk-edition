#!/usr/bin/env python3
"""Generate esp32_marauder/NeonPalette.h.

The Mini v3 UI is rethemed to a neon cyberpunk palette. Two things make that safe
to claim rather than hope for:

  * the panel is driven with native RGB565 (this firmware builds no sprites and
    never calls setColorDepth), so a colour constant is shown as written - there
    is no RGB332 quantisation to reason about;
  * every entry is checked with the WCAG relative-luminance contrast formula
    against the backgrounds it is actually drawn on, and the generator refuses to
    emit a palette where body text fails.

The theme is applied by naming colours `NEON_<NAME>` in the firmware instead of
`TFT_<NAME>`. On the Mini v3 those expand to the neon entries; on every other
target they expand to the stock TFT_eSPI macro, so no other board's firmware
changes by a single byte. The mapping is kept strictly 1:1 with the legacy token
names - collapsing two legacy names onto one macro would silently change the
value used on those other targets.
"""

import argparse
import os
import re
import sys

# --- the neon palette -----------------------------------------------------------------
# Colours are taken from the reference artwork the user supplied (a synthwave poster).
# Palette extraction read the image's saturated pixels and clustered them by hue:
#
#   magenta/pink  #ED35BC  27.6%     yellow    #F4C139   9.6%
#   cyan          #45D8E2  17.2%     orange    #F09651   8.5%
#   rose/red      #E52565  16.4%     blue-grey #39516E   5.5%
#   purple        #8D6AA3  12.2%     mint/teal #4EACA0   1.4%
#
# Those hues are the families below. The artwork's blue-grey and purple are too dark to
# read on a black panel and it has almost no green, so those entries are lifted or
# supplied while staying in the artwork's families.
#
# TWO RULES, both of which the generator enforces:
#
# 1. Every entry must be readable as text on black. MenuFunctions::getColor() hands
#    these to menu *labels*, so each one is drawn colour-on-black when unselected and
#    black-on-colour when selected. Contrast is symmetric, so one floor covers both and
#    there is no such thing as a colour that is "only a background". An earlier palette
#    exempted two entries as fills, and TFTNAVY - a text colour for "Add SSIDs" and
#    "Select APs" - landed at 1.33:1, invisible in both states.
#
# 2. Saturated entries must be far apart in hue. Two entries ~10 degrees apart read as
#    the same colour on a 128 px panel, which is how WiFi and Bluetooth ended up
#    indistinguishable in the wardriving display (mint green vs cyan). Nothing here is
#    within MIN_HUE_GAP degrees of anything else.
#
# Where two legacy names mean the same thing they share one entry, so "same kind of
# item, same colour" holds: TFTNAVY and TFTBLUE are both informational blue, TFTOLIVE
# and TFTGREENYELLOW are both lime, and so on.
#
# name                rgb        note
PALETTE = [
    ("kNeonBody",    "0xEAF7FF", "primary body and menu text, cool white"),
    ("kNeonAccent",  "0x4FE3EE", "image cyan - scanners, primary accents"),
    ("kNeonOk",      "0x4DFF7A", "hacker green - GPS, success, WiFi, connected"),
    ("kNeonWarn",    "0xFF8C55", "image orange - files, SD, uploads, counters"),
    ("kNeonAlarm",   "0xFF3355", "cyberpunk red - attacks, errors, warnings"),
    ("kNeonHot",     "0xED4FD0", "image magenta - recon, highlights, selection"),
    ("kNeonAlert",   "0xFFE633", "image yellow - choices, confirmations, attention"),
    ("kNeonInfo",    "0x7FA8FF", "image blue-grey, lifted - wardriving, info"),
    ("kNeonLime",    "0xA6F53C", "warning lime - fox hunt, geofences"),
    ("kNeonPurple",  "0xB071F0", "image purple, lifted - Bluetooth"),
    ("kNeonSky",     "0x9FE4FF", "pale cyan tint - sniffers (low saturation, see rule 2)"),
    ("kNeonSilver",  "0xCFDCEE", "neutral - settings and configuration"),
    ("kNeonMuted",   "0x93A2C0", "de-emphasised - Back and exit items, still readable"),
    ("kNeonWhite",   "0xFFFFFF", "maximum emphasis"),
]

STATUS_BAR = ("kNeonStatusBar", "0x140B2B")
TITLE_TEXT = ("kNeonTitleText", "0x06060B")
BACKGROUND_BLACK = 0x0000

# --- legacy TFT_eSPI names, mirrored so this header has no library dependency ----------
# The value is only used for the firmware-side static_assert in Display.cpp; the
# header itself only needs the name and its neon target.
LEGACY = [
    # Names that mean the same kind of thing share an entry on purpose, so that menu
    # items of one kind render in one colour. Every value here is the stock TFT_eSPI
    # value, used for the firmware-side static_assert and for the off-target arm.
    ("TFT_NAVY",        0x000F, "kNeonInfo"),    # informational blue (a TEXT colour)
    ("TFT_BLUE",        0x001F, "kNeonInfo"),
    ("TFT_DARKCYAN",    0x03EF, "kNeonAccent"),
    ("TFT_CYAN",        0x07FF, "kNeonAccent"),
    ("TFT_DARKGREEN",   0x03E0, "kNeonOk"),
    ("TFT_GREEN",       0x07E0, "kNeonOk"),
    ("TFT_MAROON",      0x7800, "kNeonAlarm"),   # a TEXT colour, not a deep fill
    ("TFT_RED",         0xF800, "kNeonAlarm"),
    ("TFT_PURPLE",      0x780F, "kNeonPurple"),
    ("TFT_VIOLET",      0x915C, "kNeonPurple"),
    ("TFT_OLIVE",       0x7BE0, "kNeonLime"),
    ("TFT_GREENYELLOW", 0xB7E0, "kNeonLime"),
    ("TFT_LIME",        0x97E0, "kNeonLime", "0x97E0"),
    ("TFT_LIGHTGREY",   0xD69A, "kNeonBody"),
    ("TFT_SILVER",      0xC618, "kNeonSilver"),
    ("TFT_DARKGREY",    0x7BEF, "kNeonMuted"),
    ("TFT_MAGENTA",     0xF81F, "kNeonHot"),
    ("TFT_PINK",        0xFE19, "kNeonHot"),
    ("TFT_YELLOW",      0xFFE0, "kNeonAlert"),
    ("TFT_GOLD",        0xFEA0, "kNeonAlert"),
    ("TFT_ORANGE",      0xFDA0, "kNeonWarn"),
    ("TFT_SKYBLUE",     0x867D, "kNeonSky"),
    ("TFT_WHITE",       0xFFFF, "kNeonWhite"),
]

OUTPUT = os.path.join("esp32_marauder", "NeonPalette.h")


def to_rgb565(hex_string):
    value = int(hex_string.lstrip("#"), 16)
    r, g, b = (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def from_rgb565(packed):
    r5, g6, b5 = (packed >> 11) & 0x1F, (packed >> 5) & 0x3F, packed & 0x1F
    return ((r5 << 3) | (r5 >> 2), (g6 << 2) | (g6 >> 4), (b5 << 3) | (b5 >> 2))


MIN_HUE_GAP = 30.0   # degrees between any two saturated palette entries


def hsv(packed):
    """Hue in degrees, saturation and value in 0..1, from a packed RGB565 value."""
    r, g, b = (c / 255.0 for c in from_rgb565(packed))
    mx, mn = max(r, g, b), min(r, g, b)
    delta = mx - mn
    if delta == 0:
        return 0.0, 0.0, mx
    if mx == r:
        hue = (60.0 * ((g - b) / delta) + 360.0) % 360.0
    elif mx == g:
        hue = 60.0 * ((b - r) / delta) + 120.0
    else:
        hue = 60.0 * ((r - g) / delta) + 240.0
    return hue, delta / mx, mx


def relative_luminance(packed):
    r, g, b = (c / 255.0 for c in from_rgb565(packed))
    def channel(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(a, b):
    la, lb = relative_luminance(a), relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def render(checks):
    palette_lines = "\n".join(
        f"constexpr uint16_t {name:<16} = 0x{to_rgb565(rgb):04X};  // {rgb}  {note}"
        for name, rgb, note in PALETTE)

    legacy_lines = "\n".join(
        f"constexpr uint16_t kLegacy{entry[0][4:].title():<14} = 0x{entry[1]:04X};  // {entry[0]}"
        for entry in LEGACY if len(entry) == 3)

    neon_arm = "\n".join(
        f"  #define NEON_{entry[0][4:]:<15} marauder::{entry[2]}"
        for entry in LEGACY)
    stock_arm = "\n".join(
        f"  #define NEON_{entry[0][4:]:<15} {entry[3] if len(entry) > 3 else entry[0]}"
        for entry in LEGACY)

    verdict = "\n".join(
        f"//   {name:<16} black {checks[name]['black']:>6.2f}:1   "
        f"status bar {checks[name]['statusbar']:>6.2f}:1"
        for name, *_rest in PALETTE)

    return f"""#pragma once

#include <stdint.h>

// Neon cyberpunk UI palette for the Marauder Mini v3.
//
// Generated by tools/generate_neon_palette.py, which computes each entry's WCAG
// contrast ratio against the backgrounds it is actually drawn on and refuses to
// emit a palette where body text fails. Do not hand-edit: change the generator.
//
// The panel is driven with native RGB565 - this firmware creates no sprites and
// never calls setColorDepth - so these constants reach the display unquantised.
//
// How the theme is applied: the firmware sources name colours NEON_<NAME> rather
// than TFT_<NAME>. On the Mini v3 those expand to the neon entries below; on any
// other target they expand to the stock TFT_eSPI macro, so this file changes
// nothing at all for other boards. The mapping is deliberately one macro per
// legacy token name - merging two legacy names onto one macro would change the
// value those other targets use.
//
// Measured contrast:
{verdict}

namespace marauder {{

// --- neon palette --------------------------------------------------------------------
{palette_lines}
constexpr uint16_t kNeonBlack          = 0x0000;  // panel background

// --- status bar and title text -------------------------------------------------------
// The stock status bar is flat mid-grey (0x4A49). A deep indigo keeps the neon text
// on it high contrast and makes the bar read as part of the theme.
constexpr uint16_t {STATUS_BAR[0]:<16} = 0x{to_rgb565(STATUS_BAR[1]):04X};
constexpr uint16_t {TITLE_TEXT[0]:<16} = 0x{to_rgb565(TITLE_TEXT[1]):04X};  // text on a bright title bar

// --- stock values, mirrored for the firmware-side static_assert -----------------------
{legacy_lines}

}}  // namespace marauder

// --- colour names used by the firmware ------------------------------------------------
#if defined(MARAUDER_MINI_V3)
{neon_arm}
#else
{stock_arm}
#endif
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    checks = {}
    failures = []

    # Which legacy names share one colour, for the review printout below.
    shared = {}
    for _entry in LEGACY:
        shared.setdefault(_entry[2], []).append(_entry[0].replace("TFT_", ""))

    for name, rgb, _note in PALETTE:
        packed = to_rgb565(rgb)
        checks[name] = {
            "black": contrast_ratio(packed, BACKGROUND_BLACK),
            "statusbar": contrast_ratio(packed, to_rgb565(STATUS_BAR[1])),
        }
        # Every colour is used as text somewhere, so every colour has to pass - there
        # is no "fills only" exemption. That exemption is what shipped a dark navy
        # that made "Add SSIDs" and "Select APs" invisible.
        if checks[name]["black"] < 4.5:
            failures.append(
                f"{name} on black is {checks[name]['black']:.2f}:1 (< 4.5) - every "
                "colour is used as text somewhere in the UI")
        if checks[name]["statusbar"] < 4.5:
            failures.append(
                f"{name} on the status bar is {checks[name]['statusbar']:.2f}:1 (< 4.5)")

    if checks["kNeonBody"]["black"] < 10.0:
        failures.append(f"kNeonBody on black is {checks['kNeonBody']['black']:.2f}:1, "
                        "want >= 10 - body text must be the brightest thing on screen")

    # Selected menu rows are filled with the node colour and written in black, and
    # title bars do the same, so every colour must also carry dark text.
    for name, rgb, _note in PALETTE:
        ratio = contrast_ratio(to_rgb565(rgb), to_rgb565(TITLE_TEXT[1]))
        if ratio < 4.5:
            failures.append(f"{name} cannot carry dark text ({ratio:.2f}:1)")

    # The macro mapping must be 1:1 with the legacy token names, and those names
    # must not collide in value (a collision would mean one of them is wrong).
    palette_names = {name for name, *_rest in PALETTE}
    macro_names, seen_values = set(), {}
    for entry in LEGACY:
        name, value, neon = entry[0], entry[1], entry[2]
        macro = f"NEON_{name[4:]}"
        if macro in macro_names:
            failures.append(f"duplicate macro {macro}")
        macro_names.add(macro)
        if neon not in palette_names:
            failures.append(f"{name} maps to unknown palette entry {neon}")
        if value in seen_values:
            failures.append(f"{name} has the same value as {seen_values[value]}")
        seen_values[value] = name

    # Rule 2: saturated entries must be far enough apart in hue to be told apart on a
    # 128 px panel. This is the check that the WiFi-vs-Bluetooth collision needed.
    saturated = []
    for name, rgb, _note in PALETTE:
        packed = to_rgb565(rgb)
        hue, sat, _val = hsv(packed)
        if sat >= 0.5:
            saturated.append((name, hue))
    for i in range(len(saturated)):
        for j in range(i + 1, len(saturated)):
            (n1, h1), (n2, h2) = saturated[i], saturated[j]
            gap = abs(h1 - h2)
            gap = min(gap, 360.0 - gap)
            if gap < MIN_HUE_GAP:
                failures.append(
                    f"{n1} and {n2} are only {gap:.0f} degrees apart in hue "
                    f"(< {MIN_HUE_GAP}) - they will read as the same colour")

    # Nothing may be emitted as a value wider than the type it is stored in.
    for name, rgb, _note in PALETTE:
        if to_rgb565(rgb) > 0xFFFF:
            failures.append(f"{name} does not fit a uint16_t")
    for label, rgb in (STATUS_BAR, TITLE_TEXT):
        packed = to_rgb565(rgb)
        if packed > 0xFFFF:
            failures.append(f"{label} does not fit a uint16_t")
        if packed == 0:
            failures.append(f"{label} packs to zero")

    if failures:
        print("palette rejected:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        sys.exit(2)

    with open(OUTPUT, "w") as handle:
        handle.write(render(checks))

    for name, *_rest in PALETTE:
        hue, sat, _val = hsv(to_rgb565(dict((n, r) for n, r, _x in PALETTE)[name]))
        print(f"  {name:<16} black {checks[name]['black']:>6.2f}:1  "
              f"hue {hue:>5.0f}  sat {sat:.2f}")
    print("\nshared roles (several legacy names, one colour):", file=sys.stderr)
    for neon, names in sorted(shared.items()):
        if len(names) > 1:
            print(f"  {neon:<14} <- {', '.join(sorted(names))}", file=sys.stderr)
    print(f"\n{len(LEGACY)} legacy colour names mapped -> {OUTPUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
