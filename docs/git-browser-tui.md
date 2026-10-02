# Git browser TUI: options, quality, and interop

Status: proposal. Nothing here is implemented. Decision needed on the git access
layer (see "Recommendation").

## What we are trying to build

A read-only git view inside the ragbaz fleet TUI that can:

1. show the commit graph for a repo that is part of a box's SBOM;
2. hand a **selected revision** to another view (pin a version, fill a version
   string, compare two repos' constraint sets);
3. be driven *from* another view (the box/SBOM view selects a repo, the git view
   follows);
4. never shell out in a way that a hostile repo can subvert.

Requirement 2 and 3 are the real content. The log browser is the easy part.

## Option A: git access layer

| | `gix` (gitoxide) | `asyncgit` | `GitPort`/`LocalGit` (in-house) |
|---|---|---|---|
| Language | Rust | Rust (wraps libgit2, C) | Python, stdlib `subprocess` |
| Version | 0.88.0 (2026-09-25) | 0.28.1 (2026-03-21) | in this workspace |
| C toolchain | no | **yes** (libgit2) | no |
| Stability | pre-1.0, self-documented churn; only `gix-lock` is "production grade" | libgit2 bindings | small, already hardened |
| Embeddable | yes | yes (published separately from gitui) | yes, already a `Protocol` |
| New dep for frog | Rust toolchain + binary | Rust + C | **none** |

`gix-tui` does not exist — it is an unpublished 0.0.0 binary, not a component.
`gitui` has no `src/lib.rs`; read it, do not depend on it. If we ever want gitui's
git layer specifically, `asyncgit` is the published extraction of it.

### The in-house layer already solves our hard problem

`weftmark/src/weftmark/adapters/git_local.py` is the only hardened read-only git
layer in the fleet, and it is hardened for exactly the threat model of "a repo we
do not control":

- `GIT_SAFETY_OPTIONS = ("-c","core.fsmonitor=false","-c","core.hooksPath=/dev/null")`
  applied to *every* call — a repo's own `.git/config` and hooks are untrusted;
- `--end-of-options` on every invocation and revisions starting with `-` are rejected;
- read-only subcommand allowlist `{diff, for-each-ref, merge-base, rev-parse, show, status}`;
- 30s timeout; SHA-1 and SHA-256 object ids both handled; detached heads and
  worktrees modelled.

frog currently shells out ad-hoc (`store.py` uses `rev-parse`, `log -1 --format=%cI`,
`status --porcelain`, `ls-files -s`) with none of that. So the cheapest
improvement available to us is **not** adding a git library — it is having frog
call the port that already exists.

## Option B: rendering

Nothing suitable is embeddable. gitui/lazygit/tig are whole applications.

What we can borrow:

- **gitui** (org `gitui-org`) — the closest stack match: ratatui 0.30 + crossterm
  0.29, `asyncgit`, `syntect` for diffs, `ratatui-textarea` for a message editor,
  key config in `.ron`, theming documented in `THEMES.md`. Copy the architecture,
  not the code.
- **tig** (C/ncurses, GPLv2) — best *view model* to imitate: main/status/stage/
  stash/**grep**/pager/help. Note it is mature but slowing (down ~10% YoY), and it
  shells out to git for all rendering.
- **git-delta** — a pager, not a viewer, but the cheapest possible integration:
  if it is on `PATH`, set it as `GIT_PAGER` and we get line numbers, decorations
  and syntax highlighting for free. Degrade gracefully when absent.

Our own rendering then handles: commit graph (ASCII lanes: `│ ├─╱─`), refs and
their decorations, ahead/behind, and diffs via `git log -p` / `git show`.

## Option C: interop with other data models

The interesting part: a git browser that can point at a model that is not
commits.

- **jujutsu (jj)** and **Sapling (sl)** are change-based, not commit-based:
  the working copy *is* a commit, `@` is mutable, and there is no branch to
  check out. Our revision record ("the box runs commit X") has no clean meaning
  in that model, so a "pin a version" action must refuse or translate rather
  than silently pick a sha.
- **git-absorb**, **git-branchless** move history rewriting into new objects;
  a pinned rev can be rewritten away from, which breaks an SBOM pin.
- Our own multi-repo model: `frog.repo_deps` edges mean a pin on A constrains B.
  A single-repo git browser cannot show that; the constraint view must sit
  beside it, not inside it.

**Design consequence:** define a small selection/event model and make every view
a subscriber.

```
SelectionBus
  emit SelectRepo(repo_key)        -> git view follows
  emit SelectRevision(repo_key, sha, ref)
  emit PinRequested(repo_key, sha, ref)  -> SBOM/box view consumes, writes the pin
  emit ConstraintCheck(repo_key)         -> dep view consumes
```

Views never call each other. This is what makes "hook to another view" cheap, and
it is the same pattern frog already has in miniature with its `event_log` and
`hook dispatch`.

## Popular git browsers: can they talk to us?

| tool | can it be hooked to another data model? | mechanism |
|---|---|---|
| **lazygit** | **best of the bunch** | `customCommands` in its user config run shell commands with template context (`{{.SelectedLocalCommit}}` etc.) and render output in a notification or panel. A genuine external hook. But it is a Go app; we cannot embed it, only shell out to it. |
| **gitui** | no external hook surface | but its internal split (asyncgit / ratatui / syntect) is the design to copy |
| **tig** | no | read-only pager model to imitate |
| **git-delta** | yes, trivially | it *is* a pager; make it the `GIT_PAGER` |
| **jj** | yes, different model entirely | change ids; see above |
| **lazygit + delta together** | — | the conventional pairing; we can support the same pairing for our own view without depending on either |

## Recommendation

1. **Access: `GitPort` + `LocalGit` now.** Zero new dependencies, consistent with
   frog's `dependencies = []`, and it inherits the hardening we already wrote.
   Expose it from frog rather than duplicating the subprocess calls in `store.py`.
2. **Revisit `gix` only if** we need in-process object-graph walking (blame,
   bisect, range queries) at a scale subprocesses cannot serve — and pin it
   exactly, because it is pre-1.0.
3. **Rendering: ours**, with `git-delta` as an optional `GIT_PAGER` and gitui as
   the architectural reference.
4. **Interop: `SelectionBus`**, so the git view is a peer of the SBOM view rather
   than a mode inside it. Explicitly refuse `PinRequested` for a change-based
   repository state rather than guessing.
5. **Optionally offer a `lazygit`-style external hook surface** in our own config
   (a command template per action, output into a panel) — that is the one
   integration trick worth copying outright, because it is how operators extend
   a TUI without patching it.

## Open questions

- Does the fleet need to browse repos it does not have locally (a box reads
  `~baz0/src` as a read-only mirror)? If so the git layer needs a VFS path, and
  `LocalGit` does not have one.
- Commit-graph rendering for very large histories: limit depth by default and
  paginate, or risk the freeze we already saw with a 6000-row frog board.