# ragbaz design system

The single design language for the ragbaz fleet's **terminal** surfaces, derived
from the existing ragbaz web design system rather than invented beside it.

This is where the fleet's TUIs and CLIs stop each inventing their own colours,
glyphs, help boxes and spacing, and start reading one token file.

> **Status: proposal.** The token files here are real and the example scripts run
> against them, but no production surface consumes them yet. The three design
> documents under [`docs/`](docs/) are decisions to be made, several of which are
> still open. Nothing here is committed to any other repository.

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
README.md            this file
docs/
  configuration.md   four-layer config, provenance, --config-out
  git-browser-tui.md git access/rendering options, SelectionBus interop
  signing.md         key registry, four key kinds, minisign translation warning,
                     x509 entries carry no trust rule by default
examples/
  tokens.py          resolve a theme, run the colour fallback ladder, print provenance
  legend.py          data-driven, paginated hotkey legend
```

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
2, 3, 4` rem. In a terminal these are **cell counts**: `space.3` is one column of
padding, `space.6` is two. `examples/tokens.py --spacing` prints the ladder.

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
That exception must be a single `is_editing` predicate in the key dispatcher, not
a special case in each view.

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
and that is fine — the reconciliation happens at the **token, theme, glyph and
binding** layer, not by forcing one widget toolkit on the fleet.