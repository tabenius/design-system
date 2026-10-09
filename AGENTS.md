# AGENTS.md: working on the ragbaz design system

This repository holds the design language for the ragbaz fleet's **terminal**
surfaces — tokens, themes, glyph sets, the hotkey binding table, and the frame.
It holds no production code: every surface in the fleet adopts it.

Two rules matter more than anything else here:

1. **The token files are the source of truth.** Never a literal colour, never a
   literal glyph, in any renderer.
2. **You are not here to make a renderer easier.** If a surface cannot express
   something, record the gap in the surface's own repository. Do not fork the
   palette.

This repository also hosts the fleet's **skills wire** (below). `generated/`
compiles the token files into vendorable modules; `skills/` carries agent-facing
conventions. Neither is design-system domain content beyond the terminal — a
skill here covers one concern and points at whoever owns the code.

## Skills

Three skills, standard `SKILL.md` frontmatter, loadable like any other. They are
written to be used **by other skills** as well as by people. Symlink each one
into `~/.claude/skills/`, `~/.codex/skills/` and `~/.config/opencode/skills/`
from this repository, so no tool holds a fork. **Resolve paths inside a skill
from the skill file** — two directories up is this repository's root, and it has
moved more than once.

| skill | path | use it for |
|---|---|---|
| `ragbaz-design-language` | [`skills/ragbaz-design-language/SKILL.md`](skills/ragbaz-design-language/SKILL.md) | the language itself: the invariants, which role to ask for, the type→emphasis mapping, and the six behaviours a conformant renderer provides |
| `ragbaz-renderer-adapter` | [`skills/ragbaz-renderer-adapter/SKILL.md`](skills/ragbaz-renderer-adapter/SKILL.md) | adapting **one or more** renderers (curses, ratatui, Textual, bubbletea, plain ANSI, anything) to those six behaviours, plus the conformance checks and the traps |
| `ragbaz-component-model` | [`skills/ragbaz-component-model/SKILL.md`](skills/ragbaz-component-model/SKILL.md) | WIT worlds and WASI Preview-2 components: cross-cutting concerns as imported interfaces, pull-based liveness, observability as an import, and version discipline |

A skill that covers a concern this repository does not own names the owning
repository and restates none of its contracts. `ragbaz-component-model` owns no
WIT file: the worlds live in `nostoi/` and `BAZ.AI-Governance/`.

Read `ragbaz-design-language` first. Use `ragbaz-renderer-adapter` whenever the
task involves bringing an actual surface into the system — it has the order of
work, and skipping to step 4 is how surfaces end up with pretty colours and a
stale legend. Use `ragbaz-component-model` before editing a WIT world or world
`import`/`export` list.

A renderer conforms by providing six behaviours. Nothing more is asked of the
toolkit, which is why different toolkits can conform without resembling each
other:

```
layout(width, height) -> regions      the frame and its degradation ladder
resolve(role, colour_mode) -> bytes   truecolor -> ansi256 -> ansi16 -> none
glyph(key) -> str                     narrowed nerd -> unicode -> ascii
bindings() -> table                   one table, shared with the legend
resolve_key(key, editing) -> action   with field-scope precedence
truncate(text, width) -> str          escape- and width-safe
```

## Invariants

Breaking one of these is a bug, not a style choice.

- **Never a literal colour.** Ask for a role: `ink.muted`, never `#6d6659`.
- **Never a literal glyph.** Reference a glyph key; let the set narrow.
- **One binding table.** The legend renders it, the dispatcher resolves from it.
  No second hand-kept copy of the key list.
- **Field-local bindings outrank global ones** for the same key. `nav` is
  suppressed while a field has focus, `field` goes live. Capital `W` is both the
  global *snapshot config* and readline's *kill to end of line*; without this
  rule the global eats the readline binding.
- **No information by colour alone.** Status is always glyph + word + colour.
  This is what makes `mono` a first-class theme.
- **Selection is two signals**: a gutter marker glyph *and* reverse video.
- **A theme defines every role.** A partial theme is a configuration error, not a
  set of defaults. `mono` is the one declared exception.
- **Chrome heights are counts, not percentages.** Title 1, status 1, legend 1;
  only content flexes.
- **Nerd Font is opt-in** (`ui.nerd_font`), never auto-detected.
- **Colour honours the environment**: `NO_COLOR` off, `FORCE_COLOR` on and beating
  `NO_COLOR`, `TERM=dumb` off, not a TTY off unless forced.

## Checks

Run before claiming a surface conforms, or before changing anything here:

```bash
python3 examples/tokens.py --explain              # every role resolves; why it did
python3 examples/tokens.py --theme ragbaz-night
python3 examples/tokens.py --color-mode ansi256   # exercise each rung
python3 examples/legend.py --list-views
python3 examples/legend.py --view git --page-size 6
python3 examples/legend.py --editing               # nav suppressed, readline live
```

A conformant surface passes all of:

- `mono` output is byte-identical to the colourless rendering;
- `NO_COLOR=1` and `TERM=dumb` produce plain text;
- piped output contains no escape sequences;
- every legend key resolves to the same action through `resolve_key`, in both
  editing and non-editing modes;
- truncation never splits an escape sequence or a double-width character;
- resizing across the thresholds in [`docs/layout.md`](docs/layout.md) leaves no
  garbled frame.

## Where things are

| path | what |
|---|---|
| [`tokens.toml`](tokens.toml) | roles, space scale, type→emphasis scale, glyph keys |
| [`themes.toml`](themes.toml) | `ragbaz`, `ragbaz-night`, `ragbaz-white`, `mono` |
| [`docs/layout.md`](docs/layout.md) | the frame: regions, pane widths, degradation ladder |
| [`docs/configuration.md`](docs/configuration.md) | four-layer config, provenance, `--config-out` |
| [`docs/git-browser-tui.md`](docs/git-browser-tui.md) | git access/rendering options, `SelectionBus` interop |
| [`docs/signing.md`](docs/signing.md) | key registry, four key kinds, org vouching, minisign warning |
| [`examples/tokens.py`](examples/tokens.py) | reference implementation of the colour ladder |
| [`examples/legend.py`](examples/legend.py) | reference implementation of the binding table |

## Derived from the web design system

`library/public/assets/tokens.css` remains the single source of design truth. The
values here are copied from it, and each role records which web token it came
from, so the correspondence is auditable rather than asserted. The web system's
rule carries over: no literal colour, size or duration outside the token files.

The one genuinely new mapping is that the 1.200 type scale becomes **emphasis,
not size** — a terminal's font size belongs to the user's terminal.

## Adding to this repository

- A **new theme** is welcome: a complete role table plus a line saying what it is
  derived from.
- A **new role** means adding it to every theme in the same change, or the
  completeness check fails.
- A **new glyph key** needs all three renderings (`nerd`, `unicode`, `ascii`) in
  the same change.
- A **new binding** goes in the example table, and the legend picks it up. Never
  add a binding in a way that requires editing the legend too.