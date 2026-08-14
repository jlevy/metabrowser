# Changelog

All notable changes to Metabrowser are documented here.

## Unreleased

Compatibility policy:

- Development guidance now forbids speculative compatibility layers.
  An alias, fallback branch, shim, deprecation window, or transitional duplicate field
  requires a consumer that cannot be updated in the same commit, named in the pull
  request. The server, browser shell, and built-in plugins ship as one artifact behind an
  uncached page with content-versioned asset URLs, so there is no version skew for such
  code to protect against.
- Removed the file-type compatibility layer that policy forbids.
  The `/api/rollup` response no longer carries `type_tallies`; consume
  `file_type_breakdown`. The `type_top` query parameter and its `mb.fetchRollup` option
  are gone in favor of `remaining_top`, and `RollupOptions` and `InventoryIndex.rollup`
  take `remaining_top` rather than `type_top`.
- Removed the `ROLLUP_FILE_TYPE_NAMED_LIMIT` and `ROLLUP_FILE_TYPE_RAW_LIMIT` browser
  settings; use `ROLLUP_FILE_TYPE_FILENAME_LIMIT` and
  `ROLLUP_FILE_TYPE_REMAINING_LIMIT`.
- Removed the `file-type-taxonomy-compat-v1` settings projection and
  `serialize_file_type_taxonomy()`, which no longer had a consumer.
- Removed the `mb.fileTypes.categories` and `mb.fileTypes.categoryForFile` aliases; use
  `groups` and `groupForFile`. The browser SDK carries no deprecation window and is
  versioned with the release.

## 0.4.0

Folder Overview and Treemap:

- Every directory now opens with an extensible Overview whose always-present Files
  summary appears above a rendered README when the folder contains one.
  Files and README share responsive alignment and independently collapsible section
  headings, while the README retains the ordinary Markdown document surface.
- The Files summary compares exact file counts and byte totals with percentages and
  independently normalized bars.
  A leading Total row and conditional Ignored row make the selected population explicit,
  including deliberate empty, pending, partial, incompatible, and unavailable states.
- Treemap is now a peer folder view with Bytes and Files sizing, a Show ignored
  checkbox, adaptive labels, and hierarchy-preserving hover.
  File icons and colors match Overview and navigation, folder labels end in `/`, and
  folder navigation keeps the Treemap active.

File types and folder summaries:

- One versioned File-Type Registry now drives folder Overview, navigation filters,
  Treemap colors, and the public browser SDK. Common extensions roll up into readable
  semantic families under Code, Documentation, Data, Logs, Archives, Media, and Other;
  singleton families remain expandable to their exact extension.
- The Files summary now explains extensionless and unknown populations.
  No extension expands to exact basenames and Other types expands to raw logical
  extensions; each list is capped at 20 and conserves omitted files and bytes in an
  exact Others row.
- Logical extensions are ASCII-case-insensitive, treat bare dotfiles as extensionless,
  and retain at most two trailing components.
  This keeps `.js.map` and `.tar.gz` useful without fragmenting reports into names such
  as `.umd.min.js.map`. This intentionally merges uppercase suffixes into their
  lowercase identities: `README.MD` joins `.md`, `photo.PNG` joins `.png`, and `.C`
  joins `.c` rather than retaining a case-distinct language bucket.
- Log files include `.log`, `.jsonl`, and `.ndjson`; archives and common image, video,
  audio, and font formats gain explicit families.
  JSON Lines retains its data-analysis identity and SVG retains its markup identity
  while using those display families.
- Registry, Breakdown v1, JSON Schemas, conformance cases, and a checked export tool now
  form a self-contained compatibility packet that `fdu` can adopt without a sibling
  checkout or network access.
  Packet export prunes stale destination content, verifies exact manifest membership and
  hashes before returning, and supports an independent `--verify` mode.

Navigation, plugins, and reliability:

- The file-type chooser uses the same registry-backed hierarchy as Overview: broad
  groups, semantic families, and exact canonical or raw extensions can be selected
  independently, with parent choices selecting their children.
- The public browser SDK adds immutable file-type definitions, bounded folder-rollup
  helpers, folder context, view-aware navigation, shared formatters and file identity,
  active-view state, and an extensible folder-panel registry.
- Folder rollups run off the event loop and reuse the inventory snapshot instead of
  crawling the filesystem again.
  Rapidly rebuilt directories are reconciled against the current filesystem so stale
  watcher deletes cannot leave an Overview blank, and brief local navigation no longer
  flashes loading chrome.

## 0.3.0

Filtering and file navigation:

- The Files pane gains one always-available filter bar for age, type, minimum size, and
  gitignored visibility, with Docs, Code, and Data presets and a one-click Clear action.
  The separate Recent tab is folded into this pane so every dimension composes in one
  place.
- Age filters query the complete inventory rather than only expanded folders.
  Each age row shows its cumulative index-wide file count, refreshed when the menu
  opens. Capped results prioritize tracked files over ignored dependency churn, report
  the shortfall, and continue to incorporate filesystem changes while the view is open.
- **Live** now has one general definition: every file modified in the past 90 seconds.
  The server owns that cutoff, and expired rows disappear even when no later filesystem
  event arrives. Agent-log activity remains a separate capability that supplies active
  badges and live tailing for supported logs.
- Filter controls are keyboard navigable, expose their state through ARIA, keep the
  active value visible when the drawer is closed, and share the documented design-system
  primitives with plugin views.
- Agent-log event-type filters use the same additive chips, including counts and a
  visible selected state for dynamically discovered record types.
- Filter selections are transient view state and reset on every page load instead of
  leaking through a host-wide browser preference.
  Durable appearance choices such as theme and typography remain shared across
  Metabrowser instances.
- Recency overlays no longer grow after returning to the full tree, compound extensions
  match consistently on streamed rows, and filtered tallies update under every
  dimension.

Quick File navigation:

- A new Quick File palette opens with `/` or `T` and jumps to any file by name or path
  fragment, the way go-to-file works on GitHub.
  Matching is fuzzy and deterministic, ranking whole-word, path-boundary, and camel-case
  hits above scattered letters, and the ranking contract is pinned by a fixture set.
- The palette searches every non-gitignored file under the root, not just the subtree
  the browser happens to have expanded.
  A one-shot `GET /api/catalog` endpoint serves a minimal gzipped payload with ETag
  revalidation, and `catalog.change` events on the existing stream keep it live.
- An open search converges as coverage grows: files that arrive after the query was
  typed join the visible results instead of waiting for another keystroke.
  The status line distinguishes complete coverage from a walk still in progress or
  stopped at the file cap.
- Results hold their previous contents until real ones replace them, so the list no
  longer flickers empty on each keystroke, and a row stays inert until the results it
  describes are the ones on screen.
  A result reads as one line of navigation: the filename at full contrast, the parent
  path beside it muted.
- Catalog upkeep costs the same whether the palette is open or closed, and a batched
  directory removal now costs an entry’s depth rather than the size of the removal
  batch. Removing 2,000 directories from a 100,000-entry catalog went from 1441ms to
  52ms, and stays flat as the batch grows.
- Quick File catalog recovery now closes the last reconnect gap: if a restarted server
  is still scanning, its terminal state triggers one authoritative membership fetch
  before stale paths can survive.
  This also repairs capped inventories while keeping their root coverage labeled
  incomplete.

Document rendering:

- KPress is upgraded through `0.3.2`. Version 0.3.1 adds the `toc_rail` option this
  repository’s host CSS had been standing in for.
  The host reimplementation is deleted, so the reading column holds one position whether
  or not a document earns a table of contents.
- Version 0.3.2 fixes the content-card breakpoint for a narrow preview pane inside a
  wider browser window and restores the intended lighter code size inside wide tables.
- KPress now owns the whole document size ramp.
  The host had collapsed graded size families onto single values, which rendered inline
  code inside a table larger than the cell around it; prose code is now 12.3px, table
  cells 14.25px, and code in a table cell 12.3px.
- Unscoped `.md-body` chrome rules no longer reach inside embedded documents.
  Twenty-six of them had been capping the reading column at 50em, overriding KPress’s
  list rhythm, and constraining blockquotes.
  `.md-body` remains the documented convention for plugins that render their own
  Markdown.
- Embedded documents are square.
  KPress’s own box radii are bridged to `--radius-document`, so code blocks, tables, and
  callouts no longer sit rounded inside square panes; pills and circles keep their
  shape.

Design system:

- Chrome icons draw at one `--icon-glyph` size inside a 16px alignment box, and
  icon-only controls collapse into a single `.icon-btn` primitive that raises a surface
  and hairline border only while hovered, focused, or holding a menu open.
- Keyboard keys get one `.kbd` component, and a chrome typography rule puts navigation
  text — file paths, parent paths, ancestor segments, and shortcut hints — in the same
  sans face as the rows they point at, leaving mono for the user’s own content.
  A contract test enforces the three named exceptions.

Reliability:

- Symbolic links now appear as explicit, non-expanded leaves with the standard link
  icon. They never contribute file counts or type tallies, never graft a target directory
  into the served tree, and report whether an unavailable target is missing, outside the
  served root, or otherwise unreadable.
- Live filesystem updates now replace an existing row when its path changes between a
  file, directory, and symbolic link, including removing a former directory’s rendered
  descendants before mounting the replacement.
- Ctrl-C during command startup or an in-progress filesystem scan now exits quietly with
  status 130 instead of printing a traceback or waiting on a background thread.
  A second Ctrl-C remains an immediate forced exit if another operation cannot finish
  cooperatively.
- Live updates remain correct when a large filesystem burst fills a bounded event queue.
  The server replaces the incomplete backlog with a resynchronization marker, and each
  affected browser reconnects with bounded exponential backoff for a fresh inventory
  snapshot instead of remaining open with stale state or reconnecting in a tight loop.
- Folder totals that remain pending now produce a bounded client/server diagnostic and
  recover through a fresh root tally.
  The tracked/ignored split stays pending until its inventory snapshot is complete,
  tally values and scan status stay aligned, and a filter change during recovery cannot
  restore a stale view.
- `metab ROOT --check-api` runs the application in-process and validates the initial,
  filtered, cleared, and completed navigation responses without opening a browser.
- Default server output no longer reports routine lifecycle events, expected concurrent
  inventory conflicts, protected directories, or sub-threshold helper timings.
  Slow requests, long inventory scans, plugin problems, and operational failures remain
  visible, while `--log-level debug` retains the detailed trace when needed.

Security documentation:

- SECURITY.md now states the content trust model: application surfaces (the shell,
  static assets, `/api`, and plugin assets) are first-party code, browsed content is
  not, and browsed content never executes inside the application page.
- Two boundaries are documented as **not yet enforced**, so the trusted-local guidance
  stays operative until they are: `/raw` serves in-root files on the application origin
  with no sandboxing, and `/api` routes take no proof that a request came from the
  application’s own pages.
  A tracked plan closes both with an opaque content origin, same-origin proof on `/api`,
  and an `--untrusted` profile.

Agent Skill:

- The skill now prefers a locally installed `metab` and falls back to
  `uvx metabrowser@latest`, instead of reaching for the runner first.
  The zero-install guarantee is unchanged; an agent that already has Metabrowser no
  longer pays a `uvx` resolve.
- The skill no longer carries a version pin, so an installed copy does not go stale
  between releases. Release cool-off is enforced by uv configuration instead
  (`exclude-newer`, or `UV_EXCLUDE_NEWER`), which is read from the environment the agent
  runs in rather than from this repository.
- The skill declares its `compatibility` requirement (a local `metab`, or uv with
  network access on first use).
- The skill states that serving blocks until the server is stopped, so an agent
  backgrounds it and reports the printed URL instead of hanging on the most common
  operation, and that passing a file selects it inside its parent directory.
- The release workflow no longer requires the skill to name the release version, and
  still keeps the worked pin examples in the README and installation guide current.
- The README leads with the skill: its install command now sits directly under the
  introduction instead of below the plugin documentation.

Contributor workflow:

- Repository-wide checks ask git for the file set instead of walking the filesystem and
  naming skipped trees by hand, so a newly ignored tree is excluded in one place.
  Read-only third-party checkouts under `attic/` and agent worktrees checked out inside
  the repository are excluded from doc lint, codespell, Biome, and the sdist.

## 0.2.0

Flat single-command CLI:

- Serving is now the default operation: `metab .` serves the current directory the way
  `open .` opens a folder on macOS. The `serve`, `walk`, `plugins`, and `remote`
  subcommands are removed and replaced by mode flags on one command: `--walk`,
  `--remote HOST`, `--plugins`, `--plugin NAME`, and `--doctor`.
- Exactly one mode applies per invocation.
  Options explicitly passed outside their mode are rejected as usage errors, and
  `--help` groups options by mode.
- This is a breaking change with no compatibility aliases: scripts that invoked a
  subcommand spelling must drop `serve` or switch to the matching mode flag.
  `metab --remote` starts the remote side with the flat syntax, so both hosts need
  Metabrowser 0.2.0 or newer.
- The Agent Skill, README, and installation guide pin `uvx metabrowser@0.2.0`, the first
  release with the flat CLI.

KPress embedding and visual consistency:

- KPress is upgraded to `0.3.0` and its declarative fragment architecture.
  Metabrowser owns one root theme attribute and one root type-size hook, fragments are
  theme-agnostic, the KPress asset manifest is authoritative, and host-side heading,
  bullet, theme-restamping, resolver-filtering, and numeric-table workarounds are
  removed.
- Embedded document prose is now 15px, down from 17px and one step above the 14px app
  body. KPress derives headings from that base, while proportional host tokens keep code
  and secondary text tied to it, so the document hierarchy stays stable when the browser
  root size changes.
- Embedded document navigation now matches KPress’s polished static-site treatment:
  compact hierarchy and active states in the narrow drawer, plus a borderless docked
  rail at the wide document breakpoint.
- Theme changes now keep embedded KPress content, full-file syntax highlighting, and
  plugin charts aligned with the Metabrowser chrome.
  The host owns the complete Highlight.js palette with WCAG AA contrast checks in both
  themes. Token-colored SDK and built-in canvas charts repaint when the resolved palette
  changes and release their theme subscriptions through the existing chart `destroy()`
  lifecycle.

Reliability and distribution:

- Pressing Ctrl-C twice now forces an immediate server exit without non-actionable
  Uvicorn cancellation tracebacks.
  Graceful shutdown keeps normal error reporting, and every exit path restores the
  process-global logger state for later in-process runs.
- Repository and package metadata now state AGPL-3.0-or-later explicitly, matching the
  license obligation that has always applied through the required KPress runtime.
  Vendored browser components remain under their own licenses in `NOTICE.md`, and built
  distributions verify the license expression and include both license files.
- The publish workflow refuses a release whose tag does not match the Agent Skill,
  README, and installation-guide version pins.
  After publishing, it smoke-tests the pinned Skill invocation with `--help` and
  `--doctor` directly from PyPI.

Contributor workflow:

- Golden console-output tests now pin the CLI surface (help, every mode, and the
  usage-error matrix) under `tests/golden/`, run with tryscript
  (github.com/jlevy/tryscript) via `make test` and regenerated with
  `make golden-update`.
- Repository automation is updated to tbd 0.4.2. Its exact fallback stays usable under
  the dependency cool-off policy, and release documentation incorporates the verified
  GitHub CLI workflow for proxied agent sessions.

## 0.1.1

Hardening, offline support, and UI refinement:

- Offline-first assets: every third-party browser library is vendored into the wheel
  from lockfile-verified npm packages with a hash manifest, license texts, and size
  caps. The served page references no external origins, so Metabrowser works without
  network access; unused elkjs was dropped.
- Host-header validation defends against DNS rebinding.
  Loopback names and a concrete `--host` value are permitted automatically; wildcard
  binds keep validation and use loopback for the printed URL and auto-open, and
  `METABROWSER_ALLOWED_HOSTS` extends the allowlist (see SECURITY.md).
- First-paint navigation expands folders within a visible-row budget instead of
  expanding every top-level folder; document and tab spacing tightened, prose sized
  relative to navigation, compact TOC rows, and Markdown tables right-align signed
  percentages and localized number formats.
- Server responsiveness: live-tail polling, watcher classification, active-file sweeps,
  and synchronous plugin data hooks no longer block the event loop, and the mtime cache
  no longer serializes reads behind slow filesystem stats.
- Browser resilience: superseded file loads abort, client caches are bounded, the
  inventory event stream reconnects with backoff after repeated failures, live tree
  updates handle filenames containing backslashes and quotes, and the SDK owns
  copy-button behavior end to end.
- Documentation: project design records reorganized under a dedicated records tree with
  maintained architecture documents and dated plans, plus a research brief on the
  planned diff viewer architecture.
- Licensing: Metabrowser is licensed under AGPL-3.0-or-later, aligned with its required
  KPress runtime. Vendored browser components remain under their own licenses listed in
  `NOTICE.md`.

## 0.1.0

Initial standalone release:

- Local file, log, Markdown, structured-data, image, and binary browsing.
- Primary `metab` command with a `metabrowser` compatibility alias.
- Concise zero-install and global-tool onboarding, plus a portable Agent Skill that
  delegates to the pinned `uvx metabrowser@0.1.0` runner.
- Trusted manifest-driven plugins with JavaScript views and Python data hooks.
- KPress-backed Markdown rendering through `kpress==0.2.2`.
- Gzip- and zlib-transparent previews, frontmatter classification, Markdown rendering,
  and KPress export with bounded input, output, and text windows.
- Background inventory indexing, live filesystem updates, and recent-file navigation.
- SSH and optional GCP remote tunnels.
- AGPL-3.0-or-later licensing, PyPI packaging, locked uv environments, and isolated
  wheel checks.
- Review hardening for bounded compressed reads, safe rendered labels, byte-accurate
  event streaming, renderer disposal, explicitly repository-configured development
  commands, and release builds without mutable dependency caches.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
