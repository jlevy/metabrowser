# Architecture: Editor Plugin Editing Contract

**Author:** Metabrowser maintainers

**Status:** Draft

## Overview

Metabrowser’s current plugin contract is read-only: manifests classify files and declare
views, and JavaScript renderers own a view container until disposal.
The editor contract extends that model without making plugin installation equivalent to
enabling filesystem mutation.

The first implementation should prove the boundary with a small text editor.
Selecting a rich editor framework for every file type is outside the architecture
decision.

## Goals and Non-Goals

### Goals

- Preserve read-only startup as the default
- Require the host’s explicit edit-mode gate before any editor can save
- Let multiple plugins offer different editors for one file kind
- Give the shell a uniform dirty, save, conflict, draft, and disposal lifecycle
- Route every mutation through host-owned, schema-validated operations
- Keep large editor dependencies and build pipelines inside the plugins that need them
- Make contracts testable from manifests, runtime validators, fixtures, and browser
  lifecycle tests
- Separate trusted plugin code from untrusted document content

### Non-Goals

- Collaborative editing in the first release
- A built-in office suite or fidelity-preserving DOCX editor
- Replacing KPress as the Markdown renderer
- Allowing renderer data hooks to mutate arbitrary files
- Loading editor frameworks from a CDN in published plugins
- Treating complex editor assets as a required dependency of Metabrowser core

## System Context

An editor is a separate plugin capability from a read-only view.
The loader validates the editor declaration, the shell coordinates an editor session,
and the server authorizes every proposed mutation only when edit mode is enabled.

```text
manifest -> plugin loader -> shell editor session -> mutation proposal
                                             |
                                             v
browser draft store <- revision/conflict <- server edit gate -> filesystem
                                                     |
                                                     v
                                             inventory and events
```

Installing or discovering a plugin never crosses the edit-mode gate.
Existing `manifest.toml` files and read-only views remain valid, and discovery does not
expand into the served data tree.

## Design

### Components

#### Plugin Loader

**Responsibility:** Validate an editor declaration, its supported file kinds, required
host capabilities, resource limits, and declared browser assets.

**Interfaces:** Existing manifest discovery plus a versioned editor-capability block.

#### Shell Editor Coordinator

**Responsibility:** Own the active editor session, dirty state, navigation decisions,
draft recovery, save commands, conflicts, and disposal.

**Interfaces:** A narrow public lifecycle implemented by editor plugins.

#### Editor Plugin

**Responsibility:** Render and edit one supported file representation, report state, and
produce a schema-valid save proposal.

**Interfaces:** File envelopes and revision tokens in; lifecycle state and mutation
proposals out. An editor receives no filesystem path or write handle beyond the relative
path within the served root in its envelope.

#### Mutation Service

**Responsibility:** Enforce the startup edit gate, validate operations and limits,
re-resolve containment immediately before writing, detect conflicts, and publish the
result through the inventory event path.

**Interfaces:** A host-owned HTTP operation contract shared by core UI and plugins.

#### Draft Store

**Responsibility:** Retain recoverable local drafts keyed by served root, path, editor,
and base revision.

**Interfaces:** Host-owned browser storage with explicit quota and serialization errors.

### Data Flow

1. The shell mounts an editor from a file envelope and opaque revision token.
2. The editor reports clean or dirty state and may serialize a recoverable draft.
3. Save produces a validated proposal against the loaded revision.
4. The mutation service re-resolves the path, verifies edit mode and limits, and either
   writes or returns a structured conflict.
5. Success updates inventory and live views through the same event path as an external
   filesystem change.
6. The shell clears the draft only after confirmed success and disposes all editor
   resources when the session is replaced.

When an external event changes a clean document, the editor may refresh automatically.
When it changes a dirty document, the shell marks the session stale and requires an
explicit reload, comparison, or overwrite decision.
Automatic merging is not part of the initial contract.

### Data Model

An editor declaration includes a stable ID, label, supported file kinds, required host
capabilities, declared assets, optional size or encoding limits, and a public contract
version once the surface stabilizes.

The first save proposal is whole-file UTF-8 replacement:

```json
{
  "operation": "replace_text",
  "path": "notes/example.md",
  "expected_revision": "opaque-server-token",
  "text": "replacement contents"
}
```

Structured operations require independent schemas and preservation tests.
Examples include frontmatter patches, comment sidecars, and aggregate edits across a
directory. Plugins must not implement structured edits by rewriting unrelated document
regions ad hoc.

### Interfaces

#### External APIs

| Interface | Method | Description |
| --- | --- | --- |
| Mutation route, path to be finalized | POST | Submit one bounded operation against an expected revision |
| `/api/events` | GET | Reconcile successful saves and external filesystem changes |

The mutation response distinguishes success, validation errors, disabled editing, and
stale-revision conflicts.
The route remains unavailable or rejects mutations unless the server started with
explicit edit authorization.

#### Internal Interfaces

The shell invokes lifecycle behavior equivalent to mount, report state, serialize a
draft, propose a save, accept success or conflict, and dispose.
The shell’s Save command targets the active editor through this interface rather than
probing plugin DOM.

Replacing the selected file requires an explicit save, discard, or recoverable-draft
outcome. Switching between render and editor tabs may preserve the mounted session.

## Trade-Offs and Alternatives

### Decision 1: Keep Editors Separate From Views

**Chosen approach:** Add an explicit editor capability without changing the read-only
view contract.

**Alternatives considered:**

- Add mutation methods to every renderer, which would blur authorization and lifecycle
  boundaries
- Replace renderers with editors, which would make editing dependencies part of the
  default viewing path

**Rationale:** Separate capabilities preserve compatibility and make write authority
visible and testable.

### Decision 2: Keep Mutation Authority in the Host

**Chosen approach:** Plugins propose typed operations; the server validates and applies
them.

**Alternatives considered:**

- Give trusted plugins direct filesystem handles, which would bypass containment,
  limits, revision checks, and event consistency
- Let each plugin define its own mutation route, which would fragment error and security
  behavior

**Rationale:** A single host boundary keeps authorization, conflicts, and filesystem
safety consistent.

### Decision 3: Start With Whole-File Text Replacement

**Chosen approach:** Prove revisions and containment with one bounded operation before
adding structural patches.

**Alternatives considered:**

- Begin with generic JSON Patch, which does not preserve arbitrary source formatting
- Begin with plugin-defined operations, which would make the first contract too broad

**Rationale:** Whole-file replacement is small enough to validate end to end while
retaining optimistic concurrency.

### Decision 4: Keep Drafts and Complex Assets Host-Visible

**Chosen approach:** The host owns draft persistence; plugins own reproducibly built
assets that they declare explicitly.

**Alternatives considered:**

- Let plugins silently manage drafts, which prevents consistent navigation and failure
  behavior
- Bundle complex editors into core, which would impose their size and toolchains on all
  users

**Rationale:** The host can protect user state without taking ownership of every editor
implementation.

## Security Considerations

- Read-only startup exposes no successful editor mutation path
- Installing a plugin does not enable edits
- Every save is contained, bounded, revision-checked, and schema-validated
- The server re-resolves paths immediately before mutation and preserves exception and
  conflict detail without exposing unrestricted filesystem paths
- Plugin code is trusted, but document HTML, embedded resources, links, and pasted
  content remain untrusted
- Workers, WebAssembly, fonts, dynamic imports, and iframe use must be declared and
  tested before the manifest accepts them
- Published plugin assets must operate without runtime network access

The
[trusted-local file editing plan](../specs/active/plan-2026-07-16-trusted-local-file-editing.md)
applies to every mutation.

## Operational Concerns

### Monitoring

Development and browser tests should expose leaked editor sessions, workers, listeners,
requests, failed draft writes, and stale-revision conflicts.

### Logging

Mutation logs should record safe served-root-relative operation metadata and outcomes
without copying document contents or browser-local drafts.

### Deployment

Simple editors may ship bundleless JavaScript and CSS. Complex editors declare
reproducibly built assets that remain owned by the plugin.
The host serves declared outputs without understanding the plugin’s source language or
builder.

### Scaling

Only the active or deliberately retained editor sessions remain mounted.
Size and encoding limits protect browser memory and synchronous server work.

### Verification

- Contract tests derive manifest parsing, runtime validation, and browser-facing types
  from the same editor model
- Server tests cover disabled mode, containment, limits, stale revisions, and inventory
  event reconciliation
- Real-browser tests cover lazy mounting, dirty-state navigation, draft failures,
  external changes, conflict handling, replacement, and complete disposal
- Packaged plugin fixtures prove that declared editor assets work without runtime
  network access

## Open Questions

- What is the final mutation route and versioning scheme?
- Which draft retention and quota policy provides useful recovery without indefinite
  content retention?
- Which structured operation should follow whole-file text replacement?
- What asset declarations are required before admitting a complex editor bundle?

## References

- [Core architecture](../../architecture.md)
- [Plugin authoring](../../plugins.md)
- [Trusted-local file editing](../specs/active/plan-2026-07-16-trusted-local-file-editing.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
