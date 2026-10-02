# Configuration: one schema, four layers, visible provenance

Status: proposal.

Default path: `~/.config/ragbaz/rebekah.toml`.
Snapshot path: `--config-out=$HOME/ragbaz-config-snap-261002.toml`.

## Why this needs deciding early

The same settings have to reach four different places — a config file, CLI
overrides, in-TUI changes, and a saved snapshot — and the fleet already has a
"three surfaces must never disagree" requirement. If precedence is implicit, the
TUI will show settings that the CLI does not use. So: one schema, explicit
precedence, and every effective value knows where it came from.

## Precedence, low to high

1. **Compiled defaults** — every key has a default, so a config file only ever
   states differences.
2. **Config file** — `~/.config/ragbaz/rebekah.toml`, then `$XDG_CONFIG_HOME`
   override, then `--config <path>`. Later files override earlier; unknown keys
   are an error, not a warning (typos in a fleet config are expensive).
3. **CLI options** — `--theme`, `--color`, `--nerd-font`, `--git-pager`, and a
   general `--set key.path=value` for anything without a dedicated flag.
4. **In-TUI changes** — applied to the live session immediately, and either
   discarded or persisted (see below).

Environment variables are consulted *before* the config file for the few values
that must come from the environment (`REBEKAH_GATEWAY_TOKEN` and friends already
work this way). They are not a fifth layer, because they cannot be edited in the
TUI — anything settable in the TUI is a config-file or CLI concern.

## Provenance is a feature

Every effective setting carries where it came from:

```
theme          = "ragbaz-dark"     (config file, line 41)
color          = "auto"            (default)
nerd_font      = true              (--nerd-font, this session)
git.pager      = "delta"           (in-TUI, unsaved)
```

This is what makes "the TUI lied to me" a bug you can diagnose instead of an
argument. The TUI renders values with their origin dimmed, and `:config origins`
(or the status line) shows the full table. Saved files record provenance
explicitly rather than baking in whatever happened to be in effect:

```toml
# written by ragbaz, 2026-10-02
[ui]
theme = "ragbaz-dark"        # was: default
nerd_font = true             # was: default
```

## Saving

Two distinct operations, deliberately not conflated:

- **Save** (`w`) writes the session's *explicit* settings back to
  `~/.config/ragbaz/rebekah.toml`, preserving comments and key order. Requires
  confirmation if it would overwrite a file that is not ours (no header marker).
- **Snapshot** (`W`, or `--config-out` at startup) writes a *complete* file:
  every key at its effective value, annotated with its origin. This is the
  artifact you want to attach to a box SBOM or a bug report — it reproduces the
  exact behaviour without needing the layers that produced it.

`--config-out` is deliberately one-shot and never merges into the live config, so
scripting it cannot mutate a box's real configuration by accident.

## Schema shape

TOML, grouped to match the surfaces:

```toml
[ui]
theme = "ragbaz-dark"          # name from the theme registry
color = "auto"                 # auto | always | never  (NO_COLOR honoured)
nerd_font = false              # glyph set: nerd | unicode | ascii
unicode = "auto"               # override terminal detection
tab_width = 4
list_page = 20                 # rows per page in list views
help_page = 12                 # hotkey legend entries per page
border = "rounded"             # rounded | plain | none
tooltips = true

[git]
pager = ""                     # empty -> $GIT_PAGER, else git-delta if present
history_depth = 500
graph = true
word_wrap = false
external = "lazygit"           # optional external browser for handoff

[boxes]
db = ""                        # empty -> frog's AGENTS.db
channel = "pinned"            # pinned | bleeding

[signing]
registry = ""                  # empty -> identities/keys.toml
allow_translation_loss = false # acknowledge SSH-blob -> minisign degradation

[developer]
enabled = false                # unlocks format translation (e.g. to minisign)

[keys]
# optional overrides of the binding table; see the keymap doc
```

Themes are **names into a registry**, never inline colour values, so the design
system stays the single source of truth (the same rule the web design system
follows: "no literal colour, size or duration outside tokens").

## Hotkey legend

Bindings are data, one table, rendered by the help view — never a hand-kept
second copy. There is already a precedent in the fleet:
`remote-android/src/remote_android/tui/keymap.py` defines a frozen `Key` dataclass
and a `BINDINGS` list, derives `GLOBAL_KEYS`, and cycles `VIEWS` on tab/backtab.
frog's TUI hand-draws its legend box from a `KEYS` list, which is the same idea
but not yet data-driven. Unify on one table.

The legend is paginated because the binding set will be large; `help_page`
controls the page size, `?` opens it, and the legend shows the *current* context
(the same `remote-android` pattern: bindings carry a `view`, and the legend
filters by it).

## Rebinding

`keys.<action> = ["j", "C-j"]` overrides a single action. Because the palette is
a table, rebinding is a merge, not a rewrite — and the help view renders the
actual bindings, so a rebind can never desynchronise the legend from reality.

Vim-style `hjkl` and arrows are always live *except* inside a text field, which
switches to readline semantics (`C-a`/`C-e`/`C-w`/`C-d`, `Y`, `W`, and so on).
That exception needs to be a single predicate in the key dispatch (`is_editing`)
rather than per-view special-casing — see the keymap doc.