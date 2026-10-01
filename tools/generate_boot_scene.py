#!/usr/bin/env python3
"""Generate esp32_marauder/BootSceneBitmap.h - the Mini v3 boot-screen scene.

A synthwave sunset: banded sky, a large half-set sun cut by horizontal slits,
a neon skyline of towers framing the sun, lit windows, and a striped reflection
on the water.

The scene is 128 x 72, which is one pixel-sized bitmap for a 128 px panel, and it
is emitted as a run-length table rather than a pixel buffer: the sky bands, the
skyline silhouettes and the water are all long horizontal runs, so runs cost a
few kilobytes where a 16-bit image would cost 18 KB, and drawing is a sequence of
drawFastHLine calls with no intermediate buffer.

Checked before anything is written:
  * every pixel has a colour (no uninitialised cells in the table),
  * the run table round-trips to exactly the composed image,
  * the run count is within the range the renderer's counters can hold.

Run from the repository root:  python3 tools/generate_boot_scene.py [--preview]
"""

import argparse
import math
import os
import sys

W, H = 128, 72
HORIZON = 58          # first row of water
SUN_RADIUS = 28
SUN_CX, SUN_CY = 64, HORIZON

# Palette: index -> (name, #rrggbb). Kept in step with NeonPalette.h so the boot
# scene is drawn from the same neon theme as the rest of the UI.
PALETTE = [
    ("skyTop",   "#140A2C"),
    ("skyUpper", "#2B1054"),
    ("skyMid",   "#4E1379"),
    ("skyLower", "#7C1B72"),
    ("skyGlow",  "#B22765"),
    ("skyHot",   "#E24761"),
    ("skyRim",   "#FF7A50"),
    ("sunCore",  "#FFE873"),
    ("sunMid",   "#FFB43C"),
    ("farTower", "#3A1668"),
    ("nearTower", "#07040F"),
    ("winCyan",  "#29E4FF"),
    ("winMagenta", "#FF3DD6"),
    ("winAmber", "#FFA23A"),
    ("water",    "#0B0618"),
    ("reflect",  "#FF6A9E"),
]

BANDS = ["skyTop", "skyUpper", "skyMid", "skyLower", "skyGlow", "skyHot", "skyRim"]

# Near skyline: tall towers at both edges, deliberately low across the middle so
# the sun reads. (x, width, roof_y, antenna_height)
NEAR_TOWERS = [
    (0, 12, 38, 5), (12, 10, 45, 0), (22, 9, 35, 6),
    (31, 11, 50, 0), (42, 10, 52, 0), (52, 12, 51, 0), (64, 12, 53, 0),
    (76, 10, 50, 0), (86, 11, 48, 4),
    (97, 12, 36, 6), (109, 10, 43, 0), (119, 9, 34, 7),
]

FAR_TOWERS = [(0, 18, 51), (18, 16, 49), (34, 20, 53), (54, 18, 50),
              (72, 18, 52), (90, 20, 49), (110, 18, 51)]

OUTPUT = os.path.join("esp32_marauder", "BootSceneBitmap.h")


def compose():
    index = {name: i for i, (name, _) in enumerate(PALETTE)}
    g = [[index["skyTop"]] * W for _ in range(H)]

    # Sky bands, then water.
    for y in range(HORIZON):
        colour = index[BANDS[min(y * len(BANDS) // HORIZON, len(BANDS) - 1)]]
        for x in range(W):
            g[y][x] = colour
    for y in range(HORIZON, H):
        for x in range(W):
            g[y][x] = index["water"]

    def band_at(y):
        return index[BANDS[min(y * len(BANDS) // HORIZON, len(BANDS) - 1)]]

    # Sun, clipped to above the horizon so it never bleeds into the water.
    for y in range(HORIZON):
        for x in range(W):
            d = math.hypot(x + 0.5 - SUN_CX, y + 0.5 - SUN_CY)
            if d <= SUN_RADIUS:
                g[y][x] = index["sunCore"] if d <= SUN_RADIUS * 0.58 else index["sunMid"]

    # Horizontal slits through the lower half of the disc.
    for slit in range(40, HORIZON, 5):
        for y in range(slit, min(slit + 3, HORIZON)):
            for x in range(W):
                if math.hypot(x + 0.5 - SUN_CX, y + 0.5 - SUN_CY) <= SUN_RADIUS:
                    g[y][x] = band_at(y)

    # Stars in the dark upper sky: fixed positions, never regenerated at boot.
    stars = [(9, 11), (24, 6), (37, 18), (48, 9), (61, 4), (72, 15), (84, 7),
             (95, 20), (106, 12), (118, 5), (15, 24), (52, 26), (110, 27),
             (30, 3), (77, 25)]
    for (sx, sy) in stars:
        if 0 <= sx < W and 0 <= sy < HORIZON:
            g[sy][sx] = index["sunCore"]

    # Horizon glow.
    for y in (HORIZON - 1, HORIZON - 2):
        for x in range(W):
            g[y][x] = index["skyRim"]

    # Far towers: the distant layer, drawn behind the near skyline.
    for (bx, bw, roof) in FAR_TOWERS:
        for y in range(roof, HORIZON):
            for x in range(bx, min(bx + bw, W)):
                if g[y][x] not in (index["sunCore"], index["sunMid"]):
                    g[y][x] = index["farTower"]

    # Near towers plus their antennae.
    for (bx, bw, roof, antenna) in NEAR_TOWERS:
        for y in range(roof, HORIZON):
            for x in range(bx, min(bx + bw, W)):
                g[y][x] = index["nearTower"]
        if antenna:
            ax = bx + bw // 2
            for y in range(max(0, roof - antenna), roof):
                g[y][ax] = index["nearTower"]

    # Lit windows, in a fixed pattern so the scene is identical every boot.
    window_colours = ["winCyan", "winMagenta", "winAmber"]
    seed = 20261001
    for (bx, bw, roof, _antenna) in NEAR_TOWERS:
        x0, x1 = bx + 2, min(bx + bw - 3, W - 3)
        row = 0
        for wy in range(roof + 3, HORIZON - 2, 4):
            row += 1
            for wx in range(x0 + (row % 2) * 2, x1, 4):
                seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
                if (seed >> 16) % 10 < 8:
                    colour = index[window_colours[(seed >> 9) % 3]]
                    for yy in range(wy, min(wy + 2, HORIZON)):
                        for xx in range(wx, min(wx + 2, W)):
                            g[yy][xx] = colour

    # Water: a striped reflection under the sun, plus two broken light streaks.
    for i, y in enumerate(range(HORIZON, H, 2)):
        depth = (y - HORIZON) / float(H - HORIZON)
        half = max(1, int(15 * (1 - depth ** 0.5)))
        colour = index[["sunCore", "sunMid", "reflect"][i % 3]]
        for x in range(SUN_CX - half, SUN_CX + half + 1):
            if 0 <= x < W:
                g[y][x] = colour
    for y, (x0, x1) in ((HORIZON + 5, (4, 40)), (HORIZON + 9, (86, 124))):
        for x in range(x0, x1):
            g[y][x] = index["reflect"]

    return g


def encode_runs(g):
    """One entry per horizontal run: (y, x, length, palette index)."""
    runs = []
    for y in range(H):
        x = 0
        while x < W:
            colour = g[y][x]
            length = 1
            while x + length < W and g[y][x + length] == colour:
                length += 1
            runs.append((y, x, length, colour))
            x += length
    return runs


def decode_runs(runs):
    g = [[None] * W for _ in range(H)]
    for (y, x, length, colour) in runs:
        for i in range(length):
            g[y][x + i] = colour
    return g


def preview(g):
    chars = {i: " .:-=+*#%@ABCDEFG"[i] for i in range(len(PALETTE))}
    return "\n".join("".join(chars[g[y][x]] for x in range(W)) for y in range(H))


def render_header(runs):
    palette_lines = "\n".join(
        f"constexpr uint16_t kScene{name[0].upper()}{name[1:]:<14} = 0x{value:04X};"
        for name, value in ((n, rgb565(h)) for n, h in PALETTE))

    palette_array = "\n".join(
        f"  kScene{name[0].upper()}{name[1:]},  // {index:>2}  {name}"
        for index, (name, _hex) in enumerate(PALETTE))

    run_lines = []
    for i in range(0, len(runs), 4):
        chunk = runs[i:i + 4]
        run_lines.append("  " + " ".join(
            f"{{{y:>2}, {x:>3}, {length:>3}, {colour:>2}}}," for (y, x, length, colour) in chunk))

    return f"""#pragma once

#include <stdint.h>

// Synthwave sunset boot scene for the Marauder Mini v3, {W} x {H}, generated by
// tools/generate_boot_scene.py. The generator asserts that the run table below
// round-trips to exactly the composed image before writing this file.
//
// Stored as horizontal runs rather than pixels: the sky bands, tower
// silhouettes and water are long runs, so this costs a few kilobytes instead of
// the 18 KB a 16-bit pixel buffer would need, and it draws as a sequence of
// drawFastHLine calls with no intermediate buffer.
//
// Run format: {{y, x, length, palette index}}.
namespace marauder {{

constexpr uint16_t kBootSceneWidth = {W};
constexpr uint16_t kBootSceneHeight = {H};
constexpr uint16_t kBootSceneRunCount = {len(runs)};

// Palette, in the same neon family as NeonPalette.h.
{palette_lines}

// Indexed by BootSceneRun::colour.
static const uint16_t kScenePalette[{len(PALETTE)}] = {{
{palette_array}
}};

struct BootSceneRun {{
  uint8_t y;
  uint8_t x;
  uint8_t length;
  uint8_t colour;
}};

static const BootSceneRun kBootSceneRuns[kBootSceneRunCount] = {{
{chr(10).join(run_lines)}
}};

}}  // namespace marauder
"""


def rgb565(hex_string):
    value = int(hex_string.lstrip("#"), 16)
    r, g, b = (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    g = compose()

    # Every pixel must have a colour.
    for y in range(H):
        for x in range(W):
            if g[y][x] is None:
                sys.exit(f"unpainted pixel at ({x}, {y})")

    runs = encode_runs(g)
    if decode_runs(runs) != g:
        sys.exit("run table does not round-trip to the composed image")
    if len(runs) > 4096:
        sys.exit(f"{len(runs)} runs is more than the render loop should carry")
    for (y, x, length, colour) in runs:
        if not (0 <= x < W and 0 < length <= W and x + length <= W):
            sys.exit(f"run out of bounds: {y},{x},{length},{colour}")
        if not (0 <= colour < len(PALETTE)):
            sys.exit(f"palette index out of range: {colour}")

    print(preview(g))
    on_colours = {}
    for (y, x, length, colour) in runs:
        on_colours[colour] = on_colours.get(colour, 0) + length
    total = float(W * H)
    print("\nshares:", {PALETTE[k][0]: round(v * 100.0 / total, 1)
                        for k, v in sorted(on_colours.items(), key=lambda kv: -kv[1])})
    print(f"{len(runs)} runs", file=sys.stderr)

    if args.preview:
        return

    with open(OUTPUT, "w") as handle:
        handle.write(render_header(runs))
    print(f"wrote {OUTPUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
