#!/usr/bin/env python3
"""A paginated, data-driven hotkey legend.

The point of this script is what it does *not* contain: there is no second copy
of the key list. `BINDINGS` is the only table, the legend renders it, and
`resolve()` looks up the same table, so a rebind can never leave the help text
advertising a binding the dispatcher does not have.

The shape follows remote-android/src/remote_android/tui/keymap.py, which is the
model the fleet should unify on.

    python3 examples/legend.py
    python3 examples/legend.py --page-size 6
    python3 examples/legend.py --view boxes
    python3 examples/legend.py --list-views
    python3 examples/legend.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tokens as T  # noqa: E402  (same dir; the token resolver)

GLOBAL = "*"  # a binding that applies in every view


@dataclass(frozen=True, slots=True)
class Key:
    action: str
    keys: tuple[str, ...]
    help: str
    view: str = GLOBAL
    op: str | None = None   # what it does, for --json consumers
    scope: str = "view"     # global | view | nav | field
    """`nav` is suppressed while a text field has focus; `field` is live only
    while it does. That split is the whole of the "hjkl unless inside a field"
    rule, and it is one predicate in the dispatcher rather than a special case
    in every view."""


# In help order, which is also tab order within a view. First match wins on
# lookup, so more specific bindings are listed before global ones.
BINDINGS: list[Key] = [
    # --- global -------------------------------------------------------------
    Key("help", ("?",), "this legend", GLOBAL, "toggle_help", "global"),
    Key("view.next", ("tab",), "next view", GLOBAL, "next_view", "global"),
    Key("view.prev", ("shift+tab",), "previous view", GLOBAL, "prev_view", "global"),
    Key("view.menu", ("v",), "view menu", GLOBAL, "view_menu", "global"),
    Key("command", (":",), "command line", GLOBAL, "command", "global"),
    Key("config", ("g",), "in-TUI configuration", GLOBAL, "config", "global"),
    Key("save.config", ("w",), "save settings to the config file", GLOBAL, "save_config", "global"),
    Key("snapshot.config", ("W",), "write a full annotated config snapshot", GLOBAL, "snapshot_config", "global"),
    Key("config.origins", ("O",), "where each effective value came from", GLOBAL, "config_origins", "global"),
    Key("quit", ("q",), "quit (warns if there are unsaved changes)", GLOBAL, "quit", "global"),
    # --- boxes --------------------------------------------------------------
    Key("box.select", ("j", "down"), "next box", "boxes", "move", "nav"),
    Key("box.select", ("k", "up"), "previous box", "boxes", "move", "nav"),
    Key("box.open", ("enter",), "open the selected box", "boxes", "open", "nav"),
    Key("box.tag", ("t",), "tag the fleet repos to include", "boxes", "tag"),
    Key("box.refresh", ("r",), "re-read box identity", "boxes", "refresh"),
    # --- sbom ---------------------------------------------------------------
    Key("sbom.pin", ("p",), "pin the selected revision", "sbom", "pin"),
    Key("sbom.verify", ("V",), "verify the genesis attestation", "sbom", "verify"),
    Key("sbom.constraint", ("c",), "show inter-repo constraints", "sbom", "constraints"),
    # --- git ----------------------------------------------------------------
    Key("git.log", ("l",), "git log browser", "git", "log"),
    Key("git.pin", ("p",), "pin the selected revision", "git", "pin"),
    Key("git.depth", ("+", "-"), "widen or narrow history depth", "git", "depth"),
    Key("git.handoff", ("H",), "hand off to an external browser", "git", "handoff"),
    # --- field editing: readline, and only here ----------------------------
    # While a field has focus these are live and the nav bindings above are not.
    Key("field.start", ("C-a", "home"), "start of line", GLOBAL, "readline", "field"),
    Key("field.end", ("C-e", "end"), "end of line", GLOBAL, "readline", "field"),
    Key("field.kill-forward", ("C-k",), "kill to end of line", GLOBAL, "readline", "field"),
    Key("field.kill-word", ("C-w",), "kill word backward", GLOBAL, "readline", "field"),
    Key("field.kill-to-end", ("W",), "kill region to end (capital W)", GLOBAL, "readline", "field"),
    Key("field.yank-pop", ("Y",), "yank-pop (capital Y)", GLOBAL, "readline", "field"),
    Key("field.accept", ("enter",), "accept the value", GLOBAL, "commit", "field"),
    Key("field.cancel", ("escape",), "cancel editing", GLOBAL, "cancel", "field"),
]

# Tab cycles this list. Derived, never hand-maintained separately.
VIEWS: list[str] = [v for v in dict.fromkeys(k.view for k in BINDINGS) if v != GLOBAL]

# Global bindings resolved once; the dispatcher consults view bindings first so a
# view can shadow a global key without editing the global entry.
GLOBAL_KEYS: dict[str, Key] = {}
for k in BINDINGS:
    if k.view == GLOBAL:
        for key in k.keys:
            GLOBAL_KEYS.setdefault(key, k)


@dataclass
class View:
    """Render state. Kept pure so it is testable without a terminal."""
    view: str = "boxes"
    page: int = 0
    page_size: int = 8
    editing: bool = False
    bindings: list[Key] = field(default_factory=lambda: list(BINDINGS))

    def entries(self) -> list[Key]:
        """Bindings live in the current view, then globals, minus the ones the
        field editor owns while it has focus."""
        live = [k for k in self.bindings if k.view in (self.view, GLOBAL)]
        if self.editing:
            # A field takes over: nav and view bindings go, field bindings
            # arrive -- and field bindings sort FIRST, because a field owns the
            # printable keys. Without this, the global `W` (snapshot config)
            # would shadow readline's capital-W (kill to end of line).
            live = [k for k in live if k.scope in ("global", "field")]
            live.sort(key=lambda k: 0 if k.scope == "field" else 1)
        else:
            live = [k for k in live if k.scope in ("global", "view", "nav")]
        # A key is listed once; the first binding that owns it wins. The legend
        # and the dispatcher share this list, so they cannot disagree.
        seen: set[str] = set()
        out: list[Key] = []
        for k in live:
            if any(key in seen for key in k.keys):
                continue
            seen.update(k.keys)
            out.append(k)
        return out

    def pages(self) -> int:
        n = len(self.entries())
        return max(1, -(-n // self.page_size))

    def clamp(self) -> None:
        self.page = max(0, min(self.page, self.pages() - 1))

    def turn(self, delta: int) -> None:
        self.page = (self.page + delta) % self.pages()
        self.clamp()

    def cycle(self, delta: int) -> None:
        self.view = VIEWS[(VIEWS.index(self.view) + delta) % len(VIEWS)]
        self.page = 0

    def resolve(self, key: str) -> Key | None:
        """The one lookup the dispatcher and the legend both go through."""
        for k in self.entries():
            if key in k.keys:
                return k
        return None


def render(state: View, mode: str, theme: str = "ragbaz") -> str:
    values = T.THEMES["themes"][theme].get("role", {})
    glyphs = T.TOKENS["glyphs"]["set"]
    gm = T.glyph_mode()
    g = lambda k: glyphs[k][gm]  # noqa: E731

    p = T.paint
    entries = state.entries()
    total = state.pages()
    # slice to the current page: the legend is paginated, so it must not print
    # everything and merely *say* it is on page 1 of 3
    start = state.page * state.page_size
    entries = entries[start:start + state.page_size]
    out: list[str] = []

    title = f" keys {state.view} "
    if total > 1:
        title += f" {state.page + 1}/{total} "
    bar = g("box_h")
    out.append(p(title, values.get("ink.invert"), mode, "reverse"))
    out.append("")

    for k in entries:
        keys = ", ".join(p(key, values.get("ink.link"), mode, "bold") for key in k.keys)
        out.append(f"  {keys:<{28}} {p(k.action, values.get('ink.body'), mode)}"
                   f"  {p(k.help, values.get('ink.muted'), mode, 'dim')}")

    if state.editing:
        out.append("")
        out.append(p(f"  {g('warn')} field editing: arrow keys and hjkl are readline bindings here",
                     values.get("status.warn"), mode))

    out.append("")
    nav = f"  {g('arrow_dn')}{g('arrow_up')} page  {g('box_v')} tab view  {g('check')} save  {g('cross')} quit"
    out.append(p(nav, values.get("ink.faint"), mode, "dim"))
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--view", default="boxes", choices=VIEWS)
    ap.add_argument("--page-size", type=int, default=8)
    ap.add_argument("--page", type=int, default=0)
    ap.add_argument("--editing", action="store_true",
                    help="a text field has focus: field-only bindings appear")
    ap.add_argument("--theme", default="ragbaz", choices=sorted(T.THEMES["themes"]))
    ap.add_argument("--color-mode", default="auto")
    ap.add_argument("--list-views", action="store_true")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args()

    if args.list_views:
        for v in VIEWS:
            print(f"{v:<8} {sum(1 for k in BINDINGS if k.view == v)} bindings")
        return 0

    state = View(view=args.view, page=args.page, page_size=args.page_size,
                 editing=args.editing)
    state.clamp()

    if args.as_json:
        print(json.dumps({
            "view": state.view,
            "page": state.page + 1,
            "pages": state.pages(),
            "views": VIEWS,
            "editing": state.editing,
            "bindings": [{"action": k.action, "keys": list(k.keys), "help": k.help,
                          "view": k.view, "op": k.op, "scope": k.scope} for k in state.entries()],
        }, indent=2))
        return 0

    mode = "none" if T.THEMES["themes"][args.theme].get("color_mode") == "never" \
        else T.color_mode(args.color_mode)
    print(render(state, mode, args.theme))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())