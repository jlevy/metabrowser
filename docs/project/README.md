# Project Design and Plans

Project documents separate durable system design from implementation planning.
Architecture documents describe component boundaries and decisions that should remain
useful after implementation.
Active feature plans define scoped work, rollout, testing, and acceptance criteria.

## Architecture

- [Editor plugin editing contract](architecture/arch-editor-plugin-editing-contract.md)
- [File Rollup Format v0.1](architecture/file-rollup-format/file-rollup-format.md)
- [VS Code extension host](architecture/arch-vscode-extension-host.md)

## Active Feature Plans

- [Opt-in trusted-local file editing](specs/active/plan-2026-07-16-trusted-local-file-editing.md)
- [Scanning state and recent directories](specs/active/plan-2026-07-16-scanning-state-and-recent-directories.md)
- [Quick file finder and search providers](specs/active/plan-2026-07-17-scalable-file-search.md)
- [Full-page HTML rendering and an explicit trust model](specs/active/plan-2026-08-06-html-rendering-and-trust-model.md)
- [Menu primitives and gated file actions](specs/active/plan-2026-08-06-menu-primitives-and-file-actions.md)
- [Filter controls and fine-grained navigation filtering](specs/active/plan-2026-08-09-nav-filter-controls.md)

## Research

- [Web diff viewer architecture and intermediate representations](research/research-2026-07-17-web-diff-viewer-architecture.md)
- [Fuzzy file ranking contract and measurements](research/research-2026-07-31-fuzzy-file-ranking.md)
- [High-performance file roll-up engine](research/research-2026-08-06-file-rollup-engine.md)

## Done Plans

- [Metabrowser v0.1.0 standalone package](specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md)
- [Flat single-command `metab` CLI](specs/done/plan-2026-07-27-metab-flat-cli.md)
- [Folder Overview panels and file-type summary](specs/done/plan-2026-08-12-directory-file-type-summary.md)
- [Contextual keyboard help and tree navigation](specs/done/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md)
- [Semantic file type families](specs/done/plan-2026-08-13-semantic-file-type-families.md)
- [Shared file type taxonomy and bounded breakdowns](specs/done/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md)

The [roadmap](../../TODO.md) is the concise status index.
Draft architecture and plan documents record intent rather than compatibility
guarantees.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
