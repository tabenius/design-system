# Signing: one registry, four key kinds, org vouching

Status: proposal. The keys below exist; nothing consumes them yet.

## Decision as taken

Support **all** of: SSH (`ssh-keygen -Y sign`, what nostoi does today), OpenPGP,
and minisign — with **on-demand translation from the base64 of an SSH public key
blob**. Accept imported material including Cloudflare Origin CA certificates and
third-party OpenPGP keys (Proton Mail). RAGBAZ, as an organisation, may spawn
keys and may **vouch** for keys it did not create.

**Accepted loss in translation:** converting an SSH blob into a minisign key loses
minisign's *global signature* and its *comment binding* — the two things that make
a minisign file self-describing and tamper-evident as a file. A translated key is
therefore weaker than a natively generated minisign key. This must be recorded in
the registry as a provenance downgrade, not silently dropped, and the operator is
warned at the moment they choose it (see below).

### Minisign translation must warn, and is a developer-gated path

Selecting minisign for a key that originated as an SSH blob is not a like-for-like
choice, so the UI says so before anything is written.

**Gate.** The whole translation path is unavailable unless developer settings are
enabled:

```toml
[developer]
enabled = false          # translation to minisign requires true
```

With `[developer] enabled = false`, minisign appears in the kind list but is
disabled for any key whose `origin` is `translated`/`imported` rather than
generated locally — choosing it is impossible, not merely warned about.

**Warning text** (shown in the TUI and printed on the CLI):

```
!  minisign translation loses minisign's own guarantees:
!    - the global signature over the key file is not recreated
!    - the comment is not bound to the key, so it can be altered undetected
!   The result verifies, but it is not a self-describing minisign file.
!   Prefer a natively generated minisign key for anything that must be
!   verified offline by a third party.          [accept] [cancel]
```

**Acknowledgement.**

- Interactive: an explicit prompt defaulting to **cancel**. Accepting writes
  `native = false` plus a `downgrades` list onto the registry entry, so the loss
  travels with the key forever rather than living in a scrollback.
- Non-interactive: refuse unless the operator passes `--accept-translation-loss`
  (or sets `allow_translation_loss = true` in config). Silently degrading a
  signature format in a script is how a fleet ends up with keys nobody
  re-verifiable; the refusal is the same fail-closed posture as nostoi's
  `verify-attestation` on an unpinned key.

**Never warn-and-proceed silently in either direction:** there is no
"warn once and remember" mode. If the loss is unacceptable for a key, the key
must be generated natively as minisign.

## Keys created (mirroring the existing RAGBAZ procedure)

The two pre-existing keys use a consistent pattern — ed25519 `[SC]` primary,
cv25519 `[E]` subkey, no expiry, `<purpose> (<description>) <ragbaz@proton.me>` —
so the new keys follow it rather than introducing a new convention.

| role | fingerprint | uid |
|---|---|---|
| org root | `866ECB8348C0FE48E479736AF85CEFBA8B8E1040` | RAGBAZ root (organization root of trust; vouches for box and component keys) |
| box genesis | `78171B4532F8EFFBDFA2958F4315AE31DCC658B1` | RAGBAZ box genesis (box SBOM and instance-revision genesis attestation) |

Both are passphrase-less so a box can attest unattended; the box genesis key is
yours to protect with a passphrase later, which means it will then need an agent
or a `--pinentry-mode loopback` path at signing time.

Verified working: the root key holds an **exportable** certification over the box
key (`gpg --quick-sign-key`, not `--quick-lsign-key`, which produces a
non-exportable `sig L` that would not travel with the key), and a detached armored
signature verifies against a pinned fingerprint.

## Why OpenPGP is the right substrate for vouching

GPG already implements exactly the requested relationship: the org root key signs
a subordinate key, making it a **trusted introducer**. That is the same trust model
as SSH `authorized_signers` and minisign's flat file, except it is *hierarchical*
and it is already implemented, audited and familiar. So:

- **Do not invent a vouching protocol.** Record certifications; let GPG's trust
  model carry the semantics.
- The registry's job is to know *which* keys are allowed to vouch, and to record
  the chain so a verifier can walk it without a keyserver.

### x509 entries have no trust rule by default

A Cloudflare Origin CA certificate is trusted *because* it chains to Cloudflare's
CA, not because someone pinned a hash. Rather than bend that into the
fingerprint-pin model the other three kinds use — which would produce a rule that
looks uniform and is not — **`x509` registry entries carry no trust rule at
default settings.**

That means:

- an `x509` entry imports and records provenance exactly like any other kind;
- verification of an `x509` signature is **not performed** at default settings,
  and a verifier must say so rather than quietly falling back to "it parsed";
- no CA is pinned implicitly, and there is no default trust store.

A future CA-path rule would be a *developer-mode* feature, gated the same way the
minisign translation is: `[developer] enabled = true` plus an explicit CA pin.
Until that exists, `x509` is the honest "recorded, not yet verifiable" state.

This is also the correct outcome on the merits: a certificate whose whole purpose
is origin authentication is not a provenance signature, and treating it as one
would put a second, weaker trust model inside the same registry as the
fingerprint-pinned kinds.

## Registry

One file, one schema, referenced from config:

```toml
[[key]]
id         = "ragbaz-root"
kind       = "openpgp"
fingerprint = "866ECB8348C0FE48E479736AF85CEFBA8B8E1040"
role       = "org-root"          # org-root | box | component | imported
origin     = "generated"         # generated | translated | imported | downloaded
provenance = "gpg --quick-gen-key on this host, 2026-10-02"
native     = true                # false when translated: see accepted loss
may_vouch  = true

[[key]]
id      = "box0-genesis"
kind    = "openpgp"
fingerprint = "78171B4532F8EFFBDFA2958F4315AE31DCC658B1"
role    = "box"
vouched_by = "ragbaz-root"       # the certification that makes it trusted
origin  = "generated"
native  = true
```

`kind` drives the trust-anchor rule, which is **not** uniform:

| kind | trust anchor | verification |
|---|---|---|
| `ssh` | fingerprint (`SHA256:<base64>`) | `ssh-keygen -Y verify` + `allowed_signers` |
| `minisign` | the key hash, which *is* the trust anchor | `minisign -V` |
| `openpgp` | fingerprint + certification chain to an `org-root` key | `gpg --verify` + explicit pin |
| `x509` | **none by default** | not verified; see the section above |

The first three share a shape — a pinned identity, verified by a fingerprint. `x509`
does not, and is deliberately left out of that shape rather than approximated.

## Imports

Importing a key you downloaded from the internet and then trusting it is the
classic footgun, so the mechanics are deliberately dull:

1. import **inert** — the key lands in the registry as `trusted = false`;
2. record provenance: where it came from, when, and the **hash of the downloaded
   file** so the record is falsifiable later;
3. trust is a separate, explicit act that records *who* approved it and when;
4. **verification never consults a keyserver.** An unpinned key fails closed —
   this matches nostoi's existing behaviour, where `verify-attestation` fails on a
   missing attestation, a bad signature, or an unpinned key.

For OpenPGP specifically there is a lifecycle the other kinds do not have:
expiry, revocation, and re-issue. A pinned key that is later revoked must fail
verification, so the pin is (fingerprint, and a revocation checkpoint), not just a
fingerprint.

## nostoi integration

`nostoi` already has the right shape and the right instincts:
`Attestation { v, chain, format, seq, digest, anchored_at, principal, fingerprint,
anchor_key }`, canonical JSON, sidecars, namespace-scoped signatures, and a
document check separable from the signature check
(`crates/nostoi-core/src/attestation.rs:559-566`). Signing is deliberately
isolated in the facade crate (`src/attest.rs`, `DEFAULT_PROGRAM = "ssh-keygen"`),
so adding drivers does not touch the core.

Minimal extension: add `key_kind` and `vouched_by` to the attestation document,
and a signer registry behind the same `Attestation` struct. Two things must be
decided rather than defaulted:

- nostoi **refuses unattended passphrase-less signing by design** ("attesting is a
  human step"). Boxes need unattended attestation. Either that guard gains an
  explicit, named exemption for keys whose registry entry says
  `may_sign_unattended`, or the design changes. It should not be changed silently.
- a signature proves authorship, not time. For a genesis record, freshness needs
  the anchoring machinery nostoi already has (`nostoi-anchor`, outbox, fan-out).

## Open questions

- Should the registry live in `identities/gnupg/` (which exists and is empty) or
  inside the frog database so it federates with `peers`? Federation argues for
  frog; git-committed reproducibility argues for the repo.
- Does a box hold only its own key, or also the org root's public key? The latter
  is enough to verify a chain and is not a meaningful secret.
- Cloudflare Origin certs are for a different job (origin authentication, not
  provenance). Keeping them in the same registry is convenient; keeping them in the
  same *trust rule* is not.