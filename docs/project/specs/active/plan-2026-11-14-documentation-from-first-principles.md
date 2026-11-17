# Plan for Documentation from First Principles

**Date:** 2026-11-14

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Approved 2026-11-14, with the decisions below.
Implemented in one pull request, including the baseline benchmark results (recorded
2026-11-15).

## Overview

Metabrowser’s documentation grew one feature at a time.
The application now has three main tabs (Files, Pulls, and Commits), GitHub pull-request
review, commit history and diffs, live file watching over trees of hundreds of thousands
of files, a plugin SDK, and an optional native macOS app.
The README still introduces a plugin-based file browser and mentions most of these as
feature bullets or not at all.
Around it, guides have collected implementation internals, release-bound status, and
replacement history, and several documents serve three audiences at once.

This plan rebuilds the documentation from first principles around one thesis.
Every fact gets one owning document, every document gets one audience and one subject,
the architecture documents come level with the code at every layer, and `make verify`
gains the checks that keep this structure from drifting.

## Goals

- The README opens with the Metabrowser app icon, centered and large, above a centered
  title, and states the thesis on its first screen.
- From the README, a reader reaches a task guide for each thing Metabrowser does: browse
  files, watch them change, browse commits, review pull requests, work with agents, use
  the macOS app, script it from the command line, and extend it.
- Each fact has one owning document; every other mention is a link.
- Each document has one audience and one subject, and its length fits that subject.
- The architecture documents cover every layer of the application, say which parts are
  built and which are planned, and are reachable from one entry point.
- Every claim about speed or scale links to its measurement.
- Every human-authored document follows `tbd guidelines common-doc-guidelines`.
- `make verify` fails on a broken link, an unreachable document, or a tracker ID in a
  user guide.

## Non-Goals

- **Changing behavior:** where a document and the code disagree, the document follows
  the code. A code defect found on the way becomes its own bead.
- **Shipping planned features:** `metab --present`, a signed and notarized app, the fdu
  inventory engine, and browsing a million-file tree without the 500,000-file cap stay
  with their own plans.
  The documents describe them as planned and link those plans.
- **Documenting fdu:** the fdu engine will replace the Python walker as the inventory
  and rollup engine. The documents are structured for that architecture now (see
  Architecture Documents), but they do not describe using fdu until it ships.
- **Rewriting records:** CHANGELOG.md, research briefs, QA records, reviews, and
  experiment records keep their history.
  Only their status lines, locations, and index entries change.
- **Generated and vendored documents:** `docs/tbd/`, installed skills, and golden
  transcripts.

## Background

### The Thesis

> Metabrowser is a local, live browser for everything you and your coding agents work
> with: files, Markdown, logs, data, diffs, commits, and pull requests.
> It runs on your machine and opens in your own web browser or an optional native Mac
> app. Unlike most file browsers, it watches files as they change and stays responsive on
> trees of hundreds of thousands of files.
> Plugins extend it to new file types, today as views and in future as editors.

That is a working statement for the plan; the README pull request settles its wording.
Each pillar below ships today, with its evidence and the work it points toward.
The README states the shipped part and links the plan for the rest.

| Pillar | Ships today | Evidence | Planned |
| --- | --- | --- | --- |
| Agents show you content | The `metabrowser` agent skill. An agent can serve a path or a pull-request URL and hand you the page. `--api`, `--show`, and `--walk` give an agent the same data the UI draws. JSONL timelines for coding-agent logs. | `skills/metabrowser/SKILL.md`; `devtools/check_parity.py`; the `agent_log` built-in plugin | `metab --present`: one front door that shows content in the running app or browser ([native macOS app plan](plan-2026-11-10-native-macos-app.md), Phase 3) |
| Local, in your browser | A server bound to `127.0.0.1` that any browser opens; remote hosts over an SSH tunnel; cached repositories readable offline | `SECURITY.md`; `cli/remote.py` | None |
| A native Mac app for convenience | An alpha AppKit shell over `metab`, built from source: a window per folder, tabs, recent folders, and session restore | `apps/macos/` | A signed, notarized download |
| Any file type, through plugins | Manifest-based plugins with browser views and optional Python data hooks; every built-in view is a plugin | `docs/plugins.md`; `PLUGIN_SDK_VERSION` in `plugin_loader/manifest.py` | Editing ([trusted-local editing plan](plan-2026-07-16-trusted-local-file-editing.md)); more formats as plugins |
| Live and large | `watchfiles` watching streams tree and file changes to the page; indexing runs in the background, so the first view does not wait for a full crawl; serving stops at 500,000 files | `watch_backends.py`; `INVENTORY_MAX_FILES` in `settings.py`; the baseline benchmark (new, below) | The fdu inventory engine behind the existing provider contract ([provider plan](plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md), Phase 2); a million-file tree browsed, not cut off ([load-time plan](plan-2026-08-21-load-time-performance.md)) |
| Git and GitHub review | The Commits tab and `/commit/<rev>` pages; diffs of any range; the Pulls tab and pull-request pages with conversation, reviews, inline comments, checks, and stacks; offline reading from the cache | `docs/reviewing-pull-requests.md`; `git/routes.py`; the `github` built-in plugin | Working-tree status and diffs ([Git status plan](plan-2026-08-26-git-status-and-working-tree-diffs.md)) |

The goal includes trees of millions of files.
Serving is capped at 500,000 files today, and the fdu engine is expected to improve both
speed and reach. So the README says “hundreds of thousands of files” and links the
baseline benchmark for the figures; the benchmark reruns after the engine swap, and the
README’s wording changes only if the reach does.

### What the Survey Found

Three surveys read every document named below at `origin/main` c098e6a8 and checked
claims against the code; an independent review then checked the plan.
Line counts are from `wc -l` at that commit.

| Document | Lines | Main problems |
| --- | --- | --- |
| `README.md` | 407 | No thesis; Pulls, Commits, live watching, scale, and the app are buried or missing; duplicates five other docs; stale scale and commit-graph claims |
| `docs/command-line.md` | 1,025 | About 650 lines of Git-source and pull-request internals; five `--remote` options undocumented; inconsistent heading case |
| `docs/reviewing-pull-requests.md` | 540 | About half is preparation, cache, and styling internals |
| `docs/plugins.md` | 1,032 | A sound reference with Worker, staging, and console-tool internals mixed in |
| `docs/installation.md` | 268 | Describes app behavior that belongs in an app guide, and two release states at once |
| `SECURITY.md` | 308 | A 47-line policy followed by a 260-line content-trust threat model |
| `apps/macos/README.md` | 1,318 | Four documents in one: user notes, build and release, hand checks, and 723 lines of architecture |
| `docs/design-system.md` | 3,545 | Replacement history, measurement narratives, and the palette derivation mixed into the design rules; the user keyboard reference lives here, split across four sections |
| `docs/development.md` | 1,067 | Nineteen subjects, including browser architecture, experiment storage, and rationale that duplicates `AGENTS.md` |
| `docs/e2e-testing.md` | 643 | 220 lines of manual QA recipes and a performance playbook |
| `docs/qa-v012-repository-library.md` | 2,298 | A one-release runbook with stale status, in the durable docs folder |
| `docs/project/README.md` | 170 | Omits seven project documents; lists shipped plans as active |

Across the set:

- **Missing guides:** the Files tab (Overview, Treemap, Recent, and filters), the
  Commits tab, Quick Search for files, live logs, remote browsing, using the macOS app,
  agent workflows beyond pull requests, a user keyboard reference, and configuration and
  environment variables.
- **Duplicated facts:** trust flags, plugin discovery order, app requirements, skill
  installation, Git and `gh` requirements, failure-reason tables, and the
  beside-a-checkout cases each appear in two to four documents.
- **Stale claims:** the README’s “100,000 files or more” and “commit graph beside the
  file tree”; `TODO.md` saying 0.12.0 is untagged; tracker IDs described as under way
  that are closed; branches named that no longer exist.
- **A contradiction:** `CONTRIBUTING.md` asks for a migration plan before changing HTTP
  envelopes or SDK methods; `AGENTS.md` makes them internal contracts changed everywhere
  in one commit.
- **Old images:** the only screenshot, `images/metabrowser-overview.jpg`, dates from
  2026-07-17, before the Pulls and Commits tabs.
- **Project records:** seven shipped specs are still active, one is superseded, and four
  shipped designs never reached an architecture document.

### Checks That Exist

`tests/test_docs_discipline.py` checks that every architecture document under
`docs/project/architecture/` is linked from `docs/project/README.md`, states its status,
carries the footer, and names the check for any table of registered surfaces.
`devtools/public_hygiene.py` checks the footer on every Markdown file and rejects banned
tokens, including a list of dangling legacy document names.
Nothing checks that a link resolves, that a guide is reachable from the README, or that
a guide is free of tracker IDs.
An approximate scan by the reviewer found no broken relative links today, so the new
checks guard the moves this plan makes rather than repair existing damage.

## Design

### Rules

The common doc guidelines apply throughout.
Five rules beyond them answer what the survey found:

1. **Two indexes.** `README.md` reaches every user, contributor, and design document
   through its Documentation section, and `docs/project/README.md` reaches every project
   record and architecture document.
   Checked.
2. **Values live in code.** A constant, limit, default, timeout, enumerated list, or
   other value that code defines is documented in the code, in the docstring or comment
   beside it, with the measurement that set it where there is one.
   A document names the constant and the file that holds it, and describes what it
   means, but does not restate its value.
   The survey found such restatements drifting silently: the large-content limits table
   says 60,000 where the constant is 400,000, and the README’s file count trails the
   cap. A document may restate a value only when a test pins the copy to the code, as
   `tests/test_keymap.py` does for the keyboard table.
3. **Figures have one home each.** Benchmark figures live in `docs/scale-benchmark.md`,
   the Python engine’s unit costs in its engine document, and a bound’s measurement
   beside its constant, as `AGENTS.md` requires.
   The README and every other document state ranges and link; an adjective with no
   measurement behind it is cut.
4. **Built and planned are explicit.** Architecture documents keep their status lines.
   User documents describe what ships, and the README’s Direction section links the
   plans for the rest.
5. **No tracker IDs in user guides.** Bead IDs and branch names change state without the
   document changing; the survey found closed beads cited as under way.
   They belong in specs, records, `TODO.md`, and architecture status lines.
   Checked.

### Owners of Shared Facts

| Fact | Owner | Others link from |
| --- | --- | --- |
| Install, upgrade, and tool requirements (uv, Git, `gh`, the app, the skill) | `docs/installation.md` | README, `docs/reviewing-pull-requests.md`, `SKILL.md` |
| Release-bound status of the app and `metab` | `docs/installation.md` | README, `docs/macos-app.md` |
| Trust flags and environment variables | `docs/command-line.md` | README, `SECURITY.md`, `docs/plugins.md` |
| The content-trust model | `arch-server-and-content.md` (new) | `SECURITY.md`, `docs/command-line.md` |
| Plugin discovery order | `docs/plugins.md` | README, `SECURITY.md` |
| Failure reasons for a pull request and what to do | `docs/reviewing-pull-requests.md` | `docs/command-line.md` |
| Beside-a-checkout cases and mirror internals | `arch-mirror-acquisition-and-refresh.md` (new) | `docs/command-line.md`, `docs/reviewing-pull-requests.md` |
| Keyboard shortcuts for users | `docs/keyboard-shortcuts.md` (new) | README, `docs/design-system.md` |
| The baseline benchmark and its figures | `docs/scale-benchmark.md` (new) | README, architecture documents |
| Running a source checkout, tool versions, and the engineering benchmark method | `docs/development.md`, citing `package.json` and `.nvmrc` | README, `docs/installation.md`, `docs/engine-performance-model.md` |
| Parity rules and their rationale | `AGENTS.md` (rules) and `docs/development.md` (rationale) | `arch-parity-registry.md`, which holds only the checked tables |

### Stable Paths

Released code and installed skills link to documents by path on `main`, so these paths
and anchors keep working through every move:

- `README.md`, `docs/command-line.md` (the CLI’s help text), `docs/installation.md` (the
  app’s `ProjectLinks.swift`), `docs/reviewing-pull-requests.md`, and
  `docs/command-line.md#pull-requests` (the skill).
- `SECURITY.md` keeps a short trust-settings section, because CLI messages and the
  `cli-surface` golden say “see SECURITY.md” for `METABROWSER_ALLOWED_HOSTS` and `.env`
  rules. That section summarizes and links the trust model.

Check 1 below covers absolute `github.com/jlevy/metabrowser/blob/main/` links and
document paths named in `src/` and `apps/`, so a move that breaks one fails the build.

### Target Document Map

Size targets guide the rewrite; no check enforces them.
The targets were revised on 2026-11-16 to fit the documents as built, after the reviews’
cuts, where a document holds one subject and needs the room.
Five were raised again on 2026-11-16, when merging main brought in the rules stack #446
added: the design system’s Home, Titles, Navigation Reveals the Item, Tooltips Add
Information, Count Summaries Bold Their Numbers, Label Colors, Heading Tallies, Keys in
a Menu, and Brief Change Line; the SDK’s count-parts and change-line helpers in
`docs/plugins.md`; Keys in a Menu in `docs/keyboard-shortcuts.md`; Home, stack groups,
and the header’s Diff summary in `docs/reviewing-pull-requests.md`; and the comparison
keep and label sets in `arch-github-pull-requests.md`. The design system’s measurements
that came with them moved to
`explorations/performance-loop/design-rule-measurements.md`. A guide that needs more
than its target is a sign that it covers two subjects.

| Document | Audience | Target lines | Subject |
| --- | --- | --- | --- |
| `README.md` | Everyone | 200 | The thesis, the icon, quick start, and the map |
| `docs/installation.md` | Users | 250 | Install and upgrade `metab`, the app, and the skill; tool requirements; release-bound status |
| `docs/browsing-files.md` (new) | Users | 250 | The Files tab: tree, Overview, Treemap, Recent, and filters; reading Markdown, data, code, logs, images, and HTML; live updates and log tailing; Quick Search for files; remote hosts |
| `docs/browsing-history.md` (new) | Users | 150 | The Commits tab, commit pages, diffs of any range, and `--diff` |
| `docs/reviewing-pull-requests.md` | Users | 350 | The Pulls tab and pull-request pages |
| `docs/working-with-agents.md` (new) | Users | 150 | The skill; an agent showing you a page; agent-log timelines; `--api` and `--show` for agents |
| `docs/macos-app.md` (new) | Users | 200 | Using the app: windows, tabs, recents, restore, drops, settings, and choosing a `metab` |
| `docs/keyboard-shortcuts.md` (new) | Users | 120 | The shortcut reference, pinned to the keymap registry by `tests/test_keymap.py` |
| `docs/command-line.md` | Users and scripts | 600 | Every mode, every option, configuration, and environment variables |
| `docs/scale-benchmark.md` (new) | Everyone | 100 | What the baseline benchmark measures, how to run it, and its results |
| `docs/plugins.md` | Plugin authors | 1,000 | Manifest, SDK, data hooks, packaging, and the security boundary |
| `skills/metabrowser/SKILL.md` | Agents | 200 | Adds commits, `--diff`, live logs, and handing the user any page |
| `SECURITY.md` | Everyone | 100 | Reporting, the served-root boundary, and trust settings, linking the trust model |
| `CONTRIBUTING.md` | Contributors | 100 | Matches `AGENTS.md` on internal contracts |
| `TODO.md` | Everyone | 250 | Current release state; no replacement history |
| `docs/development.md` | Contributors | 650 | Setup, commands, the gate, conventions, docs, tbd, pull requests, troubleshooting |
| `docs/e2e-testing.md` | Contributors | 420 | Test layers, tiers, skips, and measuring the suite |
| `docs/design-system.md` | Designers and implementers | 4,950 | Tokens, color, type, components, and interaction design, with one keyboard section |
| `docs/publishing.md` | Maintainers | 190 | Unchanged |
| `apps/macos/README.md` | App developers | 450 | Build, test, and release the app |
| Architecture documents | Architecture readers | See below | One per layer |

### The README

The README is the front door for every audience, so it carries the thesis and a map and
leaves every detail to the guide that owns it.

**Title block:** the release app icon, the citrine M and amethyst B that the macOS task
switcher shows, centered above a centered title.

```html
<p align="center">
  <img src="images/metabrowser-icon.png" alt="Metabrowser app icon" width="192">
</p>

<h1 align="center">Metabrowser</h1>
```

- **Source:** `apps/macos/AppIcon/metabrowser-icon.svg`, the release master that
  `Resources/AppIcon.icns` is built from.
  Not the development master, whose gold rim marks canary builds.
- **Rendering:** `apps/macos/scripts/build-icon.sh` also writes
  `images/metabrowser-icon.png` at 512 pixels with `AppIcon/render-svg.swift`, the
  renderer that builds the `.icns`, so the README image and the app icon change
  together. Shown at 192 pixels, it stays sharp on high-density screens.
  `AppIcon/README.md` adds the file to its table.
- **Relative paths:** GitHub and Metabrowser itself both render an in-tree image.
  In a served folder, KPress keeps the presentational `align` on `p` and `h1`, so
  Metabrowser shows the block centered, as GitHub does, and reports nothing: measured
  2026-11-16 with KPress 0.3.6, `/api/kpress/render` on this README answers the two
  `align="center"` tags and empty `diagnostics` and `sanitizer_diagnostics`, so the page
  has no Diagnostics disclosure.
  With active content off, on a served mirror or a folder served with `--untrusted`,
  Metabrowser’s inert Markdown keeps only in-tree images and keeps `align` only on table
  cells, so it shows the icon left-aligned and without its `width`, still with no
  diagnostics. One more cost is accepted for the centered block on GitHub: the
  rendered-Markdown diff refuses raw HTML, so a README change has no rendered diff
  (measured the same day, a one-word README change projects as `unsupported`, and the
  same change under a Markdown title as `ready`). The inert profile’s `align` and the
  projection are tracked as mb-4cwy. PyPI, which publishes the README as the package
  description, shows the alt text instead, as it does for today’s screenshot (see
  Decisions).

**Outline:**

1. Title block
2. The thesis in three sentences
3. A refreshed screenshot of the Files tab with rendered Markdown
4. Why: the author’s motivation, kept in the first person and cut to one paragraph
5. Quick Start: `uvx metabrowser@latest .`, `uv tool install metabrowser`, and opening a
   folder, a file, a repository URL, or a pull-request URL
6. What You Can Do: one or two sentences each, linking its guide
   - Read any file
   - Watch files and logs live
   - Browse commits and diffs
   - Review pull requests
   - Find anything with Quick Search and single-key shortcuts
   - Work with coding agents
   - Browse a remote machine
   - Script it with `--api`, `--show`, `--walk`, and `--diff`
7. The Mac App: what it adds, its status, and a link
8. Scale: hundreds of thousands of files, linking `docs/scale-benchmark.md`
9. Extend It: plugins in two sentences and a link
10. Security: the local-trust warning in three lines and a link
11. Direction: the planned pillars from the thesis table, each linking its plan; the
    planned engine is named as a faster native inventory engine, without usage details
12. Documentation: the index of every guide by audience
13. Contributing and License

Removed from the README to their owners: trust flags, the plugin discovery order, the
developer tool versions, the File Rollup Format, link and transclusion semantics, and
the shortcut scheme.

The README links every guide by its planned name, so it is written alongside them.

### The Baseline Benchmark

The only speed measurements today are the performance loop’s experiment records, which
answer engineering questions on a 5 GB copied corpus.
A reader needs a few figures anyone can reproduce, and the fdu swap needs a before
figure.

- **Command:** `make benchmark` runs `devtools/bench_serving.py` on its deterministic
  synthetic corpus at 100,000 and 300,000 files with the default Python provider, one
  run each, and prints a Markdown table.
- **Metrics,** all of which the harness reports today:
  - time from start to the first folder counts
  - wall time of the scan with a client attached
  - peak server memory
- **Record:** `docs/scale-benchmark.md` holds the table with the date, `metab` version,
  provider, and machine, and says how long a run takes.
- **After the swap:** once the fdu provider is registered (`INVENTORY_PROVIDERS` lists
  only `python` today), the same command runs with `--provider fdu` and its results go
  beside the Python baseline.
- **Not a gate:** the performance loop stays the release gate.

The time for a file change to reach an open page would be the natural evidence for live
watching, but the harness sees a change only as an ETag advance.
Measuring it is new harness work, left for a follow-up bead.

### User Guides

Each new guide starts from material that exists and is checked against the code at the
pull request’s head:

- **`docs/browsing-files.md`:** the README’s Files features, the user parts of
  `docs/realtime-debugging.md` (which that pull request removes there), and the file
  half of Quick Search.
- **`docs/browsing-history.md`:** the README’s Git bullet, `docs/command-line.md`’s
  `--diff` section, and the Commits sections of the design system.
- **`docs/working-with-agents.md`:** the README’s agent section, `SKILL.md`, and the
  agent-log plugin. Sandbox settings wait for `metab --present`.
- **`docs/macos-app.md`:** the user sections of `apps/macos/README.md` and
  `docs/installation.md`’s section on what the app shows without a usable `metab`, both
  removed at their sources in the same pull request.
- **`docs/keyboard-shortcuts.md`:** the user table from the design system, with the
  `tests/test_keymap.py` pin moving to the new file.

Internals leave the user guides for the layer documents that own them:

- `docs/command-line.md`: mirror refresh and pin routes, clone progress, mirror page
  naming, the beside-a-checkout table, and application-home repair go to the mirror and
  cache documents; `--exit-on-eof` process handling goes to `arch-cli.md`.
- `docs/reviewing-pull-requests.md`: background preparation and cache refusals go to
  `arch-github-pull-requests.md`; visual styling is cut where the design system’s
  pull-request page section already says it.
- `docs/plugins.md`: retained-navigation staging, the Markdown Worker lifecycle, and the
  diagnostic console tools go to `arch-browser-shell.md`.

### Architecture Documents

A technical review read the architecture documents against the code: about 10,300 lines
across `docs/architecture.md`, `docs/project/architecture/`, and four standards in
`docs/`. It found:

- **Layers with no document:** the CLI (22 modules), the plugin system, the browser
  shell, and the native macOS shell, which `docs/architecture.md` never mentions.
  The GitHub provider has none of its own; its contracts are split between two documents
  and `docs/command-line.md`.
- **Two entry points:** `docs/architecture.md` calls itself the architecture, while
  `docs/development.md` and the project index call `arch-views-models-routes.md` the
  map. Neither maps the layers, and there is no reading order.
- **Documents of many subjects:** `arch-repository-sources-and-provider-mirrors.md` is
  1,768 lines on nine subjects and `arch-state-and-delivery.md` is 810 lines on twelve.
- **Engine detail above the engine:** the Python engine’s interpreter lock, worker
  threads, and retained store appear in the state-and-delivery, provider-contract, and
  engine-performance documents, so swapping the engine today would touch all three.
- **No thesis and no extension path:** no architecture document states the product’s
  aims, and nothing explains, in one place, how to add a file type.
- **Wrong claims:** about a dozen, from a module that does not exist to a limit stated
  as 60,000 whose constant is 400,000. Each goes into the description of the bead that
  owns its document.

**Target structure:** about 4,700 lines at first, and about 5,450 as built.
All architecture documents live in `docs/project/architecture/` except the entry point
and the four standards, which stay in `docs/`.

| Document | Subject | Target lines | From |
| --- | --- | --- | --- |
| `docs/architecture.md` | The thesis, the layers with their module paths, a reading order, and a link to every architecture document | 250 | Itself, less folder composition, URL and Markdown detail, and filtering |
| `arch-cli.md` | Modes, the serve lifecycle, in-process `--api` dispatch, remote tunnels, and process exit | 250 | New; `docs/command-line.md` |
| `arch-server-and-content.md` | Request flow, safe paths, validators, and the content-trust model | 400 | `docs/architecture.md`, `arch-state-and-delivery.md`, `SECURITY.md` |
| `arch-views-models-routes.md` | Kinds, views, formats, and the route index | 250 | Its first 176 lines; route contracts go to their layer documents |
| `arch-parity-registry.md` | The two tables `devtools/check_parity.py` reads, and nothing else | Tables | `arch-views-models-routes.md` |
| `arch-inventory-provider.md` | The engine-independent contract: queries, lifecycle, the cap, and change feeds | 500 | Itself, `docs/engine-performance-model.md` |
| `arch-inventory-engine-python.md` | The only engine-specific document: walker, concurrency, watcher backend, and unit costs | 300 | `arch-python-inventory-cost.md`, `arch-state-and-delivery.md`, `arch-inventory-provider.md` |
| `arch-live-delivery.md` | From the provider’s change feed to the browser’s stores: events, recovery, and invariants | 300 | `arch-state-and-delivery.md`, `docs/architecture.md` |
| `arch-git.md` | The process boundary, history sessions, graph checkpoints, and commit detail | 400 | `arch-git-and-comparison-sources.md` |
| `arch-source-sessions-and-pins.md` | Subjects, capabilities, path projection, and the pin guard | 250 | The repository and Git documents |
| `arch-diff-pipeline.md` | Sources, hydration, caches, and Markdown projection | 300 | `file-diff-format/`, the Git document, `docs/large-content-rendering.md` |
| `arch-repository-cache.md` | Layout, identity, record contracts, locks, and sweep | 350 | The repository document |
| `arch-mirror-acquisition-and-refresh.md` | Transports, credentials, the lending checkout, and refresh cadence | 450 | The repository document |
| `arch-github-pull-requests.md` | Records, the catalog, files, checks, stacks, and routes | 550 | The repository document, `arch-views-models-routes.md` |
| `arch-plugin-system.md` | Manifests, discovery, classification, the SDK gate, containers, and how to add a file type | 300 | New; `arch-nav-containers.md` |
| `arch-browser-shell.md` | Shell modules, stores, lifecycle, and asset loading tiers | 350 | New; `docs/development.md`, `docs/plugins.md` |
| `arch-macos-app.md` | Server supervision, windows and tabs, restore, and WebKit differences | 350 | `apps/macos/README.md`, `docs/large-content-rendering.md` |
| `file-diff-format/`, `file-rollup-format/` | Format specifications | As now | The rollup palette moves to the design system |
| `docs/large-content-rendering.md`, `docs/web-performance-framework.md`, `docs/realtime-debugging.md`, `docs/engine-performance-model.md` | Contributor standards | 250, 200, 120, 80 | Benchmark method moves to `docs/development.md`; the WebKit gate log to the app document; the limits table names its constants without restating their values |

Retired:

- `arch-hosted-review-model.md` and `arch-external-resources-and-views.md` (1,481 lines)
  describe nothing in the code; the rest of what they say is in other documents or on
  the `reference/v012-hosted-review-2026-09-30` tag.
- `arch-python-inventory-cost.md` merges into the Python engine document.
- `arch-editor-plugin-editing-contract.md` becomes a draft plan in `specs/active/`.
- `arch-vscode-extension-host.md` moves to `research/archive/`.
- Each retired name joins the dangling-document-name pattern in
  `devtools/public_hygiene.py`, and comments in `src/` that name it (the repository
  document in three files, `arch-nav-containers.md` in five) point at its successor.

**Structured for the engine swap:** the provider contract and every document above it
state only what the provider guarantees.
The walker, its threads, the watcher backend, and unit costs live only in
`arch-inventory-engine-python.md`. When the fdu provider ships, its pull request adds an
engine document beside the Python one, reruns `make benchmark`, and updates the provider
contract’s status line and `docs/development.md`’s provider section.
Nothing else changes.

### Design and Development Documents

- **`docs/design-system.md`** stays one document.
  Its visual and interaction rules share an audience and a cadence, and splitting it
  would change references in 96 tracked files, 27 of them tests
  (`git ls-files | xargs grep -l design-system.md`). Instead it loses its replacement
  history, its measurement narratives (to `explorations/`, with one-line links), and its
  palette derivation (to `color_oklch.py` docstrings); the user keyboard table moves to
  `docs/keyboard-shortcuts.md`; and its four keyboard sections become one.
- **`docs/development.md`:** asset loading tiers move to `arch-browser-shell.md`,
  durable storage and experiment-record rules to
  `explorations/performance-loop/README.md`, inventory-provider development to
  `arch-inventory-provider.md`, and rollup format maintenance to the format’s directory.
  It gains the engineering benchmark method from `docs/engine-performance-model.md` and
  the parity rationale from `arch-views-models-routes.md`, merged with its own.
  Text that restates `AGENTS.md` becomes a link.
- **`docs/e2e-testing.md`:** the manual browser recipes move to a QA checklist under
  `docs/project/qa/`, and the navigation performance playbook to
  `explorations/performance-loop/`.
- **`apps/macos/README.md`:** user material moves to `docs/macos-app.md` and
  architecture to `arch-macos-app.md`, with measurement tables beside `TabDiscardPolicy`
  and `RestoreBudget`; build, test, and release instructions stay.

### Project Records

- Move shipped specs to `specs/done/`, after folding any design that no architecture
  document holds into its layer document.
  The survey lists seven shipped, one superseded, and four whose designs need folding.
- Move `docs/qa-v012-repository-library.md` to `docs/project/qa/` under a dated name and
  update its inbound links in eleven files.
- Archive superseded research briefs under `research/archive/`.
- Make `docs/project/README.md` list every record with a current description.
- Refresh the status lines of live specs, including the native app plan, whose spike
  branch and drafted workflow have both since landed.

### New Checks

All four go into `tests/test_docs_discipline.py`, so `make verify` runs them, and each
is proven by a failing fixture, as `tests/test_experiment_storage.py` does.

1. **Links resolve.** Every relative link in a human-authored Markdown file, every
   `github.com/jlevy/metabrowser/blob/main/` link, and every document path named in
   `src/` and `apps/` names a file that exists, and a heading anchor that exists in it.
   Anchors come from `heading_slug` in `inert_html.py`, after stripping inline Markdown
   from the heading and numbering repeats as GitHub does.
   Generated trees (`docs/tbd/`, `tests/golden/`, `.tbd/`) are exempt.
2. **Every document is reachable.** Following relative links from `README.md` reaches
   every Markdown file under `docs/` outside `docs/project/` and `docs/tbd/`; following
   them from `docs/project/README.md` reaches every file under `docs/project/`.
3. **No tracker IDs in user guides.** `README.md`, the user guides in the map above,
   `SKILL.md`, and `apps/macos/README.md` contain no bead ID, matched as a whole token
   so that identifiers such as `data-mb-copy` do not count.
4. **Architecture discipline everywhere.** The status, footer, and named-check rules
   that cover `docs/project/architecture/` also cover `docs/architecture.md` and the
   four standards in `docs/`, which are outside them today.
   That gap is how `docs/large-content-rendering.md` drifted.

All four checks run on the finished pull request.

### Review of Each Pull Request

- `make verify`.
- An independent technical review that checks every changed claim, path, constant,
  route, and option against the code at the pull request’s head.
- A prose review with `pprose-review` against the common doc guidelines.
- For the README, the author reviews the thesis and the Why section, which speak in
  their voice.

## Implementation Plan

All of it lands as one standalone pull request, so a reviewer sees the whole
documentation set change at once and every check runs on the finished result.
The items below are its beads, grouped in the order a reader meets the documents; the
two groups keep their phase names.

- **Parallel work:** beads are drafted in parallel worktrees, each on a branch from the
  same base, and merged into the pull request’s branch.
- **Ownership:** each existing file has one owning bead.
  When material moves, the bead that creates the destination copies it from the base,
  and the owner of the source deletes it and leaves a link.
- **Shared files:** `README.md` belongs to the README bead and `docs/project/README.md`
  to the records bead, which add the entries for every new document by its planned name.
  A link to a moved heading in a file another bead owns is fixed after the merge, where
  the link check finds it.

### Phase 1: The Reader’s Path

- [x] Add checks 1 to 3 with their failing fixtures, and fix what they find; add the
  values-live-in-code rule (Rules, item 2) to the documentation conventions in
  `docs/development.md` and to the Documentation section of `AGENTS.md`, with its
  reason, so every later rewrite follows it.
- [x] Rewrite `README.md` with the icon block, the thesis, a refreshed screenshot, and
  the outline above, linking the documents that exist; extend
  `apps/macos/scripts/build-icon.sh` to write the README image.
- [x] Rewrite `docs/installation.md` as the owner of requirements and release-bound
  status; write `docs/macos-app.md` and remove its material from `apps/macos/README.md`.
- [x] Write `docs/browsing-files.md` and `docs/keyboard-shortcuts.md`, moving the user
  keyboard table and its pin out of the design system and the user parts out of
  `docs/realtime-debugging.md`; correct the tab order in `static/main-tabs.js`’s header
  comment.
- [x] Write `docs/browsing-history.md`; cut `docs/command-line.md` and
  `docs/reviewing-pull-requests.md` to their subjects, linking internals the repository
  document already holds and moving the rest into it; document the five missing
  `--remote` options and the configuration file and environment variables.
- [x] Write `docs/working-with-agents.md` and update `SKILL.md`, keeping the anchors
  installed skills link to.
- [x] Cut `SECURITY.md` to its policy and trust-settings section, moving the trust model
  into a new `arch-server-and-content.md`; make `CONTRIBUTING.md` agree with
  `AGENTS.md`; bring `TODO.md` to the current release.
- [x] Add `make benchmark` and `docs/scale-benchmark.md` with the Python-provider
  baseline, and link it from the README’s Scale section.

### Phase 2: The Builder’s Path

- [x] CLI, server, inventory, and delivery: write `arch-cli.md`,
  `arch-inventory-engine-python.md`, and `arch-live-delivery.md`; make
  `arch-inventory-provider.md` engine-independent; complete
  `arch-server-and-content.md`; retire `arch-state-and-delivery.md` and
  `arch-python-inventory-cost.md`; trim `docs/realtime-debugging.md`.
- [x] Git and diffs: write `arch-git.md`, `arch-source-sessions-and-pins.md`, and
  `arch-diff-pipeline.md`, folding in the general diff rendering plan’s design; retire
  the Git document, moving the paths `tests/test_git_arch_doc.py` reads.
- [x] Repository and GitHub: write `arch-repository-cache.md`,
  `arch-mirror-acquisition-and-refresh.md`, and `arch-github-pull-requests.md`, folding
  in the Pulls tab and pull-request review plans’ designs; retire the repository
  document, moving the paths `devtools/check_artifact_contracts.py` reads.
- [x] Plugins and the browser: write `arch-plugin-system.md`, with how to add a file
  type, and `arch-browser-shell.md`, folding in the Quick Search plan’s design; trim
  `docs/plugins.md` and `docs/web-performance-framework.md`; retire
  `arch-nav-containers.md`.
- [x] The app: write `arch-macos-app.md`; cut `apps/macos/README.md` to build, test, and
  release; refresh the native app plan’s status.
- [x] Contributor documents: cut `docs/design-system.md` as described above; revise
  `docs/development.md` and `docs/e2e-testing.md`; trim
  `docs/engine-performance-model.md`, moving its benchmark method into
  `docs/development.md`; move the rollup palette out of `file-rollup-format/` and its
  maintenance notes in.
- [x] The map and the entry point: split `arch-views-models-routes.md` into the map and
  `arch-parity-registry.md`, moving the paths `devtools/check_parity.py` and three tests
  read; rewrite `docs/architecture.md` as the entry point; cut and correct
  `docs/large-content-rendering.md`.
- [x] Records: retire the four documents listed above; move shipped specs, the v0.12
  runbook, and superseded research; correct `docs/project/README.md`; add check 4.

## Testing Strategy

- Each new check fails on its fixture before it passes on the tree.
- Tests that read document text (`tests/test_design_vocabulary.py`,
  `tests/test_keymap.py`, `tests/test_git_arch_doc.py`, and others) move their paths in
  the same pull request as the text.
- Each command shown in a user guide runs against the pull request’s head, and its
  output matches what the guide says.
- The README is checked as GitHub renders it in the pull request and as `metab .`
  renders it on the branch.

## Rollout Plan

One pull request against `main`, reviewed as a whole.
When the fdu provider ships, its pull request takes the engine-swap steps under
Architecture Documents.

## Decisions

1. **Benchmark sizes:** two sizes, 100,000 and 300,000 files, one run each, stay under
   the serving cap. A million-file row needs the cap lifted, so it arrives with the fdu
   engine. Decided: these two sizes now.
2. **Screenshots:** one refreshed hero image of the Files tab, plus one image each in
   the pull-request, history, and app guides, taken of this repository.
   Decided: yes, with no personal paths visible.
3. **Images on PyPI:** relative paths render on GitHub and in Metabrowser but show alt
   text on PyPI; absolute `raw.githubusercontent.com` URLs render on PyPI but not in
   Metabrowser’s inert view, and not in the pull request before merge.
   Decided: relative paths.
4. **Retiring by deletion:** the hosted-review and external-resources architecture
   documents describe nothing in the code.
   Decided: delete them, since Git and the reference tag keep them, rather than add an
   architecture archive.

## References

- [Common documentation guidelines](https://github.com/jlevy/practical-prose), applied
  with `tbd guidelines common-doc-guidelines`
- [Development: Architecture Documents](../../../development.md#architecture-documents)
- [Native macOS app plan](plan-2026-11-10-native-macos-app.md)
- [Inventory provider refactor and fdu adoption](plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md)
- [End-to-end load time plan](plan-2026-08-21-load-time-performance.md)
- [App icon](../../../../apps/macos/AppIcon/README.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
