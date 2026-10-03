# ragbaz design system

The single design language for the ragbaz fleet's **terminal** surfaces, derived
from the existing ragbaz web design system rather than invented beside it.

This is where the fleet's TUIs and CLIs stop each inventing their own colours,
glyphs, help boxes and spacing, and start reading one token file.

**Status: adopted by two surfaces, specified for the rest.** The token files are
the source of truth; the language modules under [`generated/`](generated/) are a
projection of them that other repositories vendor, so nothing outside this
repository holds a copy of a design decision.

| surface | toolkit | state |
|---|---|---|
| [`ragbaz-tui`](../ragbaz-tui) | curses | conformant; the worked example |
| [`nostoi`](https://github.com/tabenius/nostoi) `src/tui.rs` | ratatui | conformant |
| [`frog`](../frog) `src/ragbaz_frog/tui.py` | curses | pending |
| `weftmark` | Textual | pending |

The documents under [`docs/`](docs/) are decisions, several of which are still
open. Where a document and the code disagreed, that was a bug in the document and
it was corrected — twice, both times after a renderer proved it wrong by
implementing it.

## Why this exists

The workspace currently has **four** independent terminal style systems:

| where | what it does | what it lacks |
|---|---|---|
| `sylvae/src/sylvae/color.py` | dependency-free ANSI helper, `NO_COLOR`/`FORCE_COLOR` aware, status → colour map | 8 SGR codes only; no themes, no glyphs |
| `remote-android/.../tui/theme.py` | the most complete one: curses pairs, semantic maps, glyph dicts with ASCII fallbacks, `theme_for()` | coupled to curses; not shared |
| `frog/src/ragbaz_frog/tui.py` | curses board, `_THEMES = {"ragbaz", "mono"}`, hand-drawn legend box | legend is drawn from a list but is not data-driven; colours are inline constants |
| `frog/.../main_cli.py` + `cli_render.py` | ANSI role palette, width-aware clip/pad | a fourth palette, unrelated to the other three |
| `nostoi/src/tui.rs` | ratatui | colours hardcoded inline, no theme file at all |

So the same fleet already has five palettes and two unrelated glyph policies.
This repository collapses that into one token file plus one glyph policy, and
leaves each surface free to render with whatever toolkit it uses (curses, ratatui,
Textual) as long as it reads the tokens.

## Relationship to the web design system

The web system at `library/public/assets/tokens.css` is explicit that it is
"the single source of design truth" and that *no literal colour, size or duration
may live outside it*. This terminal system **derives from it** and obeys the same
rule: the values below are copied from `tokens.css`, and terminal-specific
decisions are additions to it, not replacements.

What carries over unchanged:

- the role naming rule, `--<category>-<role>-<variant>` → `category.role.variant`;
- the **spacing scale**, `--space-0` … `--space-8`;
- the **type scale** ratio, 1.200, with the same eight steps;
- the warm-paper ink ramp — `--ink-emphasis #17150f`, `--ink-body #2b2822`,
  `--ink-muted #6d6659`, `--ink-faint #a39a8b`, `--ink-invert #f6f2e9`,
  `--ink-link #7a4b12`, `--ink-code #234a63`;
- the surface ramp — `--paper-page #fffdf8`, `--paper-inset #f7f2e7`,
  `--paper-raise #ffffff`, `--paper-rule #ded5c2`;
- the chrome/control/focus roles — `--chrome-edge #d5d1c5`, `--chrome-ink #626458`,
  `--control-edge #76776b`, `--control-surface #ffffff`, `--control-ink #222222`,
  `--focus-ring #91682c`.

### The one genuinely new mapping: type scale → emphasis

A terminal has no font-size control that a program should touch — the user's
terminal owns that. Pretending otherwise produces unreadable output. So the
`--type--2` … `--type-5` scale maps to **emphasis levels**, not sizes:

| web step | terminal meaning | rendering |
|---|---|---|
| `type--2` | caption, margin, as-of marker | `dim` |
| `type--1` | small text, inline code | normal |
| `type-0` | body | normal |
| `type-1` | emphasis, strong label | `bold` |
| `type-2` | section title | `bold` + `ink.emphasis` |
| `type-3` | view title | `bold` + `reverse` (title bar) |
| `type-4`/`type-5` | document/screen titles | `bold` + `reverse` |

Ratio 1.200 still governs anything that *is* sized — column widths, rule widths,
indent steps in the spacing scale.

## Contents

```
tokens.toml          the token file: roles, scales, glyph policy   <- source of truth
themes.toml          theme list; each theme maps roles -> colours
generate.py          compiles the tokens into per-language modules
generated/
  ragbaz_design.py   vendored by a Python surface
  ragbaz_design.rs   vendored by a Rust surface
tests/
  test_generated.py  pins the generated modules and the glyph codepoints
docs/
  configuration.md   four-layer config, provenance, --config-out
  layout.md          the frame: regions, pane widths, degradation ladder
  git-browser-tui.md git access/rendering options, SelectionBus interop
  signing.md         key registry, four key kinds, minisign translation warning,
                     x509 entries carry no trust rule by default
skills/
  ragbaz-design-language/    the language: tokens, themes, glyphs, bindings, frame
  ragbaz-renderer-adapter/   adapting one or more renderers to it
examples/
  tokens.py          resolve a theme, run the colour fallback ladder, print provenance
  legend.py          data-driven, paginated hotkey legend
```

## Adopting it

Two skills, and they are written to be used by other skills:

| skill | for |
|---|---|
| `ragbaz-design-language` | the language itself — the invariants, the roles, which colour to ask for, and the six behaviours a conformant renderer provides |
| `ragbaz-renderer-adapter` | the ordered procedure for bringing a renderer (curses, ratatui, Textual, plain ANSI, anything) up to those six behaviours, plus the conformance checks |

```bash
# a renderer conforms when it provides these six, and nothing more is required
# of the toolkit:
#   1 layout(width, height) -> regions      the frame + degradation ladder
#   2 resolve(role, colour_mode) -> bytes   truecolor -> ansi256 -> ansi16 -> none
#   3 glyph(key) -> str                     narrowed nerd -> unicode -> ascii
#   4 bindings() -> table                   one table, shared with the legend
#   5 resolve_key(key, editing) -> action   with field-scope precedence
#   6 truncate(text, width) -> str          escape- and width-safe
```

That is the point of keeping this separate from any toolkit: a renderer adopts
six behaviours, and curses, ratatui and Textual can each satisfy them without
being forced to resemble each other in the pixels.

## Consuming the tokens from another repository

A surface in another repository cannot import `tokens.toml` across a checkout
boundary, and stdlib-only projects like frog will not take a runtime dependency
on a sibling directory they may never see. So the tokens are **compiled** into one
dependency-free module per language, which a surface vendors:

```bash
python3 generate.py            # write generated/ragbaz_design.{py,rs}
python3 generate.py --check    # exit 1 if stale - use this in CI
```

| language | module | vendored as |
|---|---|---|
| Python | `generated/ragbaz_design.py` | e.g. frog's `src/ragbaz_frog/_design.py` |
| Rust | `generated/ragbaz_design.rs` | e.g. nostoi's `src/design.rs` |

Both carry the **source digest** of `tokens.toml` + `themes.toml` in their header,
so a vendored copy is traceable to the exact tokens it came from, and
`--check` proves it is not stale.

Three rules for a vendored copy:

1. **Never hand-edit it.** It is a projection, and an edit is lost at the next
   regeneration.
2. **Keep the provenance banner** recording the digest, so a re-vendor is a
   deliberate act.
3. **Verify it is `rustfmt`-clean** (`cargo fmt --all --check` in an adopting repo
   covers the vendored file, and `rustfmt.toml`'s `ignore` is nightly-only). The
   generator formats its own output, so this is free — but a hand-tidied copy
   breaks it.

The **colour ladder is computed, never stored**: the generator emits hex and each
language derives `nearest256`/`nearest16` at runtime. Storing a 256-index table
here would guarantee the Python and Rust ladders drift apart.

**Layout is deliberately not generated.** The frame is a grammar each renderer
implements in its own toolkit — that is the whole point of keeping the
reconciliation above the renderers.

## Tokens

`tokens.toml` is the machine-readable form of everything above.

### Roles

Roles are **semantic**, never literal. A surface asks for `ink.muted`, never for
`#6d6659`. That is what lets one token file serve five toolkits.

| group | roles |
|---|---|
| surface | `surface.page`, `surface.inset`, `surface.raise`, `surface.chrome` |
| ink | `ink.emphasis`, `ink.body`, `ink.muted`, `ink.faint`, `ink.invert`, `ink.link`, `ink.code` |
| edge | `edge.rule`, `edge.control`, `edge.focus` |
| status | `status.ok`, `status.warn`, `status.error`, `status.info`, `status.pending` |
| delta | `delta.added`, `delta.removed`, `delta.moved` (diff rendering) |

`status.*` is where the existing fleet already agrees — `sylvae/color.py` maps
`ok/passed → green`, `failed/error → red`, `unavailable → yellow` — so this group
extends a convention rather than replacing it.

### Spacing

`space.0` … `space.8`, straight from `--space-0..8`: `0, .25, .5, .75, 1, 1.5,
2, 3, 4` rem, converted to **cell counts** under one stated assumption: 1 cell is
the `space-3` step. `examples/tokens.py --spacing` prints the ladder.

> **`space.1` rounds to zero cells** (0.25rem). That is correct for a hairline and
> wrong for anything that must be visible. The first whole-cell step is
> **`space.2`**. This is a real trap: an early version of `docs/layout.md`
> demanded "one `space.1` cell of padding, never zero" on the title bar, which is
> a contradiction rather than a preference. Padding and margins take `space.2`
> and above.

## Colour

A terminal colour is a **request**, and the resolver picks the best available
form. The ladder, most to least preferred:

1. `truecolor` — 24-bit hex, when `COLORTERM` advertises it;
2. `ansi256` — the nearest xterm-256 index;
3. `ansi16` — the nearest of the 16 base colours;
4. `none` — no escape at all, plain text.

Disabling is honoured at every rung:

- `NO_COLOR` set to anything → colour off entirely (per no-color.org);
- `FORCE_COLOR` → on, even when not a TTY;
- `TERM=dumb` → off;
- not a TTY → off unless forced.

`sylvae/color.py` already implements exactly this policy for eight codes; the
generalisation is the token list plus the ladder. `NO_COLOR` must win over
`FORCE_COLOR`? No — the established convention is that `FORCE_COLOR` wins, and
that is what we implement, but it is worth deciding explicitly rather than by
accident.

## Themes

`themes.toml` ships four, derived from the web system's three themes plus the
`mono` variant frog already has:

| theme | from | notes |
|---|---|---|
| `ragbaz` | `tokens.css` defaults (warm sepia) | default; the printed-object palette |
| `ragbaz-night` | `html[data-theme="night"]` | for dark terminals |
| `ragbaz-white` | `html[data-theme="white"]` | high contrast light |
| `mono` | frog's existing `mono` theme | **no colour at all**; bold/dim/reverse only |

`mono` is not a fallback — it is a first-class theme, and it is the correct choice
for a screen that is being piped, logged, or read by someone who does not want
colour. A theme list that only contains colour themes pushes people to invent a
`--no-color` flag; having `mono` makes the honest choice the default one.

Adding a theme means adding a role → colour table. It must define **every** role;
a partial theme is a configuration error, not a set of defaults, so that adding a
role later cannot silently leave one theme behind.

## Glyphs

Three sets, selectable, with automatic narrowing:

| set | for |
|---|---|
| `nerd` | Nerd Font patched fonts; private-use-area icons |
| `unicode` | box drawing, arrows, geometric shapes; what almost every modern terminal has |
| `ascii` | `+-|`, `<>`, `*`; always available |

The policy is `nerd → unicode → ascii`, narrowed by what the terminal actually
advertises. `remote-android/.../tui/theme.py` already ships `UNICODE_GLYPHS` and
`ASCII_GLYPHS` dicts with `_utf8_ok()` detection, and that narrowing logic is the
model — it just needs a third tier above it and a setting to opt into `nerd`.

**Nerd codepoints are written as `\uXXXX` escapes, never as literal characters.**
A literal Private Use Area glyph in a diff is unreviewable, and one was silently
mangled once already. Provenance is recorded per key in `tokens.toml`: Codicons
(`nf-cod-*`, `ea60`–`ec84`) are not relocated by the patched fonts so those
codepoints are stable across versions; Box Drawing (`2500`–`259f`) is also
unpatched, so for those keys `nerd` equals `unicode` deliberately, and that is why
it is a literal.

`caret` and `marker_select` were added after the first renderers reported having
no key for a text edit caret or for the selection gutter — the latter matters,
because using `dot` for selection makes a selected row indistinguishable from a
status dot.

### The nerd-font checkbox

Because nerd fonts are a preference and not a default, the setting is a
**checkbox, not an auto-detection**:

```toml
[ui]
nerd_font = false        # true opts in to private-use-area glyphs
```

With it off, the resolver still narrows `unicode → ascii`, it simply never selects
`nerd` even if a Nerd Font is installed. Auto-detecting a patched font and then
changing the interface layout under someone who did not ask is worse than a
slightly plainer interface — a TUI whose column widths move when a font changes is
a TUI people stop trusting.

Glyph keys are named once and resolved per set, so a surface never contains a raw
character. That is already true of `remote-android`'s `Glyphs` class and should
extend to the keymap's own decorations.

## Hotkey legend

Bindings are **data**, one table, and the legend renders that table. There is
never a second hand-maintained copy of the key list — that class of bug is how a
TUI ends up advertising a binding it does not have.

The precedent to unify on is `remote-android/src/remote_android/tui/keymap.py`:
a frozen `Key(action, keys, view, op, help)` dataclass, a `BINDINGS` list in help
order, `GLOBAL_KEYS` derived from it, and a `VIEWS` cycle for tab/backtab, with
the help view printing the real table.

The legend is **paginated** (`help_page` entries per page, `?` opens it) because
the binding set across a fleet TUI will be large. It filters by the current view,
because bindings carry a `view`.

Arrow keys and `hjkl` are always live **except inside a text field**, where the
dispatch switches to readline semantics (`C-a`/`C-e`/`C-w`/`C-d`, `Y`, `W`, …).
That exception is expressed as one `scope` per binding — `global` / `view` /
`nav` / `field` — and one predicate in the dispatcher, not a special case in every
view. `nav` is suppressed while a field has focus and `field` goes live, and where
both claim a key **the field wins**.

That precedence is not academic: capital `W` is both the global *snapshot config*
and readline's *kill to end of line*, and without field precedence the global
silently eats the readline binding. `examples/legend.py` asserts it.

## The frame

`docs/layout.md` fixes enough structure that different toolkits render surfaces
that read as one product, without pretending they are the same product:

```
 row 0        ┌ title bar — 1 row, bold+reverse ────────────────────────────┐
 rows 1..n-2  │ nav │ main table                    │ detail              │
 row n-2      │ status line — 1 row, dim                                 │
 row n-1      │ legend strip — 1 row, dim                                 │
```

- **Chrome heights are counts, not percentages** — title 1, status 1, legend 1;
  only content flexes. A renderer that computes chrome as a fraction of height
  will not line up with one that counts rows.
- Pane widths come from the space scale with stated clamps: nav 20% `[12,24]`,
  detail 40% of the remainder `[24,48]`, main the rest (min 20).
- A **degradation ladder** as a pure function of `(width, height)`: drop detail
  below 76 columns, collapse nav below 52, drop the legend strip below 10 rows,
  merge status into the title bar below 6, and refuse below 4 rather than render
  a garbled frame.
- **Selection is two signals** — a marker glyph in a gutter column *and* reverse
  video. Reverse alone disappears when a terminal renders it poorly, and vanishes
  entirely in a log.
- **No meaning by colour alone.** Status is glyph + word + colour, always. This is
  what makes `mono` a real theme rather than a broken one, and it is why
  configuration provenance has to be *text* and not merely a dimmer colour.

The goal is **identical chrome, different content**: frog's board, nostoi's chain
browser and rebekah's console do different jobs and should not share a layout.

## Configuration

One schema, four layers, explicit precedence, and every effective value knows its
origin — full rationale and the `save` vs `snapshot` distinction in
[`docs/configuration.md`](docs/configuration.md).

```bash
# layered
ragbaz                                   # defaults
ragbaz --config /etc/ragbaz/rebekah.toml # + file
ragbaz --theme ragbaz-night              # + CLI override
ragbaz --config-out=$HOME/snap.toml      # complete, annotated snapshot
```

`--config-out` writes every key at its effective value annotated with where it
came from, and never merges into the live configuration — so snapshotting a box
for an SBOM cannot mutate it.

## Verification

```bash
python3 tests/test_generated.py   # 10 assertions, no dependencies
```

These are not smoke tests. They exist because of specific failures:

- **`test_nerd_codepoints_match_the_font_tables`** pins all 15 named icons to their
  verified codepoints. The nerd column was once filled with literal Private Use
  Area characters and a later edit silently mangled several: `check` became
  U+E0A2, a Powerline divider, instead of U+EAB2, a Codicon tick. Nothing
  noticed, because a glyph table has no expected values to compare against.
- **`test_box_drawing_nerd_equals_unicode`** asserts the unpatched `2500`–`259f`
  range is identical in both sets, so a future omission looks different from the
  deliberate choice it is.
- **`test_emitted_rust_is_rustfmt_clean`** and
  **`test_emitted_rust_narrows_to_ascii`** guard the two ways the emitted module
  used to be wrong in a way only an adopting repo would notice.
- **`test_space_scale_zero_cell_step_is_documented`** keeps `layout.md` and the
  scale honest with each other.
- **`test_role_table_is_complete_in_every_theme`** makes a partial theme a test
  failure rather than a runtime surprise.

## Examples

Both scripts are stdlib-only Python (3.11+, `tomllib`) and read the real token
files in this directory.

```bash
# the resolved palette for a theme, with the colour ladder applied
python3 examples/tokens.py
python3 examples/tokens.py --theme ragbaz-night
python3 examples/tokens.py --color-mode ansi256 --spacing

# a paginated, data-driven legend
python3 examples/legend.py
python3 examples/legend.py --page-size 6
python3 examples/legend.py --view boxes
```

`tokens.py --explain` prints the provenance of each colour: which rung of the
ladder it resolved to and why. This is the script to read first — it is the
reference implementation of "role → colour, best available form".

## Reuse, not reinvention

Where each piece comes from, so nobody writes it twice:

| need | already exists at | status |
|---|---|---|
| colour on/off policy | `sylvae/src/sylvae/color.py` | generalise to tokens |
| semantic colour map | `sylvae/src/sylvae/color.py` `_STATUS_STYLES` | extend to `status.*` |
| curses theme + glyph fallback | `remote-android/.../tui/theme.py` | add a `nerd` tier, share |
| curses widget primitives | `remote-android/.../tui/widgets.py` | reuse where curses is kept |
| binding table + view cycle | `remote-android/.../tui/keymap.py` | the model to unify on |
| ANSI width/clip/pad | `frog/src/ragbaz_frog/cli_render.py` | port to other surfaces |
| legend box drawing | `frog/src/ragbaz_frog/tui.py` `help_overlay_lines` | replace with the paginated table |
| `mono` theme | `frog/src/ragbaz_frog/tui.py` `_THEMES` | promote into `themes.toml` |
| terminal styling | `nostoi/src/tui.rs`, `weftmark/src/weftmark/tui/` | port palettes to tokens |

The honest summary: ratatui, Textual and curses each keep their own rendering,
and that is fine. The reconciliation happens at the **token, theme, glyph,
binding and frame** layer, not by forcing one widget toolkit on the fleet — same
house, different pixels; identical chrome, different content.