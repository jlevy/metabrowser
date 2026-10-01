# Roadmap

This is the top-level map of Metabrowser’s work: what is planned, what is in flight, and
which document carries the detail.
It sits above the specs rather than duplicating them.
Plans live in [`docs/project/specs/`](docs/project/README.md) — `active/` while a plan
still owes work, `done/` once it is delivered, with follow-ups tracked as beads.
Checked items below are supported today; unchecked items are planned work.

## Where Work Stands

| Area | Plan | Status |
| --- | --- | --- |
| Markdown navigation | [Navigation extensions](docs/project/specs/active/plan-2026-08-13-markdown-navigation-extensions.md) | Baseline shipped; three items remain — see below |
| File search | [Quick File finder and search providers](docs/project/specs/active/plan-2026-07-17-scalable-file-search.md) | Client finder shipped; server providers planned |
| HTML trust model | [Full-page HTML rendering and trust model](docs/project/specs/active/plan-2026-08-06-html-rendering-and-trust-model.md) | Sandboxed `/raw`, same-origin `/api` proof, and `--untrusted` landed through #209; remaining plan work is tracked separately |
| File actions | [Menu primitives and gated file actions](docs/project/specs/active/plan-2026-08-06-menu-primitives-and-file-actions.md) | Draft |
| File editing | [Opt-in trusted-local file editing](docs/project/specs/active/plan-2026-07-16-trusted-local-file-editing.md) | Draft |
| Scan state | [Scanning state and recent directories](docs/project/specs/active/plan-2026-07-16-scanning-state-and-recent-directories.md) | Draft |
| Git surfaces | [Git graph nav panel](docs/project/specs/active/plan-2026-08-06-git-graph-view.md), [general diff rendering](docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md), [Git status and working-tree diffs](docs/project/specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md) | Graph panel, read-only Git API, and diff rendering shipped; working-tree status and `/compare/` remain, after CLI parity |
| Repository library | [Repository library and open from a Git URL](docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md) | v0.11.0 released. v0.12 is on unmerged stack [#218](https://github.com/jlevy/metabrowser/stack/218): an owner-only cache of full-clone mirrors acquired from `file://` and `https://` origins and served as immutable pins under the forced untrusted profile, with background refresh and pin switching, per the [thin-mirror plan](docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md). SSH, the catalog, the chooser, and very large repositories remain |
| Hosted review and GitHub | [Hosted review model and GitHub provider](docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md), [architecture](docs/project/architecture/arch-hosted-review-model.md) | The provider-neutral Hosted Review Format records and their contract gates were removed from stack [#218](https://github.com/jlevy/metabrowser/stack/218) and are kept, unmaintained, on the `reference/v012-hosted-review` branch, tagged `reference/v012-hosted-review-2026-09-30`; the [thin-mirror plan](docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md) stores pull-request data as plain validated JSON records in the GitHub plugin. GitHub URLs, pull-request records, and the pull-request page are on the stack; the pull-request list, its panel, and inline review anchors are deferred beyond v0.12. [Alpha testing](docs/project/specs/active/plan-2026-09-22-v012-alpha-testing.md#landing-status) lists what remains before landing |
| Editor host | [VS Code extension host](docs/project/architecture/arch-vscode-extension-host.md) | Architecture only; no plan yet |
| Load-time performance | [End-to-end load time](docs/project/specs/active/plan-2026-08-21-load-time-performance.md) | Draft |
| Mermaid diagrams | [Mermaid diagram rendering](docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md) | Draft; depends on load-time Phase 1 |
| CLI parity and goldens | [CLI parity and golden coverage](docs/project/specs/done/plan-2026-08-21-cli-parity-and-golden-coverage.md), [functional UI parity](docs/project/specs/active/plan-2026-09-10-functional-ui-cli-parity.md), [CLI-first delivery](docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md) | The route, kind, model, persisted-state, and functional-aspect gates have landed on `main` for the v0.10.0 release candidate. Git status, repository-cache state, and GitHub-provider behavior extend those same checked surfaces |

Delivered plans keep their record in [done plans](docs/project/README.md#done-plans):
the navigation baseline, folder Overview and file-type summaries, semantic file-type
families, the shared taxonomy, filter controls, the bounded binary byte preview, the
flat `metab` CLI, and the v0.1.0 package.

## v0.12.0 Repository and GitHub Slice

v0.12.0 lets a user paste a GitHub repository, file, commit, or pull-request URL and
browse it from a local mirror: instant once seen, usable offline, and refreshed in the
background.
[Thin Mirror for Git and GitHub Browsing](docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md)
is the design, and its Delivery section maps each step to its pull request (epic
`mb-hall`).

The work is one unmerged stack of pull requests above the released v0.11.0 `main`. The
2026-09-24 acceptance run on an installed wheel is recorded in
[QA: v0.12 alpha acceptance](docs/project/qa/qa-2026-09-24-v012-alpha-acceptance.md).
[Landing status](docs/project/specs/active/plan-2026-09-22-v012-alpha-testing.md#landing-status)
lists what remains before the stack lands, which waits for the user’s approval
(`mb-n2ro`).

Deferred beyond v0.12.0 by the user’s 2026-09-23 decision: SSH acquisition (`mb-bi2c`),
the pull-request list and its panel (`mb-lnkl`, `mb-iw1v`), inline review anchors
(`mb-rldc`), attaching a user’s own checkout (`mb-cbak`), and rebind.

The complete roadmap remains larger than this release slice.
Full generic cache management (`mb-0ybg`), the repository chooser (`mb-vmzy`), GitHub
issues and timelines (`mb-9rrc`), stacked PR projections (`mb-glxc`), measured
very-large-repository acquisition (`mb-dqvj`), and a GitLab provider (`mb-51uj`) remain
tracked follow-ups.

## Markdown Navigation: What Is Not Done

The
[navigation baseline](docs/project/specs/done/plan-2026-08-13-markdown-link-navigation.md)
is delivered: one canonical `/view/<path>` route per file and folder, exact GitHub-style
relative resolution, deterministic Obsidian wiki lookup with visible ambiguous and
missing states, bounded transclusion, verified same-repository GitHub URL localization,
configured static-site route adapters, and a typed `window.metabrowser.navigation`
boundary.

Three items from the
[extensions plan](docs/project/specs/active/plan-2026-08-13-markdown-navigation-extensions.md)
remain, and nothing else in that plan is outstanding:

- [ ] Interpret the reserved `_mb_` query namespace in the URL codec.
  The baseline reserved the namespace and pinned it with codec tests but interprets no
  key, so query stays verbatim passthrough.
  This blocks the next item.
- [ ] Add source-view line-location targets (`_mb_view`, `_mb_lines`), so a link can
  address a line range inside a rendered or source view.
- [ ] Evaluate frontmatter alias target lookup.
  Still a question, not a commitment.
- [ ] Add explicit mounted roots for multi-repository and cross-vault navigation.

Two known gaps sit outside that plan and are not regressions:

- [ ] Make navigation tree rows real links.
  Rendered Markdown links are now genuine anchors, but tree rows remain `div` elements
  with click handlers, so the primary navigation surface still lacks the native link
  behavior — middle-click, copy address, and status-bar preview — that document links
  gained.
- [ ] Reconcile `/raw?path=<path>` with the path-shaped `/view/<path>` route.
  Tracked under the HTML trust-model work, since that plan also changes how `/raw`
  responses are served.

## Core Browser

- [x] Make folders first-class with an
  [extensible Overview panel stack](docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md):
  File types is always present, README is conditional, and Treemap is a peer view
- [ ] Add a Files listing as another peer folder view beside Overview and Treemap,
  rather than as a large panel inside Overview
- [ ] Modularize the browser shell and static assets so layout, navigation, and plugin
  rendering can evolve independently
- [ ] Add real-browser coverage for DOM behavior and versioned payload contracts
- [x] Add
  [contextual keyboard help and accessible tree navigation](docs/project/specs/done/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md)
  through one shortcut registry
- [x] Add the client-only
  [Quick File finder](docs/project/specs/active/plan-2026-07-17-scalable-file-search.md)
  over a complete live catalog of non-gitignored files
- [ ] Add bounded server-side filename and full-text search providers, then evaluate
  optional persistent indexing only if measured catalog sizes require it
- [x] Give every file and folder a canonical, reloadable
  [`/view/<path>` URL](docs/project/specs/done/plan-2026-08-13-markdown-link-navigation.md)
  with GitHub and Obsidian link resolution
- [ ] Add multiplexed, fair live-tail streaming across multiple files
- [ ] Define a generic writer event-log backend for append-only generated files
- [ ] Enforce and report explicit time, memory, item-count, and payload-size budgets for
  directories containing hundreds of thousands of entries

## Git Surfaces

- [x] Design a Changes surface and comparison API from the
  [web diff viewer research](docs/project/research/research-2026-07-17-web-diff-viewer-architecture.md),
  then stage its delivery behind a written plan
- [x] Add a Git graph navigation panel over a read-only Git collection API
- [ ] Add read-only
  [Git status and working-tree diffs](docs/project/specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md),
  with conflicts, staged, unstaged, and untracked groups above history
- [ ] Build the `/compare/<base>..<head>` route, which
  [the URL grammar](docs/architecture.md) specifies and nothing serves yet
- [ ] Land the v0.12.0
  [repository mirror and GitHub browsing](docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md):
  a versioned local cache that opens or reuses Git and GitHub URLs at a selected branch,
  tag, or commit, with pull-request pages; follow with the pull-request list, SSH, full
  cache management, a repository chooser, issues, and stacked PRs

Both entered core behind written plans, with the read-only boundary and bounded-cost
model those plans required: the Git routes only read, every `git` subprocess is bounded
by `GIT_SUBPROCESS_TIMEOUT_S` and `GIT_SUBPROCESS_MAX_BYTES`, and the history and commit
routes carry their own named limits in `settings.py`.
[File Diff Format v1](docs/project/architecture/file-diff-format/file-diff-format.md)
adds a conformance corpus and an apply oracle that checks a produced document against
git’s own trees.

## Plugin Platform

- [ ] Design and implement the
  [editor plugin editing contract](docs/project/architecture/arch-editor-plugin-editing-contract.md)
  without weakening the default read-only plugin contract
- [ ] Document stable extension points for custom renderers, metadata, actions, and
  optional storage adapters as each capability graduates into the public API

Metabrowser’s core stays independent of domain-specific renderers.
Applications can ship their own plugin packages while depending only on the documented
public plugin API. `PLUGIN_SDK_VERSION` is the enforced contract between host and
plugin; it is bumped when that contract breaks, never shimmed.

## Trusted-Local Workflows

- [ ] Add
  [opt-in file operations](docs/project/specs/active/plan-2026-07-16-trusted-local-file-editing.md)
  with containment, conflict handling, and trash-first semantics
- [ ] Add
  [menu primitives and gated file actions](docs/project/specs/active/plan-2026-08-06-menu-primitives-and-file-actions.md)
  so an action surface exists before any mutating operation ships
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

Metabrowser treats compression as a transport layer around one logical file.
For example, `report.html.zst` should classify and render like `report.html` while all
reads remain bounded.

- [x] Gzip (`.gz`)
- [x] Raw zlib streams (`.zlib`)
- [ ] Zstandard (`.zst`)
- [ ] Evaluate common single-file formats such as xz (`.xz`), bzip2 (`.bz2`), and Brotli
  (`.br`) as real file-format demand appears

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

- [ ] Settle the
  [HTML rendering and content-trust model](docs/project/specs/active/plan-2026-08-06-html-rendering-and-trust-model.md),
  building on the sandboxed `/raw` responses, same-origin proof on `/api`, and
  `--untrusted` profile that landed through #209
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
