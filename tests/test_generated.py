#!/usr/bin/env python3
"""Pin the generated modules to the token files, and the glyphs to their codepoints.

These assertions exist because of a specific failure: the Nerd Font column was
filled with literal Private Use Area characters, and a later edit silently
mangled several of them into the wrong icons. `check` became U+E0A2, a Powerline
divider, instead of U+EAB2, a Codicon tick. Nothing noticed, because a glyph table
has no expected values to compare against.

Run: python3 tests/test_generated.py
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "generated"))
import ragbaz_design as design  # noqa: E402

# Verified against ryanoasis/nerd-fonts "Glyph Sets and Code Points": Codicons
# (nf-cod-*) sit at ea60-ec84 and are NOT relocated by the patched fonts.
NERD_CODEPOINTS = {
    "check": 0xEAB2,        # nf-cod-check
    "cross": 0xEA76,        # nf-cod-close
    "dot": 0xEA71,          # nf-cod-circle_filled
    "dot_empty": 0xEABC,    # nf-cod-circle
    "rec": 0xEA77,          # nf-cod-sync
    "arrow_up": 0xEAA1,     # nf-cod-arrow_up
    "arrow_dn": 0xEA9A,     # nf-cod-arrow_down
    "ellipsis": 0xEA7C,     # nf-cod-ellipsis
    "branch": 0xEC6F,       # nf-cod-git_branch
    "warn": 0xEA6C,         # nf-cod-warning
    "lock": 0xEA75,         # nf-cod-lock
    "tag": 0xEA66,          # nf-cod-tag
    "caret": 0xEC5C,        # nf-cod-cursor
    "marker_select": 0xEB85,  # nf-cod-list_selection
    "rule": 0xEB07,         # nf-cod-horizontal_rule
}

# Box Drawing (2500-259f) is unpatched: nerd == unicode by design, not by omission.
BOX_DRAWING = {k: ord(v["unicode"]) for k, v in design.GLYPHS.items()
               if k.startswith(("box_", "bar_"))}


def test_no_glyph_has_an_empty_nerd_variant():
    empty = [k for k, v in design.GLYPHS.items() if not v["nerd"].strip()]
    assert not empty, f"empty nerd variant, draws nothing: {empty}"


def test_nerd_codepoints_match_the_font_tables():
    wrong = {k: (hex(ord(design.GLYPHS[k]["nerd"])), hex(want))
             for k, want in NERD_CODEPOINTS.items()
             if ord(design.GLYPHS[k]["nerd"]) != want}
    assert not wrong, f"nerd codepoint drifted: {wrong}"


def test_box_drawing_nerd_equals_unicode():
    wrong = {k: (hex(ord(design.GLYPHS[k]["nerd"])), hex(want))
             for k, want in BOX_DRAWING.items()
             if ord(design.GLYPHS[k]["nerd"]) != want}
    assert not wrong, f"box drawing must be identical in both sets: {wrong}"


def test_every_glyph_key_has_all_three_renderings():
    incomplete = {k: sorted(v) for k, v in design.GLYPHS.items() if set(v) != {"nerd", "unicode", "ascii"}}
    assert not incomplete, f"glyph without all three renderings: {incomplete}"


def test_ascii_variant_is_always_single_width():
    wide = {k: v["ascii"] for k, v in design.GLYPHS.items()
            if any(ord(c) > 0x7F for c in v["ascii"])}
    assert not wide, f"ascii variant is not ascii: {wide}"


def test_space_scale_zero_cell_step_is_documented():
    # space.1 rounds to zero cells. That is correct for a hairline and wrong for
    # terminal padding, so it must be called out next to the scale.
    cells = design.SPACE_CELLS
    assert cells[1] == 0, "space.1 is expected to round to zero cells"
    source = (ROOT / "tokens.toml").read_text()
    assert "rounds to ZERO cells" in source, "the zero-cell trap is not documented"
    layout = (ROOT / "docs" / "layout.md").read_text()
    assert "space.2" in layout, "layout.md must name a whole-cell padding step"
    assert "never zero padding" not in layout, (
        "layout.md still demands a space.1 cell of padding, which rounds to zero")


def test_generated_files_are_current():
    done = subprocess.run([sys.executable, "generate.py", "--check"],
                          cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, f"generated files are stale: {done.stderr.strip()}"


def test_emitted_rust_is_rustfmt_clean():
    import shutil
    if not shutil.which("rustfmt"):
        return
    done = subprocess.run(["rustfmt", "--edition", "2021", "--check",
                           "generated/ragbaz_design.rs"],
                          cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, (
        "the emitted Rust would fail `cargo fmt --check` in an adopting repo:\n"
        f"{done.stdout[:400]}")


def test_emitted_rust_narrows_to_ascii():
    # Set::detect must be able to reach Ascii; it used to be unreachable, which
    # made a non-UTF-8 terminal render mojibake instead of falling back.
    source = (ROOT / "generated" / "ragbaz_design.rs").read_text()
    assert "fn locale_is_utf8" in source, "no locale check in the Rust glyph narrowing"
    for var in ("LC_ALL", "LC_CTYPE", "LANG"):
        assert f'"{var}"' in source, f"{var} is not consulted"
    assert 'std::env::var("NO_COLOR")' in source, "Rust must honour the standard NO_COLOR"


def test_role_table_is_complete_in_every_theme():
    tokens = tomllib.loads((ROOT / "tokens.toml").read_text())
    roles = {r["name"] for r in tokens["role"]}
    themes = tomllib.loads((ROOT / "themes.toml").read_text())
    colourless = set()
    for name, theme in themes["themes"].items():
        if theme.get("roles_complete", True):
            missing = roles - set(theme.get("role", {}))
            assert not missing, f"theme {name} is missing roles: {sorted(missing)}"
        else:
            colourless.add(name)
    assert colourless, "expected exactly the colourless theme to opt out"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok    {name}")
            except AssertionError as error:
                failures += 1
                print(f"  FAIL  {name}\n        {error}")
    print(f"\n{'FAILED' if failures else 'OK'}: {failures} failure(s)")
    raise SystemExit(1 if failures else 0)