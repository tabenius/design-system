---
name: ragbaz-design-language
description: The ragbaz terminal design language - semantic colour tokens, themes, glyph sets, the binding table, and the layout grammar. Use when building or changing ANY ragbaz terminal surface (TUI or CLI) in any toolkit (curses, ratatui, Textual, plain ANSI), when a surface hardcodes colours or glyphs, when two surfaces look inconsistent, when adding a hotkey or a legend, when adding a theme, or when asked whether a surface conforms to the ragbaz design system. Triggers on "ragbaz design system", "design tokens", "theme", "nerd font", "hotkey legend", "TUI styling", "colour scheme", "make it match", "conform".
---

# ragbaz design language

One design language for the ragbaz fleet's terminal surfaces, derived from the
web system at `library/public/assets/tokens.css` rather than invented beside it.

The renderer does not matter. Curses, ratatui, Textual and hand-rolled ANSI all
conform by implementing six behaviours; none of them needs to change toolkit.

## The files

> **Repo root:** this skill lives at
> `~/src/ragbaz/design-system/skills/<name>/`. Every path below is relative to
> **that repository root**, which is two directories above this file — not to the
> working directory, and not to wherever this skill happens to be symlinked from.
> Resolve `tokens.toml`, `docs/layout.md` and `examples/` against the repository
> root, or you will read the wrong file (or nothing).


Read these before writing any styling code. They are the source of truth, and a
renderer that hardcodes a colour or a box-drawing character has violated the
system, not merely missed a preference.

| file | what it holds |
|---|---|
| `tokens.toml` | semantic roles, space scale, type→emphasis scale, glyph keys |
| `themes.toml` | `ragbaz`, `ragbaz-night`, `ragbaz-white`, `mono` |
| `docs/layout.md` | the frame: regions, pane widths, degradation ladder |
| `docs/configuration.md` | four-layer config, provenance, `--config-out` |
| `examples/tokens.py` | reference implementation of the colour ladder |
| `examples/legend.py` | reference implementation of the binding table |

## Six behaviours a conformant renderer provides

A renderer is conformant when it provides exactly these:

1. `layout(width, height) -> regions` — the frame and its degradation ladder
2. `resolve(role, colour_mode) -> bytes` — truecolor → ansi256 → ansi16 → none
3. `glyph(key) -> str` — narrowed nerd → unicode → ascii
4. `bindings() -> table` — one table, shared with the legend
5. `resolve_key(key, editing) -> action` — with field-scope precedence
6. `truncate(text, width) -> str` — escape- and width-safe

To adapt a specific renderer, use the `ragbaz-renderer-adapter` skill, which is
written to be invoked from other skills.

## Invariants

These are the rules that make the system a system. Breaking one is a bug, not a
style choice.

**Never a literal colour.** Ask for a role: `ink.muted`, never `#6d6659`. Roles
are semantic; that is what lets one file serve every toolkit and theme. There is
no exception for "just this one line".

**Never a literal glyph.** Every line-drawing and status character comes from a
glyph key. Surfaces reference the key, never the character — that is what makes
the glyph narrowing and the `mono` theme possible at all.

**One binding table.** The table is the only place a key is named. The legend
renders it and the dispatcher resolves from it. A hand-kept second copy of the
key list is the bug this prevents: a rebind that leaves the help advertising a
binding the dispatcher lacks.

**Field-local bindings outrank global ones.** While a text field has focus,
`nav`-scoped bindings are suppressed and `field`-scoped ones are live, and where
both claim a key the field wins. That single rule is the whole of "arrows and
hjkl unless inside a field". It is one predicate in the dispatcher, never a
special case per view.

**No information by colour alone.** Every meaning has a non-colour signal: a
glyph, a word, or an attribute. This is what makes `mono` a first-class theme
rather than a broken one. Status must be legible in mono, so status is always
glyph + word + colour.

**Selection is two signals.** A marker glyph in a gutter column *and* reverse
video. Reverse alone fails when a terminal renders it poorly and vanishes in a
log.

**A theme defines every role.** A partial theme is a configuration error, not a
set of defaults — otherwise adding a role later silently leaves one theme behind.
`mono` is the one declared exception: `roles_complete = false`, because it is
deliberately colourless.

**Chrome heights are counts, not percentages.** Title bar 1, status 1, legend 1;
only content flexes. A renderer using fractions will not line up with one using
counts on the same terminal.

**`mono` is a real theme.** When output is piped, logged, or read by someone who
does not want colour, `mono` is the correct choice. Never invent a
`--no-colour` flag instead.

**Nerd Font is opt-in, never auto-detected.** `ui.nerd_font = true`. A TUI whose
column widths move because a font changed is worse than a slightly plainer one.

**Colour honours the environment.** `NO_COLOR` (any value) off; `FORCE_COLOR` on
and wins over `NO_COLOR`; `TERM=dumb` off; not a TTY off unless forced. Scraped
output must never be corrupted by colour.

## Which colour do I ask for

| situation | role |
|---|---|
| running text | `ink.body` |
| heading, selected label | `ink.emphasis` |
| caption, margin, as-of marker, key hint | `ink.muted` |
| rule, ornament, disabled | `ink.faint` |
| text on a dark fill | `ink.invert` |
| reference, link | `ink.link` |
| identifier, inline code | `ink.code` |
| hairline, box border | `edge.rule` |
| button or field border | `edge.control` |
| focus outline | `edge.focus` |
| ok / passed / running | `status.ok` |
| unavailable / degraded / needs review | `status.warn` |
| failed / error / broken | `status.error` |
| planned / queued | `status.pending` |
| diff add / remove / move | `delta.added` / `.removed` / `.moved` |
| the canvas | `surface.page` |
| an inset panel or table | `surface.inset` |
| a raised panel or code block | `surface.raise` |
| status bar, view chrome | `surface.chrome` |

`status.*` extends a convention the fleet already follows — `sylvae/color.py`
maps ok→green, failed→red, unavailable→yellow — so it extends rather than
replaces.

## Type means emphasis, not size

A terminal's font size belongs to the user's terminal. The web type scale maps to
emphasis levels instead: caption is `dim`, strong is `bold`, section is `bold` +
`ink.emphasis`, view and screen titles are `bold` + `reverse`. The 1.200 ratio
still governs anything genuinely sized — column widths, indents.

Spacing is in **cells**, converted from the web `rem` scale under one stated
assumption: 1 cell is the `space-3` step.

## Adapting a renderer

Follow `ragbaz-renderer-adapter`. In short: bind the tokens into the target
language, replace hardcoded glyphs with keys, port the binding table so the
legend is generated rather than drawn, implement the frame, then run the
conformance checks. Do not change token values to make a renderer easier — that
is the one thing an adapter must never do.

## Verifying

```bash
python3 examples/tokens.py --explain            # every role, and why it resolved so
python3 examples/tokens.py --theme ragbaz-night
python3 examples/tokens.py --color-mode ansi256 # exercise each rung
python3 examples/legend.py --list-views
python3 examples/legend.py --view git --page-size 6
python3 examples/legend.py --editing             # nav suppressed, readline live
```

A surface conforms when: it produces no escape sequence for a role that
`tokens.py` cannot resolve; its legend entries are all dispatchable; and its
output is byte-identical to `mono` when the theme is `mono`.

## Why it exists

The fleet had four independent terminal style systems and two unrelated glyph
policies. The reconciliation deliberately happens at the token, theme, glyph,
binding and layout layer — **not** by forcing one widget toolkit. Same house,
different pixels; identical chrome, different content.