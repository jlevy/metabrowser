# Editor-Capable Plugins

Status: requirements and architecture planning only.

Metabrowser’s current plugin contract is read-only: manifests classify files and declare
views, and JavaScript renderers own a view container until disposal.
Editor-capable plugins should extend that model without making plugin installation
equivalent to enabling filesystem mutation.

This specification records the minimum boundaries that an editor design must preserve.
The first implementation should remain a small text-editing proof rather than selecting
a rich editor framework for every file type.

## Goals

- Preserve read-only startup as the default.
- Require the host’s explicit edit-mode gate before any editor can save.
- Let multiple plugins offer different editors for one file kind.
- Give the shell a uniform dirty, save, conflict, and disposal lifecycle.
- Route every mutation through host-owned, schema-validated operations.
- Keep large editor dependencies and build pipelines inside the plugins that need them.
- Make contracts testable from manifests, runtime validators, fixtures, and browser
  lifecycle tests.
- Separate trusted plugin code from untrusted document content.

## Non-Goals

- Collaborative editing in the first release.
- A built-in office suite or fidelity-preserving DOCX editor.
- Replacing KPress as the Markdown renderer.
- Allowing renderer data hooks to mutate arbitrary files.
- Loading editor frameworks from a CDN in published plugins.
- Treating complex editor assets as a required dependency of Metabrowser core.

## Capability Boundary

An editor is a separate capability from a view.
A future manifest block may bind an editor to a file kind, but adding that declaration
does not grant write access.
The loader validates the declaration, the shell offers the editor, and the server
authorizes each proposed operation only when edit mode is enabled.

The final manifest shape must define:

- a stable editor ID, label, and supported kinds;
- required host capabilities, such as whole-text replacement or structured sidecar
  patches;
- browser-ready scripts, styles, workers, and other declared assets;
- an optional size or encoding limit;
- a public plugin-contract version when the editor surface becomes stable.

Existing `manifest.toml` files and read-only views remain valid.
The editor work must not rename the plugin manifest or broaden discovery from the served
data tree.

## Editor Lifecycle

The shell owns the active editor session and invokes a narrow lifecycle with behavior
equivalent to:

1. mount from a file envelope and revision token;
2. report clean or dirty state;
3. serialize a recoverable local draft;
4. produce a schema-valid save proposal;
5. accept success or a structured conflict;
6. dispose listeners, workers, requests, and retained state.

Switching between rendered and editor tabs may preserve a mounted editor, but replacing
the selected file must either save, discard, or retain a recoverable draft according to
an explicit user choice.
The shell’s Save command targets the active editor rather than probing plugin DOM.

## Mutation Contract

Editors never receive an unrestricted filesystem path or write handle.
They submit a proposal against a served-root-relative path and the revision they loaded.
The first operation should be whole-file UTF-8 replacement:

```json
{
  "operation": "replace_text",
  "path": "notes/example.md",
  "expected_revision": "opaque-server-token",
  "text": "replacement contents"
}
```

The server re-resolves containment immediately before writing, applies input and size
limits, and rejects a stale revision with a structured conflict instead of overwriting
newer content. A successful write updates the inventory and live views through the same
event path as an external filesystem change.

Structured operations such as frontmatter patches, comment sidecars, or directory-level
aggregate edits may be added after whole-file replacement proves the boundary.
Each operation needs its own schema and preservation tests; plugins must not implement
structured edits by parsing and rewriting unrelated document regions ad hoc.

The safety requirements in [trusted-local file editing](file-editing.md) apply to every
operation.

## Drafts and Conflicts

Unsaved drafts belong to a host-owned browser store keyed by served root, path, editor,
and base revision.
Draft storage must report quota or serialization failures and must not
clear a draft until the server confirms a save.
The interface should warn that browser-local drafts contain file content and are not a
backup system.

When an external event changes a clean document, the editor may refresh automatically.
When it changes a dirty document, the shell marks the session stale and requires an
explicit reload, comparison, or overwrite decision.
The initial contract does not attempt automatic merging.

## Trust and Packaging

Plugin code remains trusted code loaded from the same sources documented in the
[plugin authoring guide](../plugins.md).
Document HTML, embedded resources, links, and pasted content remain untrusted even when
the editor plugin itself is trusted.

Simple editors may ship bundleless JavaScript and CSS. Complex editors may ship
plugin-owned, reproducibly built assets.
The host serves declared outputs and does not need to understand the plugin’s source
language or builder.
Workers, WebAssembly, fonts, dynamic imports, and iframe use must be declared and tested
before the manifest accepts them.

## Delivery Plan

1. Finalize the opt-in mutation route and revision model in
   [trusted-local file editing](file-editing.md).
2. Define manifest, browser, and server models for one text-editor capability.
3. Publish JavaScript declarations or JSDoc types from the same contract validated at
   runtime.
4. Implement one minimal text editor with local drafts and whole-file replacement.
5. Test disabled mode, containment, stale revisions, draft recovery, live-event
   reconciliation, lazy mounting, and disposal.
6. Add a Markdown source editor that uses KPress for preview while keeping source text
   authoritative.
7. Evaluate one complex plugin-owned editor bundle only after the small contract is
   stable.

## Acceptance

- Installing an editor plugin does not enable writes.
- The read-only server exposes no successful editor mutation path.
- Every save is contained, bounded, revision-checked, and represented by a validated
  operation.
- A plugin cannot bypass the host mutation contract through the public editor API.
- Dirty state survives ordinary tab changes and has an explicit navigation outcome.
- External writes refresh clean editors and produce visible conflicts for dirty ones.
- Multiple editor choices for one kind do not change the default renderer.
- Published plugin assets work without runtime network access.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
