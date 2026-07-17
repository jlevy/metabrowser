# Roadmap

Metabrowser treats compression as a transport layer around one logical file.
For example, `report.html.zst` should classify and render like `report.html` while all
reads remain bounded.
Checked items below are supported today; unchecked items are planned work.

## Core Browser

- [ ] Modularize the browser shell and static assets so layout, navigation, and plugin
  rendering can evolve independently
- [ ] Add real-browser coverage for DOM behavior and versioned payload contracts
- [ ] Add
  [scalable file search](docs/project/specs/active/plan-2026-07-17-scalable-file-search.md)
  and evaluate optional persistent indexing for very large roots
- [ ] Add multiplexed, fair live-tail streaming across multiple files
- [ ] Define a generic writer event-log backend for append-only generated artifacts
- [ ] Enforce and report explicit time, memory, item-count, and payload-size budgets for
  directories containing hundreds of thousands of entries

## Plugin Platform

- [ ] Design and implement the
  [editor plugin editing contract](docs/project/architecture/arch-editor-plugin-editing-contract.md)
  without weakening the default read-only plugin contract
- [ ] Document stable extension points for custom renderers, metadata, actions, and
  optional storage adapters as each capability graduates into the public API

Metabrowser’s core stays independent of domain-specific renderers.
Applications can ship their own plugin packages while depending only on the documented
public plugin API.

## Trusted-Local Workflows

- [ ] Add
  [opt-in file operations](docs/project/specs/active/plan-2026-07-16-trusted-local-file-editing.md)
  with containment, conflict handling, and trash-first semantics
- [ ] Expose
  [scan progress and recent directories](docs/project/specs/active/plan-2026-07-16-scanning-state-and-recent-directories.md)
  without presenting incomplete trees as empty

File mutation remains disabled by default.
These workflows do not change Metabrowser’s trusted-client, local-filesystem security
model.

## Editor Integration

- [ ] Build the
  [VS Code extension host](docs/project/architecture/arch-vscode-extension-host.md)
  around a native tree, one embedded content panel, a supervised authenticated server,
  and uv-managed installation

The editor integration reuses the public tree, event, view, and plugin contracts.
Editor-specific readiness, authentication, and embed modes should remain host-neutral so
other trusted desktop integrations can use them without entering Metabrowser core.

## Transparent Single-File Compression

- [x] Gzip (`.gz`)
- [x] Raw zlib streams (`.zlib`)
- [ ] Zstandard (`.zst`)
- [ ] Evaluate common single-file formats such as xz (`.xz`), bzip2 (`.bz2`), and Brotli
  (`.br`) as real artifact demand appears

Adding a format requires logical-name and extension handling, streaming input/output and
CPU limits, malformed-stream behavior, and parity across preview, classification,
rendering, export, and raw serving.

## Archive and Container Formats

- [ ] Add safe browsing for ZIP archives (`.zip`)
- [ ] Add safe browsing for tar archives and compressed tarballs (`.tar`, `.tar.gz`,
  `.tgz`, `.tar.zst`)
- [ ] Define archive navigation, member preview, symlink and traversal rejection,
  duplicate-name handling, nesting limits, and aggregate decompression limits before
  enabling any container format

Archives contain multiple logical files, so they need a navigable virtual tree and a
stronger security boundary than transparent single-file compression.
They are not part of the v0.1.0 core contract.

## Browser Defense in Depth

- [ ] Enforce a strict Content Security Policy after replacing or nonce-enabling the
  remaining inline shell and plugin handlers

The current renderer sanitizes untrusted document HTML, and event data is escaped before
DOM insertion. A Content Security Policy remains useful defense in depth because the
trusted local server can read files within its configured root.

## Engineering Ratchets

- [ ] Remove the remaining scoped Python type-checking exceptions
- [ ] Graduate the remaining legacy JavaScript into strict TypeScript
- [ ] Remove the remaining exact-file Biome exceptions as those files are modernized

The release baseline already enforces Ruff, BasedPyright, Biome, TypeScript, pytest,
dependency audits, documentation formatting, source-distribution checks, wheel checks,
and installed-wheel CLI and plugin-doctor smoke tests.
These ratchets tighten known, measured legacy surfaces without weakening the enforced
baseline.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
