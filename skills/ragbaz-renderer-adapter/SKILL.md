---
name: ragbaz-renderer-adapter
description: Adapt one or more terminal renderers (curses, ratatui, Textual, bubbletea, plain ANSI, or anything new) to the ragbaz design language - bind the token files, replace hardcoded colours and glyphs, make the hotkey legend data-driven, and implement the shared frame. Use when bringing a TUI or CLI into the design system, when a surface must be made consistent with the rest of the fleet, when porting styling between toolkits, or when asked to make several surfaces look like one product. Also usable by other skills that need a conformant renderer. Triggers on "adapt renderer", "make this conform", "bring it into the design system", "unify the TUIs", "port styling", "conformance check".
---

# ragbaz renderer adapter

Procedure for bringing a terminal renderer into conformance with the
`ragbaz-design-language` skill. Read that skill first — it holds the invariants
and the token semantics. This skill holds the order of work and the traps.

Adapt **one or more** renderers in one pass

> **Repo root:** this skill lives at
> `<design-system>/skills/<name>/`. Every path below is relative to **that
> repository root**, which is two directories above this file — not to the
> working directory, and not to wherever this skill happens to be symlinked from.
> Resolve the root from this file (two levels up); the workspace has moved more
> than once. Resolve `tokens.toml`, `docs/layout.md` and `examples/` against the
> repository root, or you will read the wrong file (or nothing).
 when several surfaces must match each
other; the token binding work is shared and only the frame differs.

## The one thing you must not do

**Never change a token value, add a role, or add a theme to make a renderer
easier.** That inverts the system: the tokens are the source of truth and a
renderer adapts to them. If a surface genuinely cannot express something, record
it as a known gap in the surface's own repo and stop — do not fork the palette.

The single acceptable exception is adding a *new theme* (a complete role table),
which is a design-system change, not an adapter change.

## Order of work

Do these in order. Skipping to step 4 is how surfaces end up with pretty colours
and a stale legend.

### 1. Inventory what is already hardcoded

Before changing anything, find every literal that should not be there:

- hex colours and 256/16 colour indices;
- box-drawing and status characters (`─│┌┐└┘├┤█▌░✓✗●○⚠↑↓•…`);
- numeric SGR codes (`\033[38;5;…m`, `A_BOLD`-style constants, hardcoded
  `Color::Red`);
- a hand-maintained help or hotkey list;
- palette constants that duplicate another project in the fleet.

In this workspace there are known instances of all of these: `sylvae/color.py`,
`remote-android/.../tui/theme.py`, `frog/.../tui.py` and `main_cli.py`, and
`nostoi/src/tui.rs`. Prefer **generalising** an existing module over adding a new
one, and prefer the shared token file over either.

### 2. Bind the tokens into the target language

Produce a small module that exposes the six behaviours. Do not inline values.

For a Python surface: reuse `examples/tokens.py` as the ladder implementation and
point it at the shared `tokens.toml`/`themes.toml` — do not re-derive nearest-256
or nearest-16. For a Rust surface: read the TOML at build time (the repo already
depends on `toml`) or generate a `.rs` from it; do not hardcode the palette in
Rust literals, which is exactly what `nostoi/src/tui.rs` does today.

Colour mode detection must be identical in every language, so factor it rather
than reimplementing it: `NO_COLOR` (any value) off, `FORCE_COLOR` on and beating
`NO_COLOR`, `TERM=dumb` off, not a TTY off unless forced.

### 3. Replace glyphs with keys

Delete the literal characters and resolve from `tokens.toml` glyph keys through
the active set (`nerd` only when `ui.nerd_font` is true, then `unicode`, then
`ascii`). Reuse the fleet's existing narrowing logic in
`remote-android/.../tui/theme.py` (`UNICODE_GLYPHS`/`ASCII_GLYPHS`, `_utf8_ok`).

If the target toolkit has its own glyph/icon set, map **from the keys**, so the
fallback chain still applies.

### 4. Make the binding table the single source

This is the highest-value step and the one most often skipped.

- Define one table of bindings: action, keys, help, view, scope, and an `op`
  identifier if anything programmatic dispatches on it.
- Generate the legend **from** that table. Never keep a second copy.
- Implement `resolve_key(key, editing)` against the same table.
- Scope bindings `global` / `view` / `nav` / `field`. While editing a field,
  `nav` is suppressed, `field` is live, and where a field binding and a global one
  claim the same key the **field wins**.

That last rule is not theoretical. In this design capital `W` is both the global
"snapshot config" and readline's kill-to-end; without field precedence the global
silently eats the readline binding. After porting, assert it: every key listed in
the legend must resolve to the same action through `resolve_key`, in both editing
and non-editing modes.

### 5. Implement the frame

Follow `docs/layout.md` exactly: fixed chrome heights (title 1, status 1, legend
1, content flexes), pane widths from the space scale with the stated clamps, the
degradation ladder as a pure function of `(width, height)`, two-signal selection,
and no meaning carried by colour alone.

If the toolkit has its own layout primitives, express the regions with them — but
the *numbers* must come from the grammar, or the surfaces will not line up.

### 6. Conformance checks

Run all of these before claiming the surface conforms:

- `python3 examples/tokens.py --explain` — every role resolves, none unknown.
- Legend/dispatcher consistency, in both editing modes (see step 4).
- `mono` theme: output must be byte-identical to the colourless rendering. If it
  is not, something is conveying meaning by colour alone.
- `NO_COLOR=1` and `TERM=dumb` produce plain text.
- Every rung of the ladder (`--color-mode truecolor ansi256 ansi16 none`).
- Truncation never splits an escape sequence or a double-width character.
- Resize across the degradation thresholds in `docs/layout.md`; no garbled frame.
- Piped output contains no escape sequences.

### 7. Report the gaps honestly

Some renderers cannot express everything. Say so explicitly, in the surface's own
repository, rather than quietly approximating. Known-acceptable gaps to record
rather than fight: a toolkit with no reverse-video support (fall back to the
marker glyph alone, and note it), a toolkit with no 256-colour mode, and any
surface whose content genuinely does not fit the three-pane frame.

## Traps

- **Rebuilding the colour ladder.** `examples/tokens.py` already does
  truecolor → ansi256 → ansi16 → none with a weighted distance. Copy the approach;
  do not re-invent a nearest-colour search per language.
- **Hardcoding `neo viz gitui colours` because ratatui made it easy.** That is the
  thing being removed.
- **A help screen as a string constant.** It will drift from the bindings the
  moment anything is rebound.
- **Proportional chrome heights.** Guarantees the surface will not line up with
  another fleet surface on the same terminal.
- **Colour-only status.** Passes a visual review, fails the moment the output is
  a log or the theme is `mono`.
- **Auto-detecting a Nerd Font.** A TUI whose layout shifts when a font changes is
  worse than a plainer one. Keep it opt-in.
- **Fixing a renderer by adding a token.** Add the token only if the *design
  system* needs it, in a separate change.