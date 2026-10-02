#!/usr/bin/env python3
"""Resolve ragbaz terminal tokens and print a theme's palette.

This is the reference implementation of "role -> colour, best available form":
the ladder is truecolor -> ansi256 -> ansi16 -> none, and the off switch is
NO_COLOR / FORCE_COLOR / TERM=dumb / isatty, in that order of deference.

Reads the real token files next to it. Stdlib only (3.11+ for tomllib).

    python3 examples/tokens.py
    python3 examples/tokens.py --theme ragbaz-night
    python3 examples/tokens.py --explain
    python3 examples/tokens.py --color-mode ansi256 --spacing
    python3 examples/tokens.py --glyphs
"""

from __future__ import annotations

import argparse
import os
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
TOKENS = tomllib.loads((HERE / "tokens.toml").read_text())
THEMES = tomllib.loads((HERE / "themes.toml").read_text())

# --- the xterm 16-colour base palette, for the bottom rung of the ladder ----
ANSI16 = [
    "#000000", "#cd0000", "#00cd00", "#cdcd00", "#0000ee", "#cd00cd",
    "#00cdcd", "#e5e5e5", "#7f7f7f", "#ff0000", "#00ff00", "#ffff00",
    "#5c5cff", "#ff00ff", "#00ffff", "#ffffff",
]
CUBE = (0, 95, 135, 175, 215, 255)


def rgb(hex_colour: str) -> tuple[int, int, int]:
    h = hex_colour.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def dist(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    """Weighted distance. Green counts most, matching human sensitivity."""
    r, g, bl = (x - y for x, y in zip(a, b))
    return 2 * r * r + 4 * g * g + 3 * bl * bl


def nearest256(colour: str) -> int:
    target = rgb(colour)
    best, best_d = 16, None
    for r in range(6):
        for g in range(6):
            for b in range(6):
                cand = (CUBE[r], CUBE[g], CUBE[b])
                d = dist(target, cand)
                if best_d is None or d < best_d:
                    best, best_d = 16 + 36 * r + 6 * g + b, d
    for i in range(24):  # the greyscale ramp is often closer for near-neutrals
        cand = (8 + 10 * i,) * 3
        d = dist(target, cand)
        if d < best_d:
            best, best_d = 232 + i, d
    for i, hexv in enumerate(ANSI16):
        d = dist(target, rgb(hexv))
        if d < best_d:
            best, best_d = i, d
    return best


def nearest16(colour: str) -> int:
    target = rgb(colour)
    return min(range(16), key=lambda i: dist(target, rgb(ANSI16[i])))


def color_mode(forced: str | None) -> str:
    """The off-switch, in order of deference. FORCE_COLOR wins over NO_COLOR.

    `forced` may also name a rung directly (truecolor/ansi256/ansi16/none), which
    is what --color-mode uses to pin the ladder regardless of the environment.
    """
    if forced in ("truecolor", "ansi256", "ansi16", "none"):
        return forced
    if forced == "never":
        return "none"
    if forced == "always":
        return detect()
    no_color = os.environ.get("NO_COLOR") is not None
    force = os.environ.get("FORCE_COLOR")
    if no_color and not force:
        return "none"
    if force:
        return detect()
    if os.environ.get("TERM") == "dumb":
        return "none"
    return detect()


def detect() -> str:
    """The best rung this terminal can actually render."""
    term = os.environ.get("TERM", "")
    if os.environ.get("COLORTERM", "") in ("truecolor", "24bit"):
        return "truecolor"
    if "256" in term:
        return "ansi256"
    if os.environ.get("TERM"):
        return "ansi16"
    return "none"


def sgr(colour: str | None, mode: str) -> str:
    if mode == "none" or colour is None:
        return ""
    if mode == "truecolor":
        r, g, b = rgb(colour)
        return f"\033[38;2;{r};{g};{b}m"
    if mode == "ansi256":
        return f"\033[38;5;{nearest256(colour)}m"
    base = nearest16(colour)
    return f"\033[3{base % 10}m" if base < 8 else f"\033[9{base % 10}m"


def paint(text: str, colour: str | None, mode: str, *attrs: str) -> str:
    codes = [sgr(colour, mode)]
    codes += [
        {"dim": "\033[2m", "bold": "\033[1m", "reverse": "\033[7m"}[a]
        for a in attrs if a in ("dim", "bold", "reverse")
    ]
    if not codes:
        return text
    return "".join(codes) + text + "\033[0m"


def glyph_mode() -> str:
    """Nerd is opt-in, never auto-detected. Narrows unicode -> ascii after."""
    if not os.environ.get("RAGBAZ_NERD_FONT"):
        return "unicode" if sys.stdout.encoding.lower().replace("-", "") in (
            "utf8", "utf16", "utf32") else "ascii"
    return "nerd"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--theme", default=THEMES["default_theme"], choices=sorted(THEMES["themes"]))
    ap.add_argument("--color-mode", default="auto",
                    choices=("auto", "always", "never", "truecolor", "ansi256", "ansi16", "none"),
                    help="auto detects; the rungs pin the ladder")
    ap.add_argument("--explain", action="store_true", help="show why each colour resolved as it did")
    ap.add_argument("--spacing", action="store_true", help="print the space scale in cells")
    ap.add_argument("--glyphs", action="store_true", help="print the glyph set")
    args = ap.parse_args()

    theme = THEMES["themes"][args.theme]
    mode = "none" if theme.get("color_mode") == "never" else color_mode(args.color_mode)
    roles = {r["name"]: r for r in TOKENS["role"]}
    values = theme.get("role", {})

    print(f"theme   {args.theme}   background={theme.get('background')}   "
          f"colour={mode}   glyphs={glyph_mode()}")
    if theme.get("description"):
        print(f"        {theme['description']}")
    if theme.get("derived_from"):
        print(f"        derived from {theme['derived_from']}")
    print()

    missing = sorted(set(roles) - set(values))
    extra = sorted(set(values) - set(roles))
    if theme.get("roles_complete", True) and (missing or extra):
        print(f"! theme '{args.theme}' must define every role "
              f"(missing {missing}, unknown {extra})", file=sys.stderr)

    if args.spacing:
        sp = TOKENS["scale"]["space"]
        print("space scale (rem -> cells):")
        for i, (cells, rem) in enumerate(zip(sp["cells"], sp["rem"])):
            bar = paint(" " * cells or "-", values.get("edge.focus"), mode, "dim")
            print(f"  space.{i}  {rem:>7}  {cells} cell(s)  {bar}")
        print()

    if args.glyphs:
        keys = TOKENS["glyphs"]["set"]
        gm = glyph_mode()
        print(f"glyph set ({gm}):")
        for k, v in keys.items():
            print(f"  {k:<10} {v[gm]}")
        print()

    width = max(len(n) for n in roles)
    group = None
    for name in roles:
        g = name.split(".")[0]
        if g != group:
            group = g
            print(f"  {g}")
        colour = values.get(name)
        sample = paint("  " + " " * 8, colour, mode)
        line = f"    {name:<{width}}  {colour or '-':<9} {sample}"
        if args.explain:
            line += f"  <- {describe(name, colour, mode)}"
        print(line)

    print()
    print(f"  {len(roles)} roles, {len(THEMES['themes'])} themes "
          f"({', '.join(sorted(THEMES['themes']))})")
    return 0


def describe(role: str, colour: str | None, mode: str) -> str:
    web = next((r.get("web") for r in TOKENS["role"] if r["name"] == role), None)
    origin = f"web {web}" if web else "fleet convention"
    if mode == "none":
        return f"{origin}; colour suppressed -> plain text"
    if mode == "truecolor":
        return f"{origin}; 24-bit kept as-is"
    if mode == "ansi256":
        return f"{origin}; nearest xterm-256 index {nearest256(colour)}"
    return f"{origin}; nearest of 16 base colours {nearest16(colour)}"


if __name__ == "__main__":
    raise SystemExit(main())