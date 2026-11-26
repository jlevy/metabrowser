# Project Design and Plans

This folder holds Metabrowser’s architecture documents and its project records: plans,
research, reviews, and QA runs.
Architecture documents describe the system as built, with each one’s status line saying
what is built and what is planned.
Plans scope work: they live in `specs/active/` while they owe work and move to
`specs/done/` when it is delivered, with any follow-ups tracked as beads.
Research, reviews, and QA runs are dated records of evidence; they keep their history.
The [roadmap](../../TODO.md) is the short status index across all plans.

## Architecture

Start with [the architecture overview](../architecture.md): the product’s aims, the
layers with their module paths, and a reading order.
It links each document below and the contributor standards in `docs/`.

- [CLI](architecture/arch-cli.md): modes, the serve lifecycle, in-process `--api`
  dispatch, remote tunnels, and process exit
- [Server and content](architecture/arch-server-and-content.md): request flow, safe
  paths, validators, and the content-trust model
- [Threat model](architecture/arch-threat-model.md): assets, adversaries, trust
  boundaries, and each threat’s policy, evidence, and accepted risk
- [Views, models, and routes](architecture/arch-views-models-routes.md): kinds, views,
  formats, and the route index
- [Parity registry](architecture/arch-parity-registry.md): the route and functional
  tables that `devtools/check_parity.py` reads
- [Inventory provider contract](architecture/arch-inventory-provider.md): the
  engine-independent queries, lifecycle, file cap, and change feeds
- [Python inventory engine](architecture/arch-inventory-engine-python.md): the walker,
  its concurrency, the watcher backend, and unit costs
- [Live delivery](architecture/arch-live-delivery.md): from the provider’s change feed
  to the browser’s stores, with events, recovery, and invariants
- [Git](architecture/arch-git.md): the process boundary, history sessions, graph
  checkpoints, and commit detail
- [Open modes](architecture/arch-open-modes.md): plain folder, repository folder, and
  mirror; how a target resolves to a root; the working tree and revision views; and what
  is never written
- [Source sessions and pins](architecture/arch-source-sessions-and-pins.md): subjects,
  capabilities, path projection, and the pin guard
- [Diff pipeline](architecture/arch-diff-pipeline.md): comparison sources, hydration,
  caches, and Markdown projection
- [Repository cache](architecture/arch-repository-cache.md): layout, identity, record
  contracts, locks, and the sweep
- [Mirror acquisition and refresh](architecture/arch-mirror-acquisition-and-refresh.md):
  transports, credentials, the lending checkout, and refresh cadence
- [GitHub pull requests](architecture/arch-github-pull-requests.md): records, the
  catalog, files, checks, stacks, and routes
- [Plugin system](architecture/arch-plugin-system.md): manifests, discovery,
  classification, the SDK gate, containers, and how to add a file type
- [Browser shell](architecture/arch-browser-shell.md): shell modules, stores, lifecycle,
  and asset loading tiers
- [macOS app](architecture/arch-macos-app.md): server supervision, windows, restore, and
  WebKit differences
- [App contract](architecture/arch-app-contract.md): what the macOS app reads of
  `metab`, the one file that declares it, the golden that records it, and the checks
  that hold both sides to it
- [Recent targets](architecture/arch-recent-targets.md): the list of folders and
  repositories opened lately, what records an open, and the shells that read it

### Formats

- [Collection format](architecture/arch-collection-format.md): ordered annotated items,
  what the format owns and what a carrier adds, with guided reviews as the first carrier
- [File Diff Format v1](architecture/file-diff-format/file-diff-format.md): the JSON
  change-set document, its schema, and its apply oracle
- [File Rollup Format v0.1](architecture/file-rollup-format/file-rollup-format.md):
  file-type classification and directory totals by type, with the
  [recommended type definitions](architecture/file-rollup-format/recommended-file-types.toml);
  [File Rollup Format in this repository](architecture/file-rollup-format/README.md)
  says how to change the definitions and export a packet

## Active Plans

- [Lean language support](specs/active/plan-2026-11-25-lean-language-support.md): Lean
  as a code family with GitHub’s color and a tested port of the official Lean 4 grammar,
  and the [Adding a Language](../adding-a-language.md) recipe and the `mb-*` skills that
  make the next language or plugin repeatable
- [Diff presentation](specs/active/plan-2026-11-25-diff-presentation.md): shared
  comparison controls, file formats, and guide reference blocks
- [Whole-stack review](specs/active/plan-2026-11-24-stack-review.md): a page for a
  stack’s whole change, one consolidated diff with Docs over it; collection references
  to a pull request, a file as one changes it, and a commit; a stack’s guide in a
  `stack-review` block; and concise guides with Markdown notes
- [Guided review groups, rationale, rendered documents, and stack rollups](specs/active/plan-2026-11-24-guided-review-groups.md):
  optional groups of steps, a rationale step, documents drawn rendered in steps, and a
  design for a stack-wide rollup that whole-stack review supersedes
- [Guided reviews in the agent skill](specs/active/plan-2026-11-24-guided-reviews-skill.md):
  the skill section that writes, publishes, and refreshes a pull request’s guided
  review, now shipped, and a `metab` check of a draft guide, still to build
- [The Diff | Current chooser](specs/active/plan-2026-11-23-diff-current-chooser.md):
  the original comparison-wide chooser, superseded by Diff presentation
- [Pull request update cadence and GitHub budget](specs/active/plan-2026-11-22-pull-request-update-cadence.md):
  a draft for free conditional probes every few seconds for what is on screen, full
  reads once every minute or two, and a budget that leaves room for the account’s other
  tools
- [Treemap granularity: canvas cells and a denser rollup](specs/active/plan-2026-11-22-treemap-canvas-granularity.md):
  a draft for painting every file down to a device pixel on a canvas, with DOM kept for
  labels, focus, and hover, then sending the Treemap far more of the tree in a compact
  encoding
- [Tabular data browsing and live SQLite](specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md):
  a draft for one generic table plugin over CSV, record lists, and SQLite, with
  nondestructive, live reads of databases other applications are writing
- [A structured event log](specs/active/plan-2026-11-19-structured-event-log.md): one
  JSON line for every request, background job, and `git` or `gh` process, with latency,
  outcome, and what started it; the causes of GitHub failures in the page; browser
  reports of waits that never ended; then views of the log in Metabrowser
- [The app’s command-line dependencies and a complete doctor](specs/active/plan-2026-11-18-cli-dependencies-and-doctor.md):
  where each tool’s minimum version lives, the app’s versioning contract with `metab`, a
  doctor that checks everything a setup needs, and Check Setup… in the macOS app
- [View on branch](specs/active/plan-2026-11-17-view-on-branch.md): one control on a
  pull request’s Changes that opens a changed file at the pull request’s head in the
  main UI, replacing the standalone revision page; approved 2026-11-17
- [Object data model and views](specs/active/plan-2026-11-14-object-data-model-and-views.md):
  a draft for one modeled object per file, folder, commit, and pull request, drawn in
  several view shapes; its key decisions are open
- [Documentation from first principles](specs/active/plan-2026-11-14-documentation-from-first-principles.md):
  one owner per fact, task guides, architecture documents for every layer, a baseline
  scale benchmark, and checks that keep the set linked
- [Switching folders in the macOS app](specs/active/plan-2026-11-18-macos-folder-switching.md):
  a window that can show any open folder, the title as a native chooser of open and
  recent folders, a keyboard switcher, and marks shared with the page
- [Operational views of Claude Code and Codex](specs/active/plan-2026-11-19-agent-operations-views.md):
  one shared model, record kinds with one color each, and the home, session, timeline,
  live, usage, and latency views for both agents, in six phases, with `urollup` as an
  optional accelerator
- [Native macOS app](specs/active/plan-2026-11-10-native-macos-app.md): folder identity,
  the icon and release pipeline, warm folder switching, host mode and the agent front
  door, and the app-managed runtime
- [Fast CI](specs/active/plan-2026-11-16-fast-ci.md): bringing a pull request’s CI from
  20 minutes to about 5 with the same checks, by running the suite on every processor,
  splitting it into unit, golden, and browser jobs, and cutting what a flake costs; the
  owner approved Phases 1 and 2 on 2026-11-16, and they are implemented by
  jlevy/metabrowser#499 and jlevy/metabrowser#504
- [Opening anything from the CLI and the app](specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md):
  `metab TARGET --present`, the `open_in` preference, GitHub URLs and Open URL… in the
  app, GitHub sign-in checks, and named UI commands; Phase 1 partly built
- [Publishing the macOS app](specs/active/plan-2026-11-16-macos-app-publishing.md):
  Developer ID signing, notarization, the DMG, provenance, a tag-driven release job, and
  the checks of a downloaded copy, with the owner-only steps
- [Instant transitions and stable layout](specs/active/plan-2026-11-11-ui-apparent-performance.md):
  retained surfaces, fixed boxes at first paint, and prediction behind admission
  control, each a measured performance-loop round
- [Pull-request review from a mirror or an existing checkout](specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md):
  object borrowing and explicit repair are shipped; store conversions and deepening
  remain
- [Paying down the flat-tree delivery cost](specs/active/plan-2026-09-15-flat-tree-delivery-cost.md):
  per-page catalog hashing is shipped; larger batches and attached-walk costs remain
- [Functional UI and CLI parity](specs/active/plan-2026-09-10-functional-ui-cli-parity.md):
  the parity boundary and checked registry are shipped; migrating the existing UI
  remains
- [A machine-readable contract for the API envelopes](specs/active/plan-2026-08-30-api-schema-and-contract.md):
  a draft for describing what each internal `/api` route answers, checked against its
  responses
- [Git status and working-tree diffs](specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md):
  a draft for read-only status groups and working-tree comparisons
- [Inventory provider refactor and fdu adoption](specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md):
  the Python reference provider is shipped; the fdu provider is planned
- [Pluggable inventory engine](specs/active/plan-2026-08-23-pluggable-inventory-engine.md):
  the semantic contract, test oracles, and adoption gates that every inventory engine
  meets
- [Mermaid diagram rendering](specs/active/plan-2026-08-21-mermaid-diagram-rendering.md):
  a draft for rendering `mermaid` fences as diagrams
- [End-to-end load time, from the CLI to first paint](specs/active/plan-2026-08-21-load-time-performance.md):
  on-demand assets and progressive inventory are shipped; broader load-time goals remain
- [General diff rendering](specs/active/plan-2026-08-17-general-diff-rendering.md): the
  comparison model, Git pipeline, and renderer are shipped; presets, context expansion,
  and multi-file review remain
- [Markdown navigation extensions](specs/active/plan-2026-08-13-markdown-navigation-extensions.md):
  static-site adapters, GitHub URL localization, and transclusion are shipped; line
  targets and mounted roots remain
- [Repository library and open from a Git URL](specs/active/plan-2026-08-11-open-repo-from-git-url.md):
  the cache and URL open shipped in 0.12.0; the catalog, chooser, and very large
  repositories remain
- [Menu primitives and gated file actions](specs/active/plan-2026-08-06-menu-primitives-and-file-actions.md):
  the shared modal foundation is shipped; action menus and file mutations remain
- [Quick Search](specs/active/plan-2026-07-17-scalable-file-search.md): the file finder
  and pull-request completions are shipped; full-text search remains
- [Editor plugin editing contract](specs/active/plan-2026-07-17-editor-plugin-editing-contract.md):
  a draft for plugins that edit files without weakening the read-only view contract
- [Opt-in trusted-local file editing](specs/active/plan-2026-07-16-trusted-local-file-editing.md):
  the capability gate is shipped; rename, move, and trash workflows remain
- [Scanning state and recent directories](specs/active/plan-2026-07-16-scanning-state-and-recent-directories.md):
  scan status and pending aggregates are shipped; recent directories remain

## Done Plans

- [Files grouping, a diff summary, pull stack groups, and the conversation timeline](specs/done/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md):
  the owner’s requests of 2026-11-15, as one stack of pull requests and three of their
  own on `main`, merged after 0.12.0
- [Event-based pull-request freshness and budgeted prefetch](specs/done/plan-2026-11-11-pr-freshness-and-prefetch.md):
  merged after 0.12.0
- [Shift key reveal and a systematic keymap](specs/done/plan-2026-11-11-shift-key-reveal-and-keymap.md)
- [Watching GitHub pull requests](specs/done/plan-2026-11-06-pr-watch-and-reconnect.md)
- [GitHub Pulls tab for mirrors and local checkouts](specs/done/plan-2026-10-01-github-pulls-tab.md)
- [v0.12 thin mirror for Git and GitHub browsing](specs/done/plan-2026-09-23-v012-thin-mirror.md)
- [v0.12 alpha testing and stack acceptance](specs/done/plan-2026-09-22-v012-alpha-testing.md)
- [CLI-first delivery: v0.10 parity and the v0.12 slice](specs/done/plan-2026-08-28-cli-first-delivery-map.md)
- [Hosted review model and GitHub provider](specs/done/plan-2026-08-27-github-provider-and-pull-requests.md):
  superseded by the thin-mirror and Pulls tab plans
- [Unbounded logical Git history with bounded rendering](specs/done/plan-2026-08-25-unbounded-virtualized-git-history.md)
- [Git revision navigation performance](specs/done/plan-2026-08-25-git-revision-navigation-performance.md)
- [Diff syntax highlighting and layouts](specs/done/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md)
- [One file-type source of truth](specs/done/plan-2026-08-21-file-type-source-of-truth.md)
- [CLI parity and golden coverage](specs/done/plan-2026-08-21-cli-parity-and-golden-coverage.md)
- [Shared file type taxonomy and bounded breakdowns](specs/done/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md)
- [Semantic file type families](specs/done/plan-2026-08-13-semantic-file-type-families.md)
- [GitHub and Obsidian Markdown navigation](specs/done/plan-2026-08-13-markdown-link-navigation.md)
- [Folder Overview panels and file-type summary](specs/done/plan-2026-08-12-directory-file-type-summary.md)
- [Contextual keyboard help and tree navigation](specs/done/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md)
- [Bounded binary byte preview](specs/done/plan-2026-08-11-binary-byte-preview.md)
- [Filter controls and fine-grained navigation filtering](specs/done/plan-2026-08-09-nav-filter-controls.md)
- [Full-page HTML rendering and an explicit trust model](specs/done/plan-2026-08-06-html-rendering-and-trust-model.md)
- [Git graph nav panel and Git API](specs/done/plan-2026-08-06-git-graph-view.md)
- [Flat single-command `metab` CLI](specs/done/plan-2026-07-27-metab-flat-cli.md)
- [Metabrowser v0.1.0 standalone package](specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md)

## Research

A research record stays here while it informs open work, and moves to
[`research/archive/`](research/archive/) once its questions are answered.

- [Paraverse and Metabrowser tables](research/research-2026-11-26-paraverse-table-design.md):
  live view comparison and shared table, relationship, and record design

- [Drawing dense, deep treemaps in the browser](research/research-2026-11-22-dense-treemap-rendering.md):
  how desktop disk-usage tools and web libraries draw treemaps down to single files, and
  measured canvas, DOM, and hit-testing costs in Chrome and WKWebView

- [Operational visibility into Claude Code and Codex](research/research-2026-11-19-agent-home-visibility.md):
  every file format under `~/.claude` and `~/.codex`, what Metabrowser shows of them
  today, and a proposed agents plugin built on the public plugin contract

- [Why CI takes twenty minutes](research/research-2026-11-16-ci-speed.md): where a CI
  run’s minutes go by job, step, and test, what flakes cost, and the options for the
  fast CI plan

- [What eager startup JavaScript costs](research/research-2026-11-12-eager-startup-script-cost.md):
  measured cost of the scripts a folder page loads before `DOMContentLoaded`

- [Setup flows for `metab` and the native macOS app](research/research-2026-11-11-uv-and-macos-app-install.md):
  the CLI-first and app-first install paths

- [Apparent UI performance for the native app](research/research-2026-11-11-ui-apparent-performance.md):
  what makes the app feel instant, and the evidence behind the stable-layout plan

- [Native app server topology, lifecycle, and agent handoff](research/research-2026-11-10-native-app-server-topology.md):
  one server per folder, warm switching, and handing pages to agents

- [Native macOS app: shells, uv runtimes, and CLI layering](research/research-2026-11-08-macos-app-packaging.md):
  the AppKit shell over `metab` and how it finds a runtime

- [Git status and dirty working-tree browsing](research/research-2026-08-26-git-status-and-dirty-working-trees.md):
  input to the Git status plan

- [fdu and Metabrowser inventory-engine alignment](research/research-2026-08-23-fdu-metabrowser-inventory-engine.md):
  the provider contract the fdu engine will implement

- [Mermaid diagram support](research/research-2026-08-21-mermaid-diagram-support.md):
  input to the Mermaid plan

- [Markdown link navigation across repository browsers](research/research-2026-08-13-markdown-link-navigation.md):
  link dialects and resolution rules, input to the navigation extensions plan

- [Fuzzy file ranking](research/research-2026-07-31-fuzzy-file-ranking.md): the Quick
  Search matcher’s ranking contract and measurements

- [Browser contributor toolchain and distribution](research/research-2026-07-18-browser-contributor-toolchain.md):
  when to evaluate TypeScript, Vite, and Vitest for the raw-source browser build

### Archived Research

- [File patch formats](research/archive/research-2026-08-19-file-patch-formats.md): the
  compatibility survey behind File Diff Format v1
- [Desktop app packaging](research/archive/research-2026-08-16-desktop-app-packaging.md):
  the three-platform survey, superseded for macOS by the native app research
- [Repository cache and open from a Git URL](research/archive/research-2026-08-11-repo-cache-and-git-url-open.md):
  input to the repository library and thin-mirror plans
- [A high-performance file roll-up engine](research/archive/research-2026-08-06-file-rollup-engine.md):
  a pointer to the full research, which lives in the fdu repository
- [Diff view spike results](research/archive/research-2026-07-18-diff-view-spike-results.md):
  July 2026 prototype timings, kept for provenance
- [Web diff viewer architecture and intermediate representations](research/archive/research-2026-07-17-web-diff-viewer-architecture.md):
  the layered model that became File Diff Format v1
- [VS Code extension host](research/archive/research-2026-07-17-vscode-extension-host.md):
  a draft design that no plan adopted

## Reviews

- [Bead and spec audit, 2026-11-14](reviews/review-2026-11-14-bead-and-spec-audit.md):
  every bead closed, updated, or held in the audit after 0.12.0, with its evidence
- [Changes to existing behavior in the v0.12 stack](reviews/review-2026-10-01-v012-changes-to-existing-behavior.md):
  each intended change to v0.11.0 behavior with its changelog entry, pull request, and
  check, and the unintended differences the landing gate found
- [Per-layer review ledger for the v0.12 stack](reviews/review-2026-10-01-v012-stack-review-ledger.md):
  the review each pull request had, its findings and their disposition, and CI on each
  head
- [Test-suite baseline for the v0.12 test review](reviews/review-2026-10-01-test-suite-baseline.md):
  suite size and CI time at three points, with the command behind each figure
- [Inventory stack merge readiness](reviews/review-2026-09-07-inventory-stack-merge-readiness.md):
  the final review of the inventory-engine stack, with serving measurements in
  [`reviews/evidence/`](reviews/evidence/)
- [The pluggable inventory engine](reviews/review-2026-08-31-pluggable-inventory-engine.md):
  defects found while merging the engine stack and a measured regression against `main`
- [Delivery order for Git status, the repository cache, and providers](reviews/review-2026-08-27-delivery-order-for-status-cache-and-providers.md):
  the plans checked against the stated priority order
- [Independent design review of the status, cache, and provider plans](reviews/review-2026-08-27-independent-design-review.md):
  a second opinion on the same material
- [Repository-library phasing and GitHub content model](reviews/review-2026-08-26-repository-library-and-github-model.md):
  separating generic Git caching from GitHub integration
- [Load-time performance and the distance still to cover](reviews/review-2026-08-22-load-time-performance.md):
  the six-round load-time work, its findings, and candidate hypotheses

## QA Runs

The first two are current checklists; the dated runs after them are records.

- [Manual browser checks](qa/qa-2026-11-14-manual-browser-checks.md): what only a person
  in a real browser can judge, run before each release on the public-safe manual corpus
- [macOS app hand checks](qa/qa-macos-app-hand-checks.md): what AppKit, WebKit, and
  macOS decide, checked against a built app after a change to the behavior they cover
- [Files totals layout, 2026-11-16](qa/qa-2026-11-16-files-totals-layout.md): the
  measurements behind the Files totals’ layout rule, before and after, in Chrome
- [WebKit measurement gate, 2026-11-11](qa/qa-2026-11-11-webkit-measurement-gate.md):
  the app’s WebKit run against Chrome’s large-content bounds, which failed, with every
  figure and the print and drop checks
- [0.12.0 release preparation](qa/qa-2026-11-07-v012-release-preparation.md): the
  integrated candidate, installation evidence, and release gates before the 0.12.0 tag
- [v0.12 alpha acceptance on the integrated stack](qa/qa-2026-09-24-v012-alpha-acceptance.md):
  an installed-wheel run of the manual matrix, with per-row results
- [v0.12 repository library and HTML trust](qa/qa-2026-09-19-v012-repository-library.md):
  the step-by-step acceptance procedure those runs followed

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
