---
name: ragbaz-component-model
description: Conventions for WIT component-model contracts and WASI Preview-2 components in the ragbaz fleet - how to express cross-cutting concerns (audit, policy), liveness, and runtime observability across a component boundary. Use when adding or changing a WIT interface or world, when a component needs logging, metrics or tracing, when something must stream or stay live, when asked how to do "AOP", "aspect", "middleware", "cross-cutting", "reactive", "streaming", "backpressure", "observability", "tracing" or "telemetry" inside a WASM component, or when deciding whether something belongs in the WIT contract or in the host. Triggers on "WIT", "wit-bindgen", "wasm component", "wasm32-wasip2", "component model", "wasmtime serve", "world", "interface", "exports", "imports", "gate", "trace", "metric", "span", "SSE".
---

# ragbaz component model

Conventions for the WIT and WASI Preview-2 surfaces in the ragbaz fleet.

This skill holds **conventions**, not contracts. Every WIT world, interface and
record in the fleet is owned by exactly one repository, and this skill never
restates one. Read the owner's file; extend it there. What follows is the set of
decisions that are the same everywhere.

> **Repo root:** this skill lives at `<design-system>/skills/<name>/`. The
> design-system repository root is **two directories above this file** — not the
> working directory, and not wherever this skill is symlinked from. The fleet has
> moved more than once, so resolve it from `__file__` (or two `cd ..`) rather
> than from a remembered absolute path.

## Who owns what

| contract | owner | notes |
|---|---|---|
| `konsonans:governance@0.1.0` | `BAZ.AI-Governance/` | governance node, replica and agent-proxy worlds; private, coordinated through frog |
| `nostoi:audit@0.1.0` | `nostoi/` | audit chains + attestations; bindings/component/wit/world.wit |
| terminal tokens, themes, glyphs, bindings | this repository | unrelated to components; see `ragbaz-design-language` |

## Vocabulary

- **"WASI 0.2" / "component model" / "Preview 2"**, not "Wasmtime 2". There is no
  Wasmtime 2. Wasmtime is a *host runtime*; in this fleet it is used as a CLI
  (`wasmtime serve`) and is not a Rust crate dependency in any `Cargo.toml`. Say
  `wasm32-wasip2` for the target, `wit-bindgen` for the bindings, and
  `wasm-tools` for inspection.
- A **world** is a set of imports and exports. An **interface** is a named set of
  functions. There is no other unit of composition in WIT.

## 1. Cross-cutting concerns: the world is the weaver

WIT has no join points, no advice and no pointcuts. It has `import`, `export` and
`func`. That is enough, because **world composition is static weaving**, and it
is the only kind that leaves a verifiable trace.

The single join point that exists is a call across the component boundary. Two
consequences:

- You cannot intercept a component's **internal** calls from WIT. If a
  cross-cutting concern must hold inside the guest, the guest must call it
  itself, through an interface it imports.
- Host→component calls are the host's business — a proxy or bridge — and no WIT
  import governs them. There are two weaves; do not expect one contract to cover
  both.

Express the concern as an interface the component **must** import, rather than as
advice around host functions:

```wit
interface gate {
    record operation { interface-name: string, method: string }
    record context { trace: trace-id, session-id: session-id, deadline-ms: u64 }

    /// Ordered advice around every governed operation. An Err short-circuits.
    enter: func(op: operation, ctx: context) -> result<context, string>;
    exit:  func(op: operation, ctx: context, summary: string) -> result<_, string>;
}
```

Rules:

- **`enter` returns a new `context` or denies. It never rewrites arguments in
  place.** Policy must be able to read what was asked for. Advice that silently
  transforms its input turns a compliance gate into a transform pipeline.
- **Ordering is list order; short-circuit is the `result` error.** Encode the
  fail-closed default in the *default* case (e.g. a timeout outcome maps to deny),
  never in the caller's discretion.
- **Enforce it in CI, not in a code review.** This is the whole point of doing it
  in WIT: `wasm-tools component wit <artifact>` emits the world's imports and
  exports, so a check can fail the build when a world exports a governed
  operation without importing `gate`. Cross-cutting enforcement becomes a
  property of the artifact rather than a convention someone upholds.

## 2. Liveness: pull-based, because WIT has no streams

WIT has no `stream<T>`, and async support in the component model is still being
specified. A contract that depends on one inherits a rewrite. Keep the ABI
value-passing and synchronous, and express liveness as **handles with an explicit
lifecycle**:

```wit
interface live {
    record cursor { seq: u64, token: option<event-id> }
    record sample { at: u64, metrics: list<metric>, cursor: cursor }
    record batch { samples: list<sample>, next: cursor, live: bool }

    open:  func(session: string, metrics: list<string>) -> result<handle, string>;
    /// Empty `samples` when idle. Never blocks. Never drops a record.
    poll:  func(h: handle, max: u32) -> result<batch, string>;
    close: func(h: handle) -> result<_, string>;
}
```

Rules:

- **Backpressure is the host pulling.** No queue, no unbounded guest buffer. If
  the consumer stalls, production stops. An `open`/`poll`/`close` triple makes
  that structural instead of aspirational.
- **An audit or evidence record is never dropped under backpressure.** If the
  guest cannot hold it, the gate fails closed. State this as an invariant and
  test it; a lossy audit trail is worse than a refused one.
- **`poll` returns empty when idle, not an error**, and `max` bounds what the
  guest may materialise. Both are what make the poll non-blocking.
- **WIT is cold by construction.** A subscription that mints a token is a cold
  handle. The trap is the verb — "subscribe" promises a hot push stream. Either
  provide `poll`/`close` next to it, or name it `open` and leave `subscribe` as a
  deprecated alias.
- **Fan-out belongs to the host.** SSE, dashboards and push belong to the proxy or
  bridge, not to the component. Where a bridge doc already says "expose SSE at the
  host layer, do not change the meaning of this call underneath existing
  callers", that is the rule, not a suggestion.
- **Reuse the existing cursor.** If the interface already paginates, the live
  cursor is that same token. Two orderings in one contract is a correctness bug.

## 3. Observability: import it, never export it

One tracing interface per component package, imported by every world. Not
exported, and never a return value.

```wit
interface tracing {
    record span { trace: trace-id, span: span-id, op: string }
    record fields { entries: list<tuple<string, string>> }

    counter:  func(name: string, value: u64, attrs: option<fields>);
    duration: func(name: string, ms: f64, attrs: option<fields>);
    log:      func(level: level, msg: string, attrs: option<fields>);
    span-open:  func(s: span) -> result<context, string>;
    span-close: func(s: span, status: option<string>) -> result<_, string>;
}
```

Rules:

- **Bounded and non-reflective.** A fixed key allowlist, hard length caps, and
  never echo raw arguments or remote messages back into diagnostics. Long error
  bodies are read to a cap with an overflow marker; oversized, unreadable or
  non-UTF-8 input yields status and header metadata only.
- **Never let a trace context influence a compliance decision.** Carry
  `trace-id` for correlation. Do not accept caller-supplied baggage as policy
  input — that lets a caller influence a decision with a header, which is an
  injection path wearing a telemetry costume.
- **A diagnostics sink is not a place arguments can leak.** If the same runtime
  performs argument scrubbing for policy, an unbounded logging sink defeats it.
  Assume anything here reaches the same logs as the audit trail.
- **`wasi:io/streams` is the always-available fallback.** Where a world imports
  it, stderr works with no host wiring, so a component is never silently mute
  when the host supplies no `tracing`. Component builds should show their runtime
  imports under `wasm-tools component wit`.
- **Extend existing instruments, never fork them.** If the host already publishes
  `foo.bar.duration`, the guest extends that name. A second dashboard for one
  metric is worse than no metric.
- **Health and liveness are an export, separate from tracing.** Liveness is a
  product feature; conflating it with the telemetry sink makes the sink
  load-bearing for something it must not gate.

The thing to actually fix is usually **not** the boundary. Boundary counters and
spans tend to exist already; what is missing is visibility *inside* the guest, so
one call that does several things reads as a single opaque duration. Instrument
the interior, not the seam you already measure.

## 4. Version discipline

Changing a world's imports or exports changes the world, so it changes the
package version.

- **Bump the package** (`konsonans:governance@0.1.0` → `@0.2.0`) in the same
  change.
- **Keep the previous world alive for one cycle** (`governance-node-v1`) if any
  host might still hold it.
- **Never change the meaning of an existing call.** Deprecate and add, the way a
  bridge doc that forbids breaking existing callers requires.
- Give every owned database and component its own independent revision, and
  inspect metadata without migrating (`schema --json`). Contract versioning and
  store versioning are separate problems.

## Checks

Before claiming a component conforms:

```bash
wasm-tools component wit <artifact>                 # inspect interfaces + runtime imports
wasm-tools validate <artifact>                       # validate the component
```

And a conformant component:

- every world that exports a governed operation **imports** `gate` — checked in CI
  over `wasm-tools component wit` output, not by review;
- every world has a working sink when the host supplies no `tracing`;
- no `result<_, string>` returns diagnostics on a path where a caller must
  distinguish a finding from a failure, and none drops an audit record under
  backpressure;
- adding an import or export lands with the package bump and the previous world;
- traces correlate with host spans but cannot reach a policy decision.