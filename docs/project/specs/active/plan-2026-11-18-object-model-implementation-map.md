# Plan: Implementation Map for Objects, Views, and View State

**Date:** 2026-11-18

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Decided, and nothing here is built.
It maps [Object Data Model and Views](plan-2026-11-14-object-data-model-and-views.md),
the parent plan below, and its companions
[View Model and View State](plan-2026-11-18-view-model-and-view-state.md) and
[The Recent Tab](plan-2026-11-18-recent-tab-updates-and-events.md), onto stacks of pull
requests. The owner decided the order, Ordering 2, on 2026-11-18: safe groundwork first,
a checkout’s uncommitted changes as the first object type, then the larger surfaces.
The decisions it rests on were taken the same day, and
[Decisions This Map Follows](#decisions-this-map-follows) lists them.
What can still change it is marked **(if …)** at each place.

## Decisions This Map Follows

Numbered decisions are the parent plan’s, and VM decisions the view model plan’s.

| Standing, as of 2026-11-18 | Decisions |
| --- | --- |
| Taken by the owner on 2026-11-18 | 1 and VM-8: SoftSchema contracts for objects and UI state. 2 A, 3 A, 4 A, 6 A, 7 A, 9 A, 10 A, 13 to 18 A, 21 A, and 23 A. 5: `pull-request` everywhere, with `--present`’s kind and `SelectionKind` renamed with the macOS app in one commit, `repository` and `tree` to `folder`, `blob` to `file`, and a separate field that keeps a repository’s root apart from a named tree. 8: UTC strings at second precision. 11 A: a closed set of shapes, with the `card` frame built at its first real use, which is C5. 12: the host frame, with the header through an SDK frame that mb-7t5s builds. 19 C: a main tab named Recent, designed in the Recent tab plan, with option B’s address kept as `/recent`. 20: no SDK bump for an addition, and #380’s versioning rule if #380 is accepted. 22 D: the contract half after several types exist. VM-1 A, VM-2 B, VM-3 C, VM-5 A (VM-4 is folded into it), VM-6 B, VM-7 A, VM-9 A, and VM-10 A, with the view slice first or beside the object slice. The Recent tab plan’s RT-1 to RT-7, the plugin authoring plan’s PS-1 to PS-7, and the agent interface plan’s AI-1 to AI-6. [Ordering 2](#orderings) |
| Open | The agent interface plan’s [AI-7](plan-2026-11-18-agent-interface.md#decision-ai-7-finding-a-server-the-agent-did-not-start): whether the discovery half of the live-server registry, mb-5xi4, comes ahead of host mode |

- **(if #380 is accepted)** C3 is a patch bump with an `sdk-changes.toml` entry.
- **(if mb-r5gn finds a path the `/view/` codec cannot spell)** T1.5 keeps the git
  plan’s `/status/<scope>/<entry-id>` address, as the Recent tab plan’s RT-3 allows.
- **(if AI-7 is taken as A)** a pull request for the state file, the listing, and the
  liveness probe joins Stack V after V5, and `--live` no longer waits for mb-qzny.

## The Working Tree Today

Paths are under `src/metabrowser/` unless they start with `docs/`, `tests/`,
`devtools/`, `explorations/`, `apps/`, or `skills/`; `github/` abbreviates
`builtin_plugins/github/`. What exists:

- **The format.** File Diff Format reserves `index` and `worktree` snapshot kinds
  (`diff/format.py:69-77`), so a working-tree comparison needs no format change.
- **A revision source.** `GitDiffSource` (`diff/adapters/git.py:589`) compares two
  revisions at a folder or a store pin, with no index or working-tree side.
- **The drawing.** The diff plugin’s `comparison` hook serves revision comparisons, and
  `diff-view.js`, its strict normalizer `diff-model.js`, and the Diff summary
  (`diff-summary.js`, over the shell’s `changed-files-tree` bundle) draw any File Diff
  Format document.
- **The CLI.** `metab --diff SPEC` (`cli/diff_cli.py`) takes `BASE..TARGET`, a revision,
  or a patch file.
- **A design, unstarted.**
  [Git Status and Working-Tree Diffs](plan-2026-08-26-git-status-and-working-tree-diffs.md)
  specifies `git/status.py`, `GET /api/git/status`, `GitWorkingTreeDiffSource`, a
  one-entry `working-tree` hook, `/status/<scope>/<entry-id>`, and a Changes section
  above History. It now also records two
  [requirements from the Recent tab plan](plan-2026-08-26-git-status-and-working-tree-diffs.md#requirements-from-the-recent-tab-plan):
  a manifest of every path, and the `/status` and `/status/<path>` address.
  Its beads are open under the P1 epic mb-097x: mb-r5gn (Phase 0, now unblocked),
  mb-u4mf, mb-vibn, mb-y06t.
- **A chooser row.** Since #559 a checkout’s ref chooser offers “Working tree” as the
  served revision (`source_routes.py:261`); it shows files, not changes.

What the object adds to that design, as the Recent tab plan’s
[Working-Tree Changes](plan-2026-11-18-recent-tab-updates-and-events.md#working-tree-changes)
defines it: a type, `working-tree-changes`, and one identity for each served root, the
`id` `working-tree`; a summary carrying the shared change-totals sub-object; its entries
as `changed-file` references naming it as their parent; one manifest of every entry,
hydrated per file, for a whole-tree page; and an `href` and `parse`, so `--show`,
`--present`, and a view state name it.

## Orderings

| Ordering | Risk | First value a reader sees | Rework |
| --- | --- | --- | --- |
| **1. Working-tree diff first.** T1 starts now and defines what it needs locally | High: T1.2 is the largest, least measured backend, and mb-r5gn may end in a design review | The page after five PRs on one path, T1.1 to T1.5 | One M PR moving T1.3’s local definitions onto T0.2’s |
| **2. Groundwork, then the working tree.** T0.1 to T0.7 and T1.1 start together; T1.2 follows T1.1, and T1.3 waits for T0.3; V and P run beside T1 | Low: small golden-pinned PRs. Groundwork could grow into a campaign, so it is capped at the eight listed | T0.8’s headers after one PR; the working-tree page after the same five, at most one later, since T0.1 to T0.3 run while mb-r5gn measures | Least |
| **3. The parent plan’s order.** V and P first, then T1 | Medium: P changes the Pulls controller, the most tuned surface, before a smaller type proves the store | Agents’ `present` after V4; `/pulls` after P6; the working tree last | Low; the working tree waits longest |

**Decided 2026-11-18: Ordering 2.** The working tree’s gate needs no code and starts on
the first day, so groundwork costs it at most one pull request, and every later stack
reads one set of shared definitions.
The rest of this map follows it.

## Stacks

Each stack is a GitHub stack of its table’s pull requests, in order; Tier 0’s pull
requests land singly.

### Tier 0: Safe Groundwork

Names and shared definitions, with no behavior change except T0.8’s requested header.

| PR | Changes | Proves | Size |
| --- | --- | --- | --- |
| T0.1 `refactor(cli): name targets folder, file, commit, and pull-request in --present, selections, and the app` | `cli/present.py`; `SelectionKind` (`cache/urls.py:77`), with a field keeping “no ref named” apart from a named tree, as `cli/selection.py:262` and `cache/resolve.py:754` need; in `apps/macos/`, `PresentPlan.swift` and `minimumRelease` (`MetabVersion.swift:56`); `skills/metabrowser/SKILL.md`; `docs/command-line.md`; CHANGELOG | Present and selection goldens change only in tokens; `PresentPlanTests` | M |
| T0.2 `feat(objects): one definition each for a reference, a collection reference, an actor, change totals, and a time` | New `objects/`, Pydantic models not yet registered: `Reference{type, id, parent?}`, the collection reference `{name, params, parent?}`, shape names, `Actor`, `ChangeTotals` with nullable counts, `statuses`, and `short`, the UTC-second time; projections from `ChangeSums`, `FilesSummaryWire`, `GitCommitStats`, and diff `Totals`; `static/types.d.ts`. No wire change | Every producer projects losslessly; importing `objects` loads no schema library | M |
| T0.3 `feat(cli): --show names the object an address selects` | `href` and `parse` per type with a page, over `view_routes.py` and `cli/selection_href.py:16`; an `object:` line | `cli-show.tryscript.md`; Python and JavaScript codecs agree over `navigation.route-identity` | S |
| T0.4 `refactor(github): derive a pull request’s four states once` | One helper for `github/pull_catalog.py:640`, `github/pulls.py:1239`, `cli/show_cli.py:248`; one table `displayState` is tested against | Goldens unchanged | S |
| T0.5 `refactor(git): the log answers rows and next_after, as other collections do` | `git/wire.py:207-208`; `cursor` to `after`; `static/git-panel.js`; the golden normalizer’s cursor paths (`normalize.py:39`), which must still mask the log’s session token and leave a pull list’s `next_after`; a test of Decision 3’s keys across list routes. Times stay epoch seconds until C1 | Goldens differ only in key names | M |
| T0.6 `refactor(github): the change-line lane lives with the pulls controller` | `createRowLines` moves from the panel’s mount (`github/pulls-panel.js:5028`) into `createPullsController`, still wanting nothing while hidden (`:4541-4547`) | `github.pulls-row-lines` byte for byte; Pulls-tab pairs | S |
| T0.7 `refactor(devtools): check each contract registry against its own document` | `devtools/check_artifact_contracts.py` from one pair (`:10`, `:19`) to a list | Fails on drift in either position | S |
| T0.8 mb-7t5s `feat(shell): pull requests and commits on the view header, through an SDK frame` | A frame in #550’s on-demand `view-header` bundle; the pull request and commit pages onto it; the bead’s notes A2, A6, A11 | `test_git_commit_summary_is_one_component`; header pairs; the bead’s Chrome rhythm measurement | L |

### Tier 1: The Working Tree as the First Object

| PR | Changes | Proves | Size |
| --- | --- | --- | --- |
| T1.1 mb-r5gn `bench(git): a dirty-tree corpus and the status measurement gate` | Corpus, benchmark, record with committed protocol; the git plan’s three open decisions | The constants T1.2 and T1.4 use | M |
| T1.2 mb-u4mf, mb-y06t `feat(git): read the working tree’s status as GET /api/git/status` | `git/status.py`, the Git 2.36 gate, generations, `git/wire.py` types | `--api` goldens of every dirty state; the index untouched | L |
| T1.3 `feat(objects): a checkout’s uncommitted changes as an object` | The type `working-tree-changes`, with the one `id` `working-tree` for a served root, to the Recent tab plan’s definition: summary `head`, `generation`, `clean`, `truncated`, and `counts`; the `changes` facet; `updated_at`; entries as `changed-file` references naming it as `parent`; its object route; added to T0.3’s table; absent on a pin, a mirror, a plain folder | Projection over every T1.2 golden | M |
| T1.4 mb-u4mf `feat(diff): the working tree in File Diff Format, whole and per entry` | `diff/adapters/working_tree.py`; one manifest hydrated per file; the `working-tree` hook; `metab --diff` accepts the working tree | Schema and apply oracle; `--diff` goldens; T1.1’s constants | L |
| T1.5 `feat(git): a page for the working tree’s changes` | Its address, `/status` and `/status/<path>` under the Recent tab plan’s RT-3 A, in the URL grammar and the map; the page under T0.8’s frame, drawn by the diff plugin’s multi-file view and Diff summary | Browserless mount session; first paint against a commit page of the same change set | L |
| T1.6 mb-vibn `feat(git): Changes above History in the Commits tab, kept live` | The git plan’s Phase 2, with groups drawn by the shared `changed-files-tree` (**if the owner agrees**) rather than a fifth hand-built row collection | The git plan’s acceptance; History’s first page not later | L |

### Stack V: The View Slice

The first step of
[Phase 4](plan-2026-11-18-view-model-and-view-state.md#phase-4-the-view-model) in the
view model plan: what each tab shows, and `present` with an object or an address.
It needs T0.1 to T0.3 and T0.7, and runs beside Tier 1. “Slice” below means a step of
delivery; a surface’s part of a view state is a facet.

| PR | Changes | Proves | Size |
| --- | --- | --- | --- |
| V1 `bench(ui): what a view-state publish and a pinned page’s stream cost in Chrome and WebKit` | A record from a prototype kept on the measurement branch | Requests per settled change; connections with three tabs; `MAX_VIEWERS`, `MAX_VIEW_STATE_BYTES`, the debounce | M |
| V2 `feat(ui): ViewState and Intent as the metabrowser.ui contracts` | `ui/` with T0.2’s reference; the two contracts, with the outcome left as the intents route’s internal envelope; `data/ui-format/`; the family registry; T0.7’s second pair; `arch-view-model.md` | Drift, corpus, round trip, source and wheel | M |
| V3 `feat(ui): a viewer registry, /api/ui/viewers, /api/ui/viewer, and POST /api/ui/intents` | In-memory registry with V1’s caps; `GET` and `POST /api/ui/viewers`; the record route `GET /api/ui/viewer`; origin proof; the `control` setting, held in `ui/` outside `Capabilities`, with `--ui-control` and a default set by the caller and not by `--untrusted`; the event stream’s `?viewer=<id>`, served for every subject, with `ui` events alone where the subject has no `watcher` capability (`events_route.py:773`) | `--api` goldens for every refusal a server gives without a page; serving loads no schema library | M |
| V4 `feat(shell): each tab publishes what it shows and applies present intents` | Deferred `static/ui-state.js`: the summary’s `describe` functions, publisher, `openAddress`, applier, notice, `sessionStorage` viewer | `tests/dom/ui-view-state-session.js`; the notice in headless Chrome | L |
| V5 `feat(cli): --api --server, and artifacts from --format yaml` | `cli/api_cli.py` as a client; a `softschema:` header. `--present` does not change: every change to it waits on the live-server registry, mb-5xi4 | `ui.viewer-order` against a harness server | M |
| V6 `test(ui): --show and the page agree, and the parity check counts facets` | Agreement test; a `devtools/check_parity.py` coverage rule over facets | Both fail on a planted mismatch | S |
| V7 `feat(cli): every agent-facing route and contract is discoverable from metab` | The agent interface plan’s [Self-Description](plan-2026-11-18-agent-interface.md#self-description): the agent paragraph in `--help`; a contract identifier in each `/api/routes` entry that has one; `GET /api/contracts` and `GET /api/contract`, which build no validator | Goldens and parity rows for both routes; a test that every `/api/ui` route, object route, and contract is listed; serving loads no schema library | M |

A later V slice, after mb-5xi4, adds `--live` and the intent `--present` sends, its
confirmed report, and the `ui.present-confirmation` row.

### Stack P: The Pull Requests Page

The parent plan’s object slice: `/pulls` as wide rows from the collection the Pulls tab
holds, under Decision 22 D. In Ordering 2 it is no longer the first object type.

| PR | Changes | Proves | Size |
| --- | --- | --- | --- |
| P1 `bench(github): a /pulls page scenario for pr-view, and a control round` | `pr-view.mjs` milestones; protocol; a control round on `main` | P2 to P6’s baseline | S |
| P2 `refactor(github): the pulls rows carry the pull request object` | `github/objects.py`, projected at `github/pull_catalog.py:531`; every reader the parent’s Phase 1 lists, with `pulls-refresh`; six parity rows reread, not regenerated blind | Projection over the drawn-from-disk fixture; Pulls-tab pairs | L |
| P3 `feat(shell): the object store, in the sdk-views bundle` | `static/object-store.js`, `mb.objects`, merge rule, keyed facets, the `changes` loader over `documentRowLines` | A store session; bytes against `static/plugin-sdk-views.js:25` | M |
| P4 `refactor(github): the pulls controller holds objects and reads while any list shows` | Decision 14’s other four changes | A session with the tab hidden and the pane list shown; pairs | M |
| P5 `feat(shell): one list host for a collection in any shape` | On-demand `static/object-list.js`, prefetched once the panel mounts; windowing, Decision 21 keys, disclosure, sections | A list session; the shared keyboard check; tier probe | L |
| P6 `feat(github): the pull requests page at /pulls, as wide rows` | The `wide-row` view replacing `mountPullsLanding` (`github/pulls-panel.js:5509`), under T0.8’s frame; row estimate and overscan; `arch-object-model.md`; map and parity rows | `describePullWideRow` in a session; a Chrome paint test; first paint, scroll, return | L |

### Stacks C, R, and X

**C, core types and contracts**: C1
`feat(objects): file, folder, and commit over the tree, event, recent, and pinned feeds`
(L; adapters registered in P3’s store; the log’s times as UTC strings; #507’s D1, D10,
D18, D20, D22 where landed); C2
`feat(objects): an object contract registry for the five types` (M;
`objects/registry.py`, `data/object-format/`, T0.7’s third pair, `--api` row validation,
once file, folder, commit, pull request, and the working tree can test the header
together); C3
`feat(plugins): declare object types, views, and collections in a manifest` (M;
`--doctor`, `/api/object-types`, two parity rules, `docs/plugins.md`); C4
`feat(folder): a Files view of a folder’s children` (M; key `I`; #520’s retry state if
landed); C5 `feat(shell): a commit’s card and a pull request’s card` (M), which builds
the `card` frame, since Decision 11 leaves the frame to its first real use.

**R, the Recent tab,** is the Recent tab plan’s, in its four phases.
R1, the recent slice, needs the shared definitions (T0.2, T0.3), the store (P3), and the
list host (P5). R2, working-tree changes, needs Tier 1 from T1.2 to T1.5. R3, the GitHub
tier, needs C3 for a plugin’s source.
R4, which includes `/recent` as a page of cards, needs C5. Each source lands on its own
measurement, and so does R4’s edit-history recorder, which is new persisted state.

**X, convergence,** lands item by item behind pairs against the code each replaces, and
any item may be declined: X1, the pull request page reads the object; X2, Pulls rows as
`nav-row` views; X3, Quick Search results as references; X4, the commit row and summary;
X5, the Files tree’s rows.

## Dependencies

```text
T1.1 mb-r5gn ─► T1.2 ────────┐
T0.1 ─► T0.2 ─► T0.3 ────────┴─► T1.3 ─► T1.4 ─► T1.5 ─► T1.6
          │       └─► V1 … V7                     ▲
          └─► P1 … P6 ◄─────────────────────┐     │
T0.8 mb-7t5s ───────────────────────────────┴─────┘
P3 ─► C1 ─► C2 (after P6, T1.3) ─► C3 ─► R3 · C1 ─► C4, C5 ─► R4
T0.3, P3, P5 ─► R1 · T1.5 ─► R2
```

Within those lines, V2 also needs T0.7, P2 needs T0.4, and P4 needs T0.6. X1 to X5
follow the stacks named for each under [Beads to Create](#beads-to-create).
Outside work: C1 waits for #507, C4 for #520, and C3 for #380. #550 and #552, which T0.8
builds on, and #577, which T0.5 follows, have merged.
T0.1 to T0.7 and T1.1 run in parallel, and T1.2 follows T1.1 while T0.2 and T0.3 land; V
and P share only Tier 0 with Tier 1 and run beside it; P3 can start beside P2, and P5
beside P4.

## External Dependencies

| Work | Status, 2026-11-18 | Bears on |
| --- | --- | --- |
| #550, #552 | Merged on 2026-11-18. The header’s builders are in an on-demand `view-header` bundle | T0.8, then T1.5 and P6 |
| mb-7t5s | Open, not started; #506, which it waited on, merged | Is T0.8 |
| #380 | Open draft, awaiting the owner’s decisions | C3 |
| mb-qzny, mb-5xi4 | Open; mb-qzny blocks mb-5xi4 and mb-1zyp | `--live` and every change to `--present`, in a V slice after V7; forged publishes. The agent interface plan’s open AI-7 would bring mb-5xi4’s discovery half ahead of mb-qzny |
| mb-1zyp, mb-54r1, mb-idri | Open, each blocked (mb-qzny; mb-1zyp; mb-5xi4, mb-1zyp, mb-56nq) | Should carry V2’s `Intent` and the intents route’s outcome, not a separate `navigate` |
| #498, #501–#503, #507, #508, #518–#520 | Open drafts (the fdu stack) | C1, C4, Recent’s changed-files source |
| #577 | Merged; it changed the Git routes and the Commits tab | T0.5 starts from it |

## Measurement Gates

A pull request that changes what an existing surface reads lands behind back-to-back
pairs judged by
[the accept rule](../../../../explorations/performance-loop/README.md#the-accept-rule).
Each is a claim about one specific change, so it is judged at the careful tolerance and
not the rough cut, and at the fine tolerance for instruction counts.
[Comparing a candidate with the previous release](../../../../explorations/performance-loop/README.md#comparing-a-candidate-with-the-previous-release)
defines these tolerances and holds their values, and the accept rule says how many pairs
a side an effect this small needs.
Each protocol is committed before the first timed run, as
[Durable Storage](../../../../explorations/performance-loop/README.md#durable-storage)
requires. The harnesses below are in `explorations/performance-loop/`.

| PR | Surface | Harness and metric |
| --- | --- | --- |
| T0.6, P2, P4, P5 | Pulls tab, `pulls` route | `pr-view-pairs.sh --scenario pulls`: `rows[n]`, `lines[n]`; `server-time.mjs` for P2 |
| T0.8 | Pull request and commit headers | `pr-view.mjs --scenario pr` title; #550’s alternating cold loads |
| T1.5, T1.6 | Commits tab | `transitions.mjs`, `git-route-pairs.mjs`: History’s first row |
| V3, V4 | Every page; a pinned page’s new stream | `transitions.mjs` click to paint; `wkprobe.mjs` connections |
| P3 | `sdk-views` bundle | `tier-probe.mjs --module plugin-sdk-views.js` |
| P6 | `/pulls` | P1’s scenario: first paint, scroll long tasks, return |
| C1 | Git log, Files tree feeds | `git-route-pairs.mjs`; `run.py` load-time rounds |
| T0.3, T1.2, V5, V7 | CLI and server start | `startup_pairs.py`, instructions retired |

**Startup budgets.** `devtools/check_startup_scripts.py` holds the eager tier to
`startup_script_requests` and `startup_script_transfer_kb` in
`explorations/performance-loop/performance-budgets.toml` on every `make lint-check`. The
transfer budget is nearly spent, and the check prints the bytes that remain, so nothing
here adds eager bytes: `view-header`, `object-list`, and `git-status-model` are on
demand, the store rides `sdk-views`, and `ui-state.js` is deferred.
The pull-request and pinned shells are reported, not gated, so P6 and V3 state theirs.
`objects/` and `ui/` load no schema library at import or while serving
(`tests/test_plugin_public_api.py:108`, `devtools/check_distribution.py:62`).

## Beads to Create

Parent mb-g5d8 for each.
Existing beads keep their parents: T0.8 is mb-7t5s; T1.1 is mb-r5gn; T1.2 and T1.4’s
per-entry half are mb-u4mf, with mb-y06t’s goldens; T1.6 is mb-vibn.
T1.4’s whole-tree half is the new T1.4b.

| Key | Title | Type | Pri | Depends on |
| --- | --- | --- | --- | --- |
| T0.1 | One target vocabulary in `--present`, selections, and the app | task | P2 | — |
| T0.2 | Shared reference, collection reference, actor, change totals, time | task | P2 | T0.1 |
| T0.3 | `--show` names the object an address selects | task | P2 | T0.2 |
| T0.4 | Derive a pull request’s four states once | task | P2 | — |
| T0.5 | Git log answers `rows` and `next_after` | task | P2 | — |
| T0.6 | Change-line lane lives with the pulls controller | task | P2 | — |
| T0.7 | Contract check takes one pair per registry | task | P2 | — |
| T1.3 | Uncommitted changes as an object | feature | P1 | T0.3, mb-u4mf |
| T1.4b | Whole working-tree comparison, hydrated per file | feature | P1 | mb-u4mf, T1.3 |
| T1.5 | A page for the working tree’s changes | feature | P1 | T1.4b, mb-7t5s |
| V1 | Measure a view-state publish and a pinned stream | task | P2 | — |
| V2 | `metabrowser.ui` contracts | feature | P2 | T0.2, T0.7 |
| V3 | Viewer registry and `/api/ui` routes | feature | P2 | V1, V2 |
| V4 | Tabs publish view states and apply `present` | feature | P2 | V3, T0.3 |
| V5 | `--api --server` and YAML artifacts | feature | P2 | V4 |
| V6 | Agreement test and facet coverage rule | task | P2 | V4 |
| V7 | Agent-facing routes and contracts discoverable from `metab` | feature | P2 | V3, V5 |
| P1 | `/pulls` scenario and control round | task | P2 | — |
| P2 | Pulls rows carry the pull request object | task | P2 | P1, T0.2, T0.4 |
| P3 | Object store in `sdk-views` | feature | P2 | T0.2 |
| P4 | Pulls controller holds objects for any list | task | P2 | P2, P3, T0.6 |
| P5 | List host | feature | P2 | P3 |
| P6 | `/pulls` as wide rows | feature | P2 | P4, P5, mb-7t5s |
| C1 | File, folder, and commit types | feature | P2 | T0.2, T0.5, P3 |
| C2 | Object contract registry for five types | feature | P2 | C1, P6, T1.3, T0.7 |
| C3 | Manifest blocks for types, views, collections | feature | P2 | C2 |
| C4 | Folder Files view | feature | P3 | C1, P5 |
| C5 | Commit and pull request cards | feature | P2 | C1, P5 |
| X1 | Pull request page reads the object | task | P3 | P6, C2 |
| X2 | Pulls rows as `nav-row` views | task | P3 | P5, P6 |
| X3 | Quick Search results as references | task | P3 | C2, C3 |
| X4 | Commit row and summary as views | task | P3 | C1 |
| X5 | One view for Files tree rows | task | P3 | C1 |

Recent’s beads come from the Recent tab plan.

## Risks and the Order That Limits Rework

1. **The header frame first.** T0.8 lands before T1.5 and P6, or both restate the header
   and X1 undoes them, as Decision 12 warns.
2. **A lost distinction.** `repository` and `tree` both become `folder` while three
   readers tell them apart, so T0.1 keeps the fact in a field.
   It raises the app’s floor.
   App pull requests #565, #566, #568, #571, and #575 have merged, so it changes the app
   as `main` has it.
3. **The git plan predates the model.** Its flat rows, keys, and
   `/status/<scope>/<entry-id>` address are settled with the Recent tab plan before
   T1.5, so the page and its Recent entry share one address.
   RT-3 chose `/status` and `/status/<path>`, and the git plan records that address as a
   requirement.
4. **The gate may say no.** If mb-r5gn cannot bound untracked status, Tier 1 returns to
   design while V and P continue.
5. **A second `navigate`.** mb-1zyp and mb-54r1 would build a page-following path beside
   V3 and V4; rebase them on the `present` intent.
6. **The inventory contract under two hands.** Recent’s changed-files cursor is a
   provider requirement while #507 and #508 rewrite that contract.
7. **Two Recents.** The tab’s name collides with the Files tab’s Recent view and Open
   Recent, as Decision 19 warned.
   The Recent tab plan’s RT-6 keeps the Files filter and retires its name.

## Done for Each Stack

- **Tier 0:** goldens differ only in what each renames; CHANGELOG notes for T0.1 (the
  `--present` tokens, the app’s floor), T0.5 (the log’s keys under `--api`), and T0.8.
- **Tier 1:** the git status plan checked off and moved to `specs/done`; `arch-git.md`
  and the URL grammar updated; `docs/project/architecture/arch-object-model.md` added
  with the shared definitions and the first type, and no contract table under Decision
  22 D; a CHANGELOG entry.
- **V:** `docs/project/architecture/arch-view-model.md` with its checked contract table;
  the parity rows; the design-system entry; a CHANGELOG note naming `control`.
- **P:** `arch-object-model.md` gains the shapes, store, list host, and pull request
  projection; design-system sections for object views and a list in the pane; map rows;
  a CHANGELOG entry.
- **C:** the contract and declarations tables, each with its check; Plugin Authoring; a
  CHANGELOG note for the manifest blocks.
- **R and X:** the Recent tab plan’s criteria; each X item landed or recorded as
  declined. Then the parent plan, its companions, and this map move to `specs/done`.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
