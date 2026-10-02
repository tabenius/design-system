# Layout grammar

Status: proposal. This is the "B" level — tokens and keys, plus enough structure
that two different toolkits render a surface that reads as the same product.

The goal is **identical chrome, different content**. Frog's board, nostoi's chain
browser and rebekah's console do genuinely different jobs and should not share a
layout. What they should share is the frame: title bar, pane split, status line,
legend strip, and how selection and status look.

Both a curses renderer and a ratatui renderer must be able to produce the frame
below, from the same numbers, without either one inventing geometry.

## The frame

```
 row 0        ┌ title bar — 1 row, bold+reverse ────────────────────────────┐
 rows 1..n-2  │ nav │ main table                    │ detail              │
 row n-2      │ status line — 1 row, dim                                 │
 row n-1      │ legend strip — 1 row, dim                                 │
```

Four regions, and the rule that makes cross-renderer agreement possible:

> **Chrome heights are fixed counts, never percentages.** Title bar is exactly 1
> row. Status line is exactly 1 row. Legend strip is exactly 1 row. Only the
> content region flexes.

A renderer that computes chrome as a fraction of height will drift from one that
counts rows, and the two surfaces will not line up on the same terminal.

## Pane widths

Widths come from the space scale, in cells, with explicit clamps.

| pane | rule | clamp |
|---|---|---|
| nav | 20% of width | `[12, 24]` |
| detail | 40% of the remainder after nav | `[24, 48]` |
| main | everything left | min 20 |

Detail is dropped entirely below the width in the degradation ladder; nav is
never dropped before detail, because navigation disappearing is more confusing
than a detail panel disappearing.

### Worked examples

**Panes are adjacent.** No column is reserved for a gutter — separation is
*drawn* with the box glyphs. Reserving gutter columns is the trap: the panes then
sum to `width + gutters` and run off the right edge. The pane widths must sum to
exactly `width`, and that is the check worth writing.

| terminal | chrome rows | nav | main | detail | sum | note |
|---|---|---|---|---|---|---|
| 120×40 | 3 | 24 | 58 | 38 | 120 | all three panes |
| 100×30 | 3 | 20 | 48 | 32 | 100 | all three panes |
| 80×24 | 3 | 16 | 38 | 26 | 80 | detail near its minimum |
| 76×24 | 3 | 15 | 37 | 24 | 76 | **threshold**: detail is the last thing to appear |
| 75×24 | 3 | 15 | 60 | — | 75 | detail dropped at 76 |
| 60×20 | 3 | 12 | 48 | — | 60 | detail dropped |
| 40×12 | 3 | — | 40 | — | 40 | nav collapses to a hint line |

Content height is always `height − 3`. Detail appears at `width ≥ 76` and is
dropped below it; main has a floor of 20 columns, so detail is also dropped when
keeping it would push main under that floor.

## Degradation ladder

Applied in order as the terminal shrinks. Each step is a decision, not a
side-effect, and a renderer must not skip a step or invent its own.

1. **Full** — nav, main, detail, status, legend.
2. **No detail** (width < 76) — detail folds into the main region as a
   scrollable sub-view reachable with `enter`.
3. **No nav** (width < 52) — nav collapses to a one-line hint showing the current
   box name; switching views goes through the view menu.
4. **No legend strip** (height < 10) — the strip is dropped entirely; `?` still
   opens the paginated legend.
5. **No status line** (height < 6) — merged into the title bar's right side.
6. **Minimum** (height < 4) — render nothing but a one-line error stating the
   terminal is too small, and exit. A garbled frame is worse than a refusal.

The ladder is a function of `(width, height)` only, so every renderer reaches the
same rung for the same terminal.

## Region contents

### Title bar — 1 row, `bold` + `reverse`, `ink.invert` on `surface.chrome`

- Left: ` <view> `, the current view name.
- Right: theme name, and the observation time.
- Filler: `box_h` glyph in the same attributes, so the bar reads as continuous.
- One `space.1` cell of padding at each end. Never zero padding on a reverse-video
  bar — the reverse attribute is the surface, and text flush to the edge of it
  looks broken.

### Status line — 1 row, `dim`, `ink.muted`

- Left: a one-line summary of the selection. This is the surface that answers
  "what am I looking at" without a detail pane.
- Right: `page <n>/<m>` when the current region paginates, otherwise the count of
  the collection.
- Never the only place a fact appears; it summarises, it does not replace.

### Legend strip — 1 row, `dim`, `ink.muted`

The always-visible hint line, built from the **current page** of the binding
table — not the full legend. Format is `<keys> <action>` pairs separated by
`box_v`, padded to width with the `space.2` gap. `?` opens the paginated legend
overlay, which is `help_page` entries per page.

Because the strip is generated from the same table the overlay and the dispatcher
use, it cannot describe a binding that does not exist.

### Main region

The content. A renderer chooses its own widgets, but:

- list rows are one line each; a row that needs two lines is two rows;
- the selected row uses **reverse video** *and* a marker glyph (`▸` in
  `ink.emphasis`, `*` in ascii). Reverse alone is not enough — see below;
- one blank row (`space.1`) between regions, never two.

## Selection treatment

Two signals, always both:

| signal | colour theme | mono |
|---|---|---|
| marker glyph in a gutter column | `ink.emphasis` | `*` glyph |
| reverse video on the row | `ink.invert` on the row | reverse video |

The gutter costs one column and buys the two things reverse video alone cannot:
legibility when the terminal renders reverse poorly, and a signal that survives
piping to a log.

## Colour-independent information — a hard rule

**No fact may be conveyed by colour alone.** This is not a preference; it is the
rule that makes `mono` a first-class theme instead of a degraded one.

| meaning | colour theme | mono / no colour |
|---|---|---|
| ok | `status.ok` | `✓` glyph + the word |
| failed | `status.error` | `✗` glyph + the word |
| unavailable | `status.warn` | `!` glyph + the word |
| selected | reverse + `▸` | reverse + `*` |
| focus | `edge.focus` | bold + marker |
| provenance of a value | `ink.muted` | `dim` + `(config file)` text |

The last row is why configuration provenance has to be *text*, not just a dimmer
colour: the point of showing where a value came from is lost exactly when someone
is reading a log.

## Contrast and focus

- `edge.focus` must reach at least 3:1 against **both** the surface it borders
  and the surface behind it. In a four-theme file that is a constraint on the
  palette, and `examples/tokens.py` is where it gets checked.
- In mono, focus is the marker glyph plus bold.
- Focus is never conveyed by a border colour alone either, for the same reason.

## Scrollbars

One column, in the gutter next to the list, and **only when content exceeds the
viewport**. `bar_full` for the visible portion, `bar_empty` for the rest, with the
track in `edge.rule`. No scrollbar on content that fits; an always-present empty
scrollbar trains people to ignore it.

## Glyph discipline

No literal characters in a renderer. Every line-drawing and status character comes
from a glyph key in `tokens.toml`, resolved through the active set. This is what
makes the `nerd → unicode → ascii` narrowing and the mono theme possible at all.

`truncate()` must never cut inside an escape sequence or a double-width character.
`remote-android/.../tui/widgets.py` has both (`clip`, `truncate`); frog has
`cli_render.py`. One of those should be the implementation.

## Renderer contract

A conformant renderer provides these six behaviours. Nothing more is required of
it, which is why curses, ratatui and Textual can all conform:

1. `layout(width, height) -> regions` — the frame above, including the
   degradation ladder
2. `resolve(role, colour_mode) -> bytes` — the token ladder
3. `glyph(key) -> str` — narrowed glyph set
4. `bindings() -> table` — one table, shared with the legend
5. `resolve_key(key, editing) -> action` — with field-scope precedence
6. `truncate(text, width) -> str` — escape- and width-safe

`skills/ragbaz-renderer-adapter/SKILL.md` is the procedure for getting a renderer
to those six.

## Explicitly out of scope

- Right-to-left and bidirectional text.
- Fractional or proportional heights for chrome.
- Mouse support as a primary input; the grammar is keyboard-first.
- Colour gradients, background images, or anything else a terminal cannot render
  identically everywhere.