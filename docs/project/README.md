# Project Design and Plans

Project documents separate durable system design from implementation planning.
Architecture documents describe component boundaries and decisions that should remain
useful after implementation.
Active feature plans define scoped work, rollout, testing, and acceptance criteria.

## Architecture

Start with [Views, models, and routes](architecture/arch-views-models-routes.md): it
maps what the browser shows, what it shows it from, and how each thing is addressed, and
links to the document that covers each in depth.

- [Views, models, and routes](architecture/arch-views-models-routes.md) — the map
- [Nav containers: item-like and folder-like roles](architecture/arch-nav-containers.md)
- [State and delivery](architecture/arch-state-and-delivery.md) — what the inventory
  holds, how derived state is invalidated, and what the browser does with it
- [File Diff Format v1](architecture/file-diff-format/file-diff-format.md)
- [Diff sources, context, and anchoring](architecture/file-diff-format/diff-sources-and-anchoring.md)
- [File Rollup Format v0.1](architecture/file-rollup-format/file-rollup-format.md)
- [Editor plugin editing contract](architecture/arch-editor-plugin-editing-contract.md)
- [VS Code extension host](architecture/arch-vscode-extension-host.md)

## Active Feature Plans

- [Opt-in trusted-local file editing](specs/active/plan-2026-07-16-trusted-local-file-editing.md)
- [Scanning state and recent directories](specs/active/plan-2026-07-16-scanning-state-and-recent-directories.md)
- [Quick file finder and search providers](specs/active/plan-2026-07-17-scalable-file-search.md)
- [Full-page HTML rendering and an explicit trust model](specs/active/plan-2026-08-06-html-rendering-and-trust-model.md)
- [Menu primitives and gated file actions](specs/active/plan-2026-08-06-menu-primitives-and-file-actions.md)
- [Markdown navigation extensions](specs/active/plan-2026-08-13-markdown-navigation-extensions.md)
- [End-to-end load time, from the CLI to first paint](specs/active/plan-2026-08-21-load-time-performance.md)
- [Mermaid diagram rendering](specs/active/plan-2026-08-21-mermaid-diagram-rendering.md)

## Research

- [Web diff viewer architecture and intermediate representations](research/research-2026-07-17-web-diff-viewer-architecture.md)
- [Fuzzy file ranking contract and measurements](research/research-2026-07-31-fuzzy-file-ranking.md)
- [High-performance file roll-up engine](research/research-2026-08-06-file-rollup-engine.md)
- [Markdown link navigation across repository browsers](research/research-2026-08-13-markdown-link-navigation.md)
- [Mermaid diagram support](research/research-2026-08-21-mermaid-diagram-support.md)

## Reviews

- [Load-time performance and the distance still to cover](reviews/review-2026-08-22-load-time-performance.md)
  — review of the six-round load-time branch, plus principles and candidate hypotheses
  for the work after it

## Done Plans

- [Bounded binary byte preview](specs/done/plan-2026-08-11-binary-byte-preview.md)
- [Metabrowser v0.1.0 standalone package](specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md)
- [Flat single-command `metab` CLI](specs/done/plan-2026-07-27-metab-flat-cli.md)
- [Folder Overview panels and file-type summary](specs/done/plan-2026-08-12-directory-file-type-summary.md)
- [Contextual keyboard help and tree navigation](specs/done/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md)
- [Semantic file type families](specs/done/plan-2026-08-13-semantic-file-type-families.md)
- [Shared file type taxonomy and bounded breakdowns](specs/done/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md)
- [GitHub and Obsidian Markdown navigation](specs/done/plan-2026-08-13-markdown-link-navigation.md)
- [Filter controls and fine-grained navigation filtering](specs/done/plan-2026-08-09-nav-filter-controls.md)

The [roadmap](../../TODO.md) is the concise status index.
Draft architecture and plan documents record intent rather than compatibility
guarantees.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
