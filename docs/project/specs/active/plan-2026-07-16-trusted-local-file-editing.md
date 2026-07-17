# Feature: Opt-In Trusted-Local File Editing

**Date:** 2026-07-16 (last updated 2026-07-17)

**Author:** Metabrowser maintainers

**Status:** Draft

## Overview

Metabrowser is a trusted-local file browser, not a public-facing web server.
File operations therefore require explicit startup authorization, remain disabled by
default, and stay bounded to the served root.

## Goals

- Add rename, move, and trash actions for files and directories
- Require `--allow-edits` or `METAB_ALLOW_EDITS=1` at startup
- Display a persistent warning when mutation is enabled
- Preserve served-root containment through symlinks and concurrent filesystem changes
- Return structured conflicts and validation errors that plugins can render consistently

## Non-Goals

- Remote, public, or multi-tenant editing
- In-browser text editing in the first phase
- Permanent deletion without a separate design and explicit user action
- Plugin-defined mutations before the editor capability contract is implemented

## Background

Current Metabrowser routes and plugins are read-only.
Local file operations are useful, but loopback binding alone does not make mutation
safe. Every operation must preserve the same containment, bounded-work, and honest-error
guarantees used by file reads while remaining visibly opt-in.

## Design

### Approach

Add a server startup capability gate and a small host-owned mutation API. The server
re-resolves every source and destination immediately before mutation, validates the
operation against the served root, and publishes successful changes through the existing
inventory and event path.

### Components

- CLI and environment configuration authorize mutation before server initialization
- The mutation service validates paths, limits, conflicts, and platform capabilities
- Core browser commands expose rename, move, and trash only when the capability is
  active
- The inventory and event system reconcile successful operations with all open views

### API Changes

Mutation routes are absent or return a stable disabled response unless editing was
enabled at startup. Requests contain only served-root-relative source and destination
paths. Responses contain a stable outcome code, a human-readable message, and only the
paths the interface may safely display.

Every source and destination is resolved immediately before mutation.
Operations reject traversal, symlink escapes, reserved paths, missing parents,
cross-device surprises, and destination collisions.
No request accepts a client-supplied absolute path.

## Implementation Plan

### Phase 1: Bounded File Operations

- [ ] Specify request, response, conflict, and audit-event schemas
- [ ] Add containment and time-of-check/time-of-use regression tests
- [ ] Implement rename and move behind the startup gate
- [ ] Add platform-aware trash support with explicit unsupported-platform behavior
- [ ] Add context-menu and keyboard UI with confirmation for high-impact operations
- [ ] Exercise the capability through installed-wheel and real-browser tests

## Testing Strategy

- Test disabled startup and capability reporting
- Cover traversal, symlink races, destination collisions, missing parents, cross-device
  moves, and platform trash failures
- Verify that conflicts never overwrite an existing target silently
- Confirm successful operations update inventory, recent results, and live views without
  a restart
- Run mutation tests only against isolated temporary roots

## Rollout Plan

Ship rename, move, and trash behind explicit startup authorization.
Keep text editing and plugin-defined mutation disabled until the maintained
[editor plugin editing contract](../../architecture/arch-editor-plugin-editing-contract.md)
has a tested host implementation.

## Open Questions

- What stable route names and error codes should become public API?
- Which platforms can provide recoverable trash semantics without an additional runtime
  dependency?
- Which actions require confirmation beyond the persistent edit-mode warning?

## Acceptance Criteria

- Read-only startup exposes no working mutation path
- Enabled operations cannot read or write outside the served root through traversal,
  symlinks, races, or crafted destination names
- Conflicts never overwrite an existing target silently
- Successful changes update the inventory and live UI without requiring a restart
- Documentation retains the trusted-local security warning

## References

- [Core architecture](../../../architecture.md)
- [Editor plugin editing contract](../../architecture/arch-editor-plugin-editing-contract.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
