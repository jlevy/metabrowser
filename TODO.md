# Roadmap

This is the top-level map of Metabrowser’s work: what is planned, what is in flight, and
which document carries the detail.
It sits above the specs rather than duplicating them.
Plans live in [`docs/project/specs/`](docs/project/README.md): `active/` while a plan
still owes work, `done/` once it is delivered, with follow-ups tracked as beads.
Checked items below are supported today; unchecked items are planned work.

## Release State

The latest release is 0.12.0, tagged on 2026-11-08 and published on 2026-11-09. It adds
the repository mirror and GitHub browsing: open a Git or GitHub URL, read pull requests
from the Pulls tab, and reopen what was fetched while offline.
Work merged since then is listed under Unreleased in [CHANGELOG.md](CHANGELOG.md) and in
[changelog.d/](changelog.d/README.md).
The owner-deferred 0.12 checks are open beads under `mb-425f`, among them the landing
differential (`mb-2g6f`) and the human sign-off matrix (`mb-etqi`).

## Where Work Stands

| Area | Plan | Status |
| --- | --- | --- |
| Native macOS app | [Native macOS app](docs/project/specs/active/plan-2026-11-10-native-macos-app.md) | An alpha AppKit shell over `metab` builds from source in `apps/macos/`; a signed download and the agent front door are planned |
| Apparent performance | [Instant transitions and stable layout](docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md) | Approved; each step is a measured performance-loop round |
| Load-time performance | [End-to-end load time](docs/project/specs/active/plan-2026-08-21-load-time-performance.md), [flat-tree delivery cost](docs/project/specs/active/plan-2026-09-15-flat-tree-delivery-cost.md) | On-demand assets, progressive inventory delivery, the startup-script budget, and per-page catalog hashing are implemented; broader goals remain |
| Inventory engine | [Pluggable inventory engine](docs/project/specs/active/plan-2026-08-23-pluggable-inventory-engine.md), [provider refactor and fdu adoption](docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md) | The Python reference provider ships behind the provider contract; the fdu provider is planned |
| Repository library | [Repository library and open from a Git URL](docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md) | An owner-only cache of Git stores, served as immutable pins under the untrusted profile with background refresh, shipped in 0.12.0 per the [thin-mirror plan](docs/project/specs/done/plan-2026-09-23-v012-thin-mirror.md); SSH, a repository catalog and chooser, and very large repositories remain |
| GitHub pull requests | [Pulls tab](docs/project/specs/done/plan-2026-10-01-github-pulls-tab.md), [review from a checkout](docs/project/specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md) | The PR catalog, Pulls tab, PR pages, checkout-backed comparisons, and native-stack membership are implemented; store conversions, inline review anchors, and broader hosted-review projections remain |
| Git surfaces | [General diff rendering](docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md), [Git status and working-tree diffs](docs/project/specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md) | The Commits tab, commit pages, and diff rendering are implemented; working-tree status and `/compare/` remain |
| CLI parity and goldens | [Functional UI parity](docs/project/specs/active/plan-2026-09-10-functional-ui-cli-parity.md), [API envelope contract](docs/project/specs/active/plan-2026-08-30-api-schema-and-contract.md) | The route, kind, model, persisted-state, and functional-aspect gates are enforced; migrating the remaining UI behavior and a schema for the envelopes remain |
| File search | [Quick Search](docs/project/specs/active/plan-2026-07-17-scalable-file-search.md) | The client file finder and PR completions are implemented; full-text search is planned |
| Tabular data and SQLite | [Tabular data browsing and live SQLite](docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md) | Draft; a generic table plugin over CSV, record lists, and SQLite, with its key decisions open |
| Markdown navigation | [Navigation extensions](docs/project/specs/active/plan-2026-08-13-markdown-navigation-extensions.md) | Baseline delivered; extensions partly delivered, with the remaining scope below |
| Mermaid diagrams | [Mermaid diagram rendering](docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md) | Draft; on-demand loading exists, but the Mermaid module entry still needs a dynamic import or a module entry in `asset-loader.js` |
| File actions | [Menu primitives and gated file actions](docs/project/specs/active/plan-2026-08-06-menu-primitives-and-file-actions.md) | Shared modal foundation delivered; action menus and file mutations planned |
| File editing | [Opt-in trusted-local file editing](docs/project/specs/active/plan-2026-07-16-trusted-local-file-editing.md), [editor plugin editing contract](docs/project/specs/active/plan-2026-07-17-editor-plugin-editing-contract.md) | Startup capability gate implemented; rename, move, trash, and editor plugins planned |
| Scan state | [Scanning state and recent directories](docs/project/specs/active/plan-2026-07-16-scanning-state-and-recent-directories.md) | Scan status, counts, and pending directory aggregates implemented; recent-directory items remain |
| CI speed | [Fast CI](docs/project/specs/active/plan-2026-11-16-fast-ci.md) | Approved for Phases 1 and 2 on 2026-11-16; measured in [Why CI takes twenty minutes](docs/project/research/research-2026-11-16-ci-speed.md); Phase 1 is implemented by jlevy/metabrowser#499 and Phase 2 by jlevy/metabrowser#504, and Phase 3 is next |
| Documentation | [Documentation from first principles](docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md) | Implemented; one owner per fact, task guides, and architecture documents for every layer |

Delivered plans keep their record in [done plans](docs/project/README.md#done-plans).

## Repository and GitHub Follow-Ups

- [ ] Acquire SSH Git URLs into the shared mirror (`mb-bi2c`, deferred)
- [ ] Generic cache management: catalog, refresh, size accounting, and purge (`mb-0ybg`)
- [ ] An in-app repository chooser and session switching (`mb-vmzy`)
- [ ] Measured acquisition and deepening for very large repositories (`mb-dqvj`)
- [ ] Anchor pull-request review threads in the Changes diff (`mb-rldc`, deferred)
- [ ] Open cached pull-request timeline commits locally (`mb-g47g`)
- [ ] GitHub issues and timelines (`mb-9rrc`, deferred) and a GitLab provider
  (`mb-51uj`, deferred)

## Markdown Navigation: What Is Not Done

The
[navigation baseline](docs/project/specs/done/plan-2026-08-13-markdown-link-navigation.md)
is delivered: one `/view/<path>` route per file and folder, GitHub-style relative
resolution, deterministic Obsidian wiki lookup with visible ambiguous and missing
states, bounded transclusion, verified same-repository GitHub URL localization,
configured static-site route adapters, and a typed `window.metabrowser.navigation`
boundary.

Remaining work from the
[extensions plan](docs/project/specs/active/plan-2026-08-13-markdown-navigation-extensions.md):

- [x] Address a line range inside a source view: shipped as GitHub-style `#L` fragments
  (#235, #239), without the reserved `_mb_` keys.
- [ ] Interpret the reserved `_mb_` query namespace in the URL codec (`mb-npkt`). The
  baseline reserved the namespace and pinned it with codec tests but interprets no key,
  so query stays verbatim passthrough; nothing consumes it yet.
- [ ] Evaluate frontmatter alias target lookup.
  Still a question, not a commitment.
- [ ] Add explicit mounted roots for multi-repository and cross-vault navigation.
- [ ] Add graph analysis through a bounded server route backed by a KPress-owned intent
  manifest, as described in
  [functional UI parity](docs/project/specs/active/plan-2026-09-10-functional-ui-cli-parity.md).

One navigation gap sits outside that plan:

- [ ] Make navigation tree rows real links.
  Tree rows are `div` elements with click handlers, so the primary navigation surface
  lacks the native link behavior of rendered Markdown links: middle-click, copy address,
  and status-bar preview.

## Core Browser

- [x] Make folders first-class with an
  [extensible Overview panel stack](docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md):
  File types is always present, README is conditional, and Treemap is a peer view
- [ ] Add a Files listing as another peer folder view beside Overview and Treemap,
  rather than as a large panel inside Overview
- [ ] Modularize the browser shell and static assets so layout, navigation, and plugin
  rendering can evolve independently
- [ ] Cover DOM lifecycle browserlessly against the production JavaScript (`mb-wgka`)
  and pin the versioned payload contracts with a schema (`mb-xzb1`)
- [x] Add
  [contextual keyboard help and accessible tree navigation](docs/project/specs/done/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md)
  through one shortcut registry, with the
  [Shift key reveal](docs/project/specs/done/plan-2026-11-11-shift-key-reveal-and-keymap.md)
- [x] Add the client-only
  [Quick Search file finder](docs/project/specs/active/plan-2026-07-17-scalable-file-search.md)
  over a complete live catalog of non-gitignored files
- [ ] Add bounded server-side filename and full-text search providers, then evaluate
  optional persistent indexing only if measured catalog sizes require it
- [x] Give every file and folder a reloadable
  [`/view/<path>` URL](docs/project/specs/done/plan-2026-08-13-markdown-link-navigation.md)
  with GitHub and Obsidian link resolution
- [ ] Add multiplexed, fair live-tail streaming across multiple files
- [ ] Define a generic writer event-log backend for append-only generated files
- [ ] Enforce and report explicit time, memory, item-count, and payload-size budgets for
  directories containing hundreds of thousands of entries

## Git Surfaces

- [x] Add the Commits tab and commit pages over a read-only Git collection API
- [x] Implement the
  [repository mirror and GitHub browsing](docs/project/specs/done/plan-2026-09-23-v012-thin-mirror.md):
  a versioned local cache that opens or reuses Git and GitHub URLs at a selected branch,
  tag, or commit, with pull-request pages, catalog navigation, checkout-backed
  comparisons, and native-stack metadata
- [ ] Add read-only
  [Git status and working-tree diffs](docs/project/specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md),
  with conflicts, staged, unstaged, and untracked groups above history
- [ ] Build the `/compare/<base>..<head>` route, which
  [the URL grammar](docs/architecture.md) specifies and nothing serves yet

The Git routes only read, every `git` subprocess is bounded by
`GIT_SUBPROCESS_TIMEOUT_S` and `GIT_SUBPROCESS_MAX_BYTES`, and the history and commit
routes carry their own named limits in `settings.py`.
[File Diff Format v1](docs/project/architecture/file-diff-format/file-diff-format.md)
has a conformance corpus and an apply oracle that checks a produced document against
Git’s own trees.

## Plugin Platform

- [ ] Design and implement the
  [editor plugin editing contract](docs/project/specs/active/plan-2026-07-17-editor-plugin-editing-contract.md)
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
- [ ] Show
  [recent directories](docs/project/specs/active/plan-2026-07-16-scanning-state-and-recent-directories.md)
  without presenting incomplete trees as empty

File mutation is disabled by default.
These workflows do not change Metabrowser’s trusted-client, local-filesystem security
model.

## Editor Integration

- [ ] A VS Code extension host, with a native tree, one embedded content panel, and a
  supervised server; an
  [archived draft](docs/project/research/archive/research-2026-07-17-vscode-extension-host.md)
  exists, and no plan

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
The
[archive plan](docs/project/specs/active/plan-2026-11-24-archive-contents-and-browsing.md)
covers ZIP and the tar family in two phases.

## Browser Defense in Depth

- [x] Settle the
  [HTML rendering and content-trust model](docs/project/specs/done/plan-2026-08-06-html-rendering-and-trust-model.md):
  sandboxed `/raw` responses, same-origin proof on `/api`, and the `--untrusted` profile
- [ ] Send a strict Content Security Policy when active content is on, as the shell
  already does when `--no-active-content` or `--untrusted` turns it off (`mb-gluj`)

The renderer sanitizes untrusted document HTML, and event data is escaped before DOM
insertion.
A Content Security Policy is still useful defense in depth because the trusted
local server can read files within its configured root.

## Engineering Ratchets

- [ ] Remove the remaining scoped Python type-checking exceptions
- [ ] Graduate the remaining legacy JavaScript into strict TypeScript
- [ ] Remove the remaining exact-file Biome exceptions as those files are modernized

The release baseline enforces Ruff, BasedPyright, Biome, TypeScript, pytest, dependency
audits, documentation formatting, source-distribution checks, wheel checks, and
installed-wheel CLI and plugin-doctor smoke tests.
These ratchets tighten known legacy surfaces without weakening the enforced baseline.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
