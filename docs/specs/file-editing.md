# Opt-In Trusted-Local File Editing

Status: planned after v0.1.0.

MetaBrowser is a trusted-local file browser, not a public-facing web server.
Editing must therefore be explicit, disabled by default, and bounded to the served root.

## Goals

- Add rename, move, and trash actions for files and directories.
- Require `--allow-edits` or `METAB_ALLOW_EDITS=1` at startup.
- Display a persistent warning when mutation is enabled.
- Preserve served-root containment through symlinks and concurrent filesystem changes.
- Return structured conflicts and validation errors that plugins can render
  consistently.

## Non-Goals

- Remote, public, or multi-tenant editing.
- In-browser text editing in the first phase.
- Permanent deletion without a separate design and explicit user action.
- Plugin-defined mutations before an editor-capability contract exists.

## Safety Contract

Every source and destination is resolved immediately before mutation.
The resolved paths must remain beneath the served root, and operations must reject
symlink escapes, reserved paths, missing parents, cross-device surprises, and
destination collisions.
The server must not follow a client-supplied absolute path.

The API returns a stable error code, a human-readable message, and the paths that the UI
may safely display. Mutation routes are absent or return a disabled response unless
editing was enabled at startup.

## Delivery Plan

1. Specify request, response, conflict, and audit-event schemas.
2. Add containment and time-of-check/time-of-use regression tests.
3. Implement rename and move behind the startup gate.
4. Add platform-aware trash support with clear unsupported-platform behavior.
5. Add context-menu and keyboard UI with confirmation for high-impact operations.
6. Exercise the capability through installed-wheel and browser tests.

## Acceptance

- Read-only startup exposes no working mutation path.
- Enabled operations cannot read or write outside the served root through traversal,
  symlinks, races, or crafted destination names.
- Conflicts never overwrite an existing target silently.
- Successful changes update the inventory and live UI without requiring a restart.
- Documentation retains the trusted-local security warning.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
