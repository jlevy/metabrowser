# Review: Bead and Spec Audit, 2026-11-14

**Date:** 2026-11-14

**Status:** A dated record of one audit, not a maintained table.
The bead changes it lists were applied to tbd on 2026-11-14 and synced; the spec changes
are in the same pull request as this record.
For a bead’s current state, run `tbd show <id>`.

## Scope and Method

The audit covered the 402 beads that were not closed at `main` c098e6a8 (371 open, 25 in
progress, 6 deferred) and every plan spec in `docs/project/specs/active/`. Ten read-only
agents each took one area, split by spec and parent epic, and checked each bead and spec
against the code on `main`, merged pull requests, tags, `CHANGELOG.md`, and the
performance loop’s experiment records.
Each verdict cites a pull request, a commit, or a file and line.
The audit’s coordinating agent reviewed every proposal, resolved conflicts between
areas, held decisions that belong to the owner, spot-checked closes in the code, and
applied the rest. A bead another session changed during the audit was skipped, not
overwritten.

## Summary

- **Closed:** 56: 21 done, 28 obsolete, and 7 duplicates.
- **Updated:** 156 beads had fields changed, 22 dependency edges changed, and 92 beads
  got a dated audit note.
- **Specs:** five complete plans moved to `docs/project/specs/done/`, and the rest of
  `active/` was corrected in place.
  The pull request description lists them.
- **Not applied:** the decisions under [Held for the Owner](#held-for-the-owner), and
  `mb-hwxu`, which the native-app session was editing.
  The perf-campaign session closed its landing tracker `mb-pgva` itself, so it is not
  listed here.

## Correction After Review

The audit first closed `mb-8pyc` (the folder comparison of more than 50 files against
v0.11.0) as done, because the comparison passed on `a5390794`, whose tree is the
`v0.12.0` tag’s. The run stands, but the bead’s own notes keep two things open:
attributing the run to the release commit, and the owner’s acceptance, which the owner
deferred at `mb-4bd2` as remaining owner QA. Review A on #434 caught the premature
close, and review B corrected the reason.
The bead is open under `mb-425f` and is listed with the other deferred checks under
[Held for the Owner](#held-for-the-owner).

## Closed Beads

### Done

| Bead | Title | Evidence |
| --- | --- | --- |
| `mb-281d` | Future: Add source-view line location targets | Done in #235 and #239 (on main through #260): Source views carry GitHub-style #L line anchors; docs/architecture.md records that a line-anchor fragment wins over a heading id, as on github.com. |
| `mb-5zuz` | Fetch pull request changes automatically on first open | Fixed by #346 (merged 2026-11-11, with #348 and #351): opening Changes or a changed-file link prepares a missing comparison automatically, with progress and a retry only after a failure; its follow-ups mb-99l2, mb-01s3, mb-j5xp and mb-85qc are closed. |
| `mb-957c` | #362 B4: Required validation evidence is incomplete | #362 merged 2026-11-13 (8f447c61) with all 10 required checks green at its head, including the macOS app workflow. |
| `mb-9n12` | Land the ranked large-PR performance fixes | The ranked large-PR fixes landed in #284 (first-screen mount, prepared manifests); the windowed file list continues as mb-ivvw, of which mb-mwuz was closed as a duplicate. (Corrected after review A on #434; the bead’s close reason is the original, and a dated note on it records this.) |
| `mb-a9ek` | Implement cache-first PR review and rendered Markdown | The cache-first PR review designs landed in stack #350 (#346 to #349, 2026-11-11); paired browser timing stays open as mb-5rth. |
| `mb-f33i` | Address review: #101 — holistic pluggable-inventory-engine review | #101 merged on 2026-09-09 with 15 of 20 findings closed; the five deferred findings move under mb-8127 (pluggable inventory engine). |
| `mb-hall` | v0.12 thin mirror: GitHub-web-like browsing from a local git/gh mirror | The thin-mirror plan is delivered (#227 to #268) and shipped in 0.12.0 on 2026-11-09; its open follow-ups are reparented to mb-425f, mb-k7zy, or detached. |
| `mb-hgnf` | Files section lacks the pending skeleton that File Breakdown shows | Fixed: pending totals no longer read as a zero table (801b8d99, #59), and the Files totals show their skeleton beside File Breakdown’s throughout a scan (e758292b), pinned by cli-ui-file-overview.tryscript.md. |
| `mb-lzwc` | A refused .env key name reaches the terminal unsanitized, so a repository can write escape sequences to stderr | Fixed by 2f033ed1 (in 0.12.0): dotenv.py routes refused key names and the file path through loggable, with tests/test_dotenv_loading.py:143-144 pinning the escaped form. |
| `mb-m13a` | Load PR catalog progressively with accurate repository totals and lazy details | The progressive catalog with exact totals, Open/Closed/All with Open default, lazy details and aligned PR tabs merged in #289, #291 and #292 on 2026-11-04 (Fetch more later replaced by scroll paging, #311 and #410); follow-up mb-xl14 moves to mb-8rpp. |
| `mb-niod` | Independent review of the v1 app, addressed | Done in #377 (merged 2026-11-13): whole-app reviews C, D, and E were addressed, and follow-up rounds A-F ended with approvals (E: no new findings). |
| `mb-nns2` | Swift app code meets the tbd coding guidelines | The tbd-guidelines pass landed in #362 (apps/macos/README.md, Coding Guidelines, lists what is left on purpose), and the later layers were reviewed against the same guidelines in #377 (mb-niod), which the bead named as its closing condition. |
| `mb-nr7s` | #362 A8: Required validation is not evidenced at the pinned head | #362 merged 2026-11-13 (8f447c61) with all 10 required checks green at its head, including the macOS app workflow. |
| `mb-q3jt` | Step 4: changed files in a row, expandable like a folder | Step 4 merged in #287 (with #297) on 2026-11-04: changed-file trees, /pull/<n>/files/<path>, and the keyboard file walk are on main; follow-ups mb-egnj and mb-w5rc move to mb-8rpp. |
| `mb-t5x3` | H53: count region repaints as a standing metric, then reduce them | Done: tree_region_repaints is a required standing metric (run.py METRICS, performance-budgets.toml maximum 1, accept-rule item 4) and the tree region paints once per load since exp-014 (mb-izxl); viewport-wide coverage is H56’s visual_states (mb-unt6). |
| `mb-v0rk` | #374 A4: dead chord branch in appendBinding() and chord wording in the design system | Fixed in 5be9aec3 (landed with #383): appendBinding has no chord branch and docs/design-system.md:196 says one .kbd per alternative key. |
| `mb-wgl7` | Native window title: bold short name, dim bullet and Metabrowser | Done in #341 and refined in #391 (mb-9xbp): the title bar shows the folder’s bold short name, with window.title, the tab title and tooltip, the subtitle, and the path menu for local folders (WindowTitle.swift, BrowserWindowController.showTitle, WindowTitleTests); the bullet and Metabrowser were dropped at the user’s request. |
| `mb-yoiq` | #362 C7: Required validation is not established at the reviewed head | #362 merged 2026-11-13 (8f447c61) with all 10 required checks green at its head, including the macOS app workflow. |
| `mb-ywt7` | PullFileList: job, routes, and bounds | PullFileList, its bounded job, GET pull-files and POST pull-files-refresh merged in #287 and #297 on 2026-11-04; the expected-count and shared-manifest follow-ups mb-egnj and mb-w5rc move to mb-8rpp. |
| `mb-zn0u` | #374 A3: activateScope() accepts a permanent scope and reverses the documented precedence | Fixed in a8a2c848 (landed with #383): activateScope throws on a permanent scope, tested in tests/dom/keyboard-shortcuts-behavior.js:640-646. |
| `mb-zxo2` | Repository identity rediscovery (GIT_REPO_INFO_TTL_S, 5 s) adds about 60 ms to whichever git request pays it | Fixed in #368 (36d3e325, fc2a6d84; merge c74d0ef3): an owned repository keeps its identity past the 5 s TTL while its refs’ state is unchanged and is rediscovered off the request after 60 s, so an interactive request no longer pays the rediscovery (exp-086: TTL-boundary comparison ratio 1.59 to 1.00). |

### Obsolete

| Bead | Title | Evidence |
| --- | --- | --- |
| `mb-1742` | Hosted releases R4 implementation: discovery cache and virtual collection | Obsolete as written: the R4 implementation publishes ReleaseIndex/v1 through hosted_releases and a generic virtual collection, none of which exist on main; a thin-mirror re-plan under mb-7srn would file new beads. |
| `mb-27dr` | diff/wire.py + diff/routes.py: browser contract and the /api/diff/ collection | Superseded by the diff plugin’s document, children, and comparison data hooks and diff/format.py validation; no core /api/diff/ collection is planned by any current document. |
| `mb-2u4m` | Hosted releases R2 review: publish the direct-cache PR | Obsolete: publication bead for the retired R2 direct-cache PR; re-planned release work under mb-7srn would get its own review beads. |
| `mb-42j7` | Hosted releases R0 implementation: models, codecs, profiles, and corpora | Obsolete as written: the R0 implementation targets provider_resources and hosted-review artifact codecs that #246 removed (kept only on draft #247); a thin-mirror re-plan under mb-7srn would file new beads. |
| `mb-5m4h` | Hosted releases R0 review: publish the contract PR | Obsolete: publication bead for the retired R0 contract PR; re-planned release work under mb-7srn would get its own review beads. |
| `mb-7uta` | Platform A2: SDK data-plane v2 — POST bodies, streaming/NDJSON, SSE helper wired to view disposal | Superseded: the diff viewer became a built-in plugin, mb-qatc shipped without this, and the thin-mirror plan (#227) retired new public SDK surface for it; reopen under mb-xbw3 if a third-party plugin needs a POST/streaming data plane. |
| `mb-aw0x` | Hosted releases R2: direct release and asset cache | Obsolete as written: R2 publishes through the auth-scoped provider store that the thin-mirror plan retired and #246 removed (kept only on draft #247); release browsing stays tracked by mb-7srn until re-planned. |
| `mb-bbw8` | Hosted releases R3: direct release document and asset children | Obsolete as written: R3 registers a resource kind and generic /hosted address through SDKs the thin-mirror plan retired (absent on main); release browsing stays tracked by mb-7srn until re-planned. |
| `mb-bcdu` | Investigate merged-main cold-start shell-paint tail variance | Not reproduced: the single 996 ms FCP run on bae51fd (exp-015) did not recur in the v0.7.1 or v0.8.0 comparisons (exp-017, exp-019, FCP at most 192 ms), and H57 attributed the shell boot (mb-emhr). |
| `mb-bdso` | Add browser-grade DOM and payload contract coverage | Superseded: lifecycle and disposal coverage is the functional UI parity plan’s mb-wgka (browserless production-JS sessions plus targeted Chrome tests), and payload contracts are the API schema plan’s mb-xzb1 and mb-qdr1. |
| `mb-esj2` | Hosted releases R1: GitHub coverage oracle and gh mapping | Obsolete as written: R1 maps into the retired R0 contracts and the GitHub coverage oracle that #246 removed (kept only on draft #247); release browsing stays tracked by mb-7srn until re-planned. |
| `mb-fkcs` | Hosted releases R4: bounded index and Releases navigation | Obsolete as written: R4 publishes the retired ReleaseIndex contract on top of R3; the Releases list stays part of mb-7srn until re-planned on the thin mirror. |
| `mb-g6ed` | Hosted releases R0: freeze provider-neutral release contracts | Obsolete as written: R0 builds on the plugin-declared artifact contracts and resource profiles, the frontmatter-md profile among them, that the thin-mirror plan retired and #246 removed (kept only on draft #247); the core registry that remains admits only pure-yaml. Whether release browsing is re-planned or dropped is the open decision in mb-7srn. (Corrected after review A on #434; the bead’s close reason is the original, and a dated note on it records this.) |
| `mb-g74x` | Hosted releases R3 review: publish the direct-view PR | Obsolete: publication bead for the retired R3 direct-view PR; re-planned release work under mb-7srn would get its own review beads. |
| `mb-glxc` | Hosted review Phase 6: stacked change requests and projections | Superseded: native GitHub stack membership and navigation landed via mb-5m05 (#292, #325), and the owner’s rule to read native membership and never infer stacks from base branches replaces this provider-store derivation design; file new beads for aggregate stack status or per-layer comparisons if wanted. |
| `mb-gp0k` | Hosted releases R4 review: publish the discovery/nav PR | Obsolete: publication bead for the retired R4 discovery/nav PR; re-planned release work under mb-7srn would get its own review beads. |
| `mb-kk47` | Hosted releases: stack landing, retargeting, and post-merge verification | Obsolete: landing owner for the retired R0-R4 release stack, which will not be built as designed; a re-plan under mb-7srn would define its own landing. |
| `mb-lvno` | #280 A11: What could leave the eager tier | Superseded by the 2026-11-12 eager startup-script cost research (exp-084), which measured the tier, set the ceiling at 220 KB, and names removing per-request compression as the first lever, so moving perf.js out is no longer an open question. |
| `mb-ndeh` | Review #341 native shell spike for safe, isolated landing | Superseded: #341 merged on 2026-11-13 after the review rounds tracked by mb-o2kn and the whole-app review in #377 (mb-niod); this separate read-only review was stopped on 2026-11-08 and never published. |
| `mb-npdt` | Hosted releases R1 review: publish the GitHub mapping PR | Obsolete: publication bead for the retired R1 mapping PR; re-planned release work under mb-7srn would get its own review beads. |
| `mb-nz6a` | Hosted releases R2 implementation: direct URL acquisition and publication | Obsolete as written: the R2 implementation targets ProviderResourceStorePort, format_hosted_address and reduce_github_url, none of which exist on main after #246 (kept only on draft #247). |
| `mb-o2hk` | Record load-time baselines at 10k, 100k, and 1M and replace the proposed budgets | Superseded: the loop’s validated budgets are in performance-budgets.toml (calibrated on project-10 in exp-035) and its flat-stress companion, and the loop no longer measures build_corpus at 10k, 100k, and 1M; the million-file case is mb-s5p6’s. |
| `mb-oo4w` | Hosted releases R3 implementation: route, views, Source, and assets | Obsolete as written: the R3 implementation composes views through ResourceKindSpec and AddressSpaceSpec, which do not exist on main; a thin-mirror re-plan under mb-7srn would file new beads. |
| `mb-osqu` | Platform A6: expose MtimeCache (or generation-keyed cache) through plugin_api | Superseded: the diff plugin is built-in with its own commit-keyed comparison cache, and third-party plugin Python is moving out of process (mb-xbw3); reopen there if a plugin needs a host cache. |
| `mb-p2mi` | Comparison context in the Files tree: manifest as a third source | Superseded by the nav-container model: patch files expand to file-change children with indicators (mb-6ba6, mb-um0p), and View file controls (#248) cover the After view. |
| `mb-t1wt` | Platform A3: expose file-change event subscription/emission to installed plugins via plugin_api | Superseded: the diff plugin is built-in, comparison caches are commit-keyed, and uncommitted-comparison staleness is core work in mb-vibn (mb-tcdy closed as its duplicate); browser views already have onInventoryChange. Reopen under mb-xbw3 if an out-of-process plugin needs server-side change events. (Corrected after review A on #434; the bead’s close reason is the original, and a dated note on it records this.) |
| `mb-uawv` | diff/service.py: resolution, self-describing IDs, bounded caches | Superseded: adapters are wired at call sites with no registry, builtin_plugins/diff/comparison_cache.py bounds commit-ID comparisons (#284), and volatile generations belong to the Git-status plan (mb-u4mf). |
| `mb-xj80` | Hosted releases R1 implementation: oracle and GitHub normalization | Obsolete as written: the R1 implementation normalizes into hosted_releases contracts and a coverage oracle that do not exist on main (#246 removed the oracle; kept only on draft #247). |

### Duplicates

| Bead | Title | Duplicate of | Reason |
| --- | --- | --- | --- |
| `mb-0qkd` | Text preview: measure whether content-visibility helps past 16 MiB | `mb-1bh1` | Duplicate of mb-1bh1 (H99): content-visibility chunks for long source views, measured with find-in-page checked; its measurements are superseded by docs/large-content-rendering.md’s 2026-11-12 runs. |
| `mb-65mg` | Maintain navigation tallies per write so the first root request is bounded | `mb-0cmt` | Duplicate of mb-0cmt (H34): both maintain the navigation tallies per write in _replace_index_entry and _pop_index_entry; this bead’s notes move to mb-0cmt. |
| `mb-f591` | Measure the shell over --remote before touching request count (H26) | `mb-ycf2` | Duplicate of mb-ycf2 (H44), which owns measuring the remote-link regime; the concat fix this bead names is mb-a1nu (H96). |
| `mb-lny9` | #392 C1: add the Chrome version to --summarize’s pooling conditions | `mb-djo1` | Folded into mb-djo1, whose description already requires adding the Chrome version to tier-probe.mjs’s pooling conditions before it pools runs. |
| `mb-mwuz` | A windowed changed-file list past a few hundred files | `mb-ivvw` | Same work as mb-ivvw: window Files changed’s sections past a few hundred files, decided with the changed-files nav (mb-q3jt); exp-040’s 611 ms projection of 1,183 sections predates the first-screen mount mb-ivvw records. |
| `mb-tcdy` | Watcher-driven stale for uncommitted comparisons | `mb-vibn` | Duplicate of mb-vibn: Git-status Phase 2 specifies the watcher-driven stale state and refresh for working-tree comparisons. |
| `mb-xhtc` | Phase 3: single GraphQL query per PR record refresh | `mb-6aa8` | Same work as mb-6aa8, which holds the measurement and the design constraints for replacing a record refresh’s REST reads with one GraphQL query. |

## Updated Beads

Field names mean the text was rewritten: `title` or `description`. Labels are shown as
`+label` and `−label`.

| Bead | Title | Changed | Why |
| --- | --- | --- | --- |
| `mb-06up` | v0.12 test-suite review: maximum coverage, minimum test complexity | −release:v0.12.0, parent → none | The release-labelled children landed before 0.12.0 (#251-#258, all closed; 11 children closed). |
| `mb-0cr3` | Remove discarded patch payload from GitHub file-list fallback | status → open, description | Still valid: src/metabrowser/builtin_plugins/github/pull_files_refresh.py:180 reads repos/<owner>/<repo>/pulls/<n>/files and :124 drops each item’s patch after download. in_progress since 2026-11-03T21:47 with no commits naming it and no PR (git log --grep=mb-0cr3 origin/main: none). |
| `mb-0l4a` | H45: replace stdlib json with orjson on the tree and rollup routes | parent → mb-ww58, spec → plan-2026-08-21-load-time-performance.md, description | Open in the plan’s H45 row. orjson appears nowhere in pyproject.toml or src/. |
| `mb-0ybg` | Repository library follow-up: generic Git catalog, refresh, and cache management | description | Description assumes the ‘provider-facing slice’ and objects reachable from ‘any alias, provider, or lease’, but the thin-mirror Simplify step (#228, merged 2026-10-03) removed convergence, subject refs, leases, and store reclamation, and Phase 2B was superseded. |
| `mb-19em` | H46: bulk-attribute syscalls for the verification sweep | parent → mb-ww58, spec → plan-2026-08-21-load-time-performance.md, description | Open in the plan’s H46 row ('Only matters once H21 exists'). |
| `mb-19sr` | Drive Mermaid diagram theme from data-theme and re-render on theme change | description | Description is null; scope is Mermaid plan Phase 2 item 1. |
| `mb-1apq` | Native macOS app: thin AppKit shell over metab | description | The description says native app changes stay on the spike branch and #341 is not to be merged, but #341 merged to main 2026-11-13T07:19Z (gh pr view 341: MERGED, merge commit 2e569c25, an ancestor of origin/main), as did #359, #361, #362, #363, #377 (merge commits 2e569c25, 7323330b, 8f447c61) and the title-bar follow-ups #384, #388, #391, #398, #403. apps/macos/ exists on main (apps/macos/Package.swift, apps/macos/README.md). |
| `mb-1qsn` | Stabilize the test suite under machine load before v0.10.0 | title, description, P2 | The v0.10.0 gate in the title passed (tag v0.10.0, 2026-09-15); its starting flake mb-0mu9 is closed (tbd list --all). |
| `mb-1wk1` | Untracked GitHub capability gaps from the thin-mirror Capability Map | description | Description says the Pulls tab beads mb-lnkl, mb-iw1v and mb-cbak are ‘deferred’; all three are closed and the Pulls tab shipped in 0.12.0 (#285, #287, #288; release notes). 0.12.0 has a Checks tab (#310); logs are still not fetched (no Actions logs code under src/metabrowser/builtin_plugins/github/). |
| `mb-25nv` | Native shell: prewarm at launch, hidden load, reveal on ready, spare web view | description | Description says ‘Deferred: apps/macos stays unmerged’; apps/macos is on main through #341. |
| `mb-273l` | Run revision-page Markdown renders in the projection child with a deadline | description, parent → mb-2iok | Still valid: src/metabrowser/builtin_plugins/github/pull_snapshot.py:135 _DOCUMENT_WORK_MS = 400, :450 plain_code=True, :491 the estimate check. |
| `mb-296z` | Move /api/catalog to the on-demand tier, fetched when the finder first opens | description | The buffering policy the old text asks for exists: src/metabrowser/static/catalog-feed.js:395-440 (start, hold, release; onCatalogChange returns early while held), added in commit b8d03f0e (on main since 2026-11-04); app.js:8448-8452 holds the feed on a pull-request page. |
| `mb-2g6f` | Landing gate: regular-folder behavior is unchanged from v0.11.0 except documented fixes | status → open, parent → mb-425f | in_progress with no note since 2026-11-08T17:51Z. 0.12.0 shipped 2026-11-09 at 87b8ec81 with this gate’s final data and browser differentials incomplete; mb-4bd2’s 2026-11-09 notes say the owner approved the release ‘with the timed comparison and remaining owner QA open’ and that they ‘retain separate open beads’. |
| `mb-2iok` | Review pull requests well on large repositories: fresh mirror and existing checkout | status → open, −release:v0.12.0, description | Claim not live: started 2026-11-07, last update 2026-11-09; no origin/main commit since 2026-11-09 names mb-2iok or any open child (mb-4ifm, mb-9n12, mb-8pyc, mb-i9ll, mb-jwfx, mb-8kx1, mb-vbnn, mb-itzy, mb-mwuz: 0 each). |
| `mb-2ozh` | Design vocabulary: extend row and chevron enforcement to every surface | description | Height and hover agreements still cover only .tree-item and the diff bar (tests/test_design_vocabulary.py:49-58, :564-572). |
| `mb-2zp3` | Settled navigation tally is 1.2-1.3x slower than v0.9.1 on a 300k tree | parent → mb-odrb | Measurement-only bead (v0.10.0 candidate 03fd7997 against v0.9.1 on the 300k synthetic corpus); not re-measured here. |
| `mb-32en` | Measure an idle Markdown worker’s memory before keeping it 60 s | description | MARKDOWN_WORKER_IDLE_MS is not on main (git grep: none); it is at 6b876c54:src/metabrowser/builtin_plugins/markdown/markdown-worker-client.js:23, H90’s code, which bd971661 took out of #368. |
| `mb-32y6` | Math in a mirrored repository’s Markdown shows as raw TeX under the untrusted profile | parent → mb-k7zy | Still true: the inert allowlist removes MathML (SECURITY.md:89; src/metabrowser/static/inert-html.js), and no server-side math typesetting exists. |
| `mb-380k` | Archive containers: browse .zip through the container contract | parent → mb-p7ts, spec → arch-nav-containers.md | Archives remain unimplemented (docs/project/architecture/arch-nav-containers.md:3-8, :46, :78). |
| `mb-3arq` | P2: add complete server filename search provider | description | Its ‘blocks mb-wzy6’ dependency holds full-text search behind a deferred, evidence-gated fallback; the spec makes Phase 3 an independent /api/search/text endpoint (plan-2026-07-17-scalable-file-search.md, Full-Text Provider and Phase 3) and the shared provider runtime already exists (static/search-controller.js). |
| `mb-3s45` | Root /api/tree server time is 3-44x v0.9.1 during a walk on a repository-shaped tree | parent → mb-ww58 | Mechanism still documented on main: docs/project/architecture/arch-python-inventory-cost.md:116-123. exp-034 (experiments/exp-034-v0100-quiet-machine-rejects-the-candidate-on-300k.md:326) records it as mb-3s45. |
| `mb-3vpj` | Measure what the server-topology brief left open | description | Not started. |
| `mb-425f` | v0.12 release stability and manual acceptance | title, −release:v0.12.0, description | 0.12.0 is tagged and published: `git ls-remote --tags origin` has refs/tags/v0.12.0 at 87b8ec81 (merge of #344, 2026-11-08 17:33 -0800); `gh release view v0.12.0` publishedAt 2026-11-09T16:21:26Z; ‘Publish to PyPI’ run 42653937221 conclusion success; CHANGELOG.md:616 ‘## 0.12.0’. |
| `mb-479j` | #273 https://github.com/jlevy/metabrowser/pull/273#discussion_r4436440679: a review range starting on the other side loses its start | parent → mb-425f | Still valid: src/metabrowser/builtin_plugins/github/pull-page.js:648-650 says the record does not keep start_side; no start_side anywhere in builtin_plugins/github; pull_record.py:55 PULL_RECORD_SCHEMA = 2. |
| `mb-48vd` | Aggregate delivery: compute once, push incrementally | P3 | The steady-state goal is met: mb-l8oy (ETag /api/rollup), mb-weoj (coalesced identical rollups), and mb-bb8v are closed. arch-state-and-delivery.md:715-722 says ‘effectively compute-once’ and records mb-gqci as deferred. |
| `mb-4ifm` | Make PR and Git navigation feel immediate with measured prefetching | status → open, description | in_progress since 2026-11-05; last bead update 2026-11-08; no commit on any ref mentions mb-4ifm, mb-5rm1, mb-97ex or mb-06p9 since then (git log --all --since=2026-11-09 --grep), and the named branch codex/perf-prefetch-20261104 merged as #299 on 2026-11-08. |
| `mb-5fp7` | Clean-account matrix for both setup flows | description | Not started. |
| `mb-5no9` | Profile remaining first catalog and warm serving overhead against main | title, parent → mb-ww58 | Parent mb-jqvz is closed. |
| `mb-5rm1` | Attribute cold PR and Git navigation waterfalls before changing prefetch | description | Still open in the plan (H74 row: open for first-tab controls). |
| `mb-5rth` | Compare rendered and Source PR startup on documentation-heavy diffs | parent → mb-2iok | The measurement is not recorded anywhere (grep 'documentation-heavy'/'docs-heavy' in docs/ and explorations/: only the diff spec’s ‘Still open’ list). #349 merged 2026-11-11 (into codex/pr-review-cache-loads; on main through #351, ab346bf8). |
| `mb-609b` | H49: measure the four unrecorded regimes — interaction, churn, memory, warm reopen | parent → mb-ww58, spec → plan-2026-08-21-load-time-performance.md, description | Open, P0, in the plan’s H49 row. |
| `mb-6aa8` | #284 E4: a pull request’s record refresh takes 3.7-4.7 s against a 1.5 s budget | parent → mb-2iok | Same work as mb-xhtc ‘Phase 3: single GraphQL query per PR record refresh’: mb-6aa8’s remaining work is 'the one-request refresh, the second half of the study’s fix 6 (or one GraphQL query)'. |
| `mb-6koa` | #272 https://github.com/jlevy/metabrowser/pull/272#discussion_r4436441172: review-github-pr letter re-check omits the linked-issue and review-doc sweeps | parent → none, +upstream-tbd | Still valid with tbd 0.10.0 (tbd --version): docs/tbd/shortcuts/review-github-pr.md:226-228 step 9 repeats only ‘the formal review and PR comment sweeps from step 5’, while step 5’s discovery sweep (line 91 onward, linked-issue reads at line 99) has more. |
| `mb-6o0l` | #101 R3.3: provider restart is unrecoverable | description, parent → mb-8127 | Behavior unchanged, line references stale. |
| `mb-6rdn` | H42: client-side tree replica in IndexedDB, painted before the server answers | parent → mb-ww58, spec → plan-2026-08-21-load-time-performance.md, description | Open in the plan’s H42 row. |
| `mb-6yoz` | Check multi-file browser formatting in the pre-commit hook | parent → none, spec → none | Parent mb-4bd2 is closed. |
| `mb-725d` | Extend vendor pipeline with esbuild single-entry ESM bundling (workers, ESM-only libs) | description, P3, parent → mb-0b2h | Cited doc research-2026-07-18-diff-ui-stacks-and-browser-build-options.md no longer exists; its bundling option now lives in docs/project/research/research-2026-07-18-browser-contributor-toolchain.md:125-140. |
| `mb-76nv` | Rerun the WebKit gate under normal conditions | description | Still to do: docs/large-content-rendering.md:501 records only the 2026-11-11 run. |
| `mb-7l9k` | Prove large-directory startup and interaction budgets | parent → mb-ww58, spec → plan-2026-08-21-load-time-performance.md, description | Half of it exists: devtools/bench_serving.py:465 build_corpus generates synthetic corpora (--files, default 100,000, :1444); explorations/performance-loop/performance-budgets.toml and performance-budgets-flat-stress.toml are gated budgets. mb-o2hk (open, P0, under the load-time epic mb-ww58, spec plan-2026-08-21-load-time-performance.md) records page-load baselines at 10k/100k/1M against build_corpus. |
| `mb-8127` | Implement the pluggable inventory engine | description | Description is null. |
| `mb-8bjd` | Diff P2: comparison presets, history browsing, and content-at-revision | title, description | Done parts: Git history paging in the Commits tab (specs/done/plan-2026-08-25-unbounded-virtualized-git-history.md; static/git-history-window.js); commit-vs-first-parent with empty-tree root and --diff-merges=first-parent (diff/adapters/git.py:342-357, :440); View file at base or head on a pin (55c9bf17, #248 via #260; commit message: ‘a served folder gets no control’). |
| `mb-8kx1` | Several servers on one cache: report what is slow or confusing | −release:v0.12.0 | Still undecided: src/metabrowser/cli/serve.py:340 picks the next free port with find_available_local_port and prints no line of its own for a moved port. |
| `mb-8rpp` | Spec: GitHub Pulls tab for mirrors and local checkouts | status → open, P2 | Every delivery layer is merged: #279, #281, #285, #287, #288 and #289-#298 (2026-11-04), shipped in v0.12.0 (tag 2026-11-08; merge commits of #287, #288, #289, #311, #312, #325 are ancestors of v0.12.0). |
| `mb-8xcu` | Reduce excess file-tree right-side spacing | status → deferred, description, parent → mb-ge1b | No description. |
| `mb-8yqt` | H39: price the gitignore matcher — walk with and without gitignore_check | parent → mb-ww58, spec → plan-2026-08-21-load-time-performance.md, description | Open, P0, in the load-time plan’s H39 row. |
| `mb-9696` | R5: make the recency filter cacheable via sorted mtimes and binary search | parent → mb-48vd, description | cached_rollups no longer exists (removed in the provider refactor, 0577bb125). |
| `mb-96ho` | Patch emitter: ChangeSetDocument to git-applyable unified patch text | parent → mb-ypme, description | No emitter exists in src/metabrowser/diff/ (only diff/markdown_projection.py has an unrelated emit); diff CLI formats are text\|json (cli/diff_cli.py:7, :277). docs/project/architecture/file-diff-format/file-diff-format.md:118-121 calls the emitter ‘tracked work’. |
| `mb-97ex` | Test whether natural intent timing and request joining prepare navigation | description | Still open in the plan (H75 row: open for intent timing; H92 row: ‘H75 stays open for intent timing’). |
| `mb-98mi` | Vendor Mermaid 11.17.0 ESM build with a directory-shaped vendor entry | description | Still accurate: devtools/vendor_assets.py:30-31 PER_FILE_CAP_BYTES 1,700,000 and TOTAL_CAP_BYTES 3,000,000; ENTRIES at :42 are flat files; vendored total still 432,092 bytes (ls -l static/vendor/*.js). |
| `mb-9uyb` | Separate release artifact construction from OIDC publishing | description | Still one privileged job: .github/workflows/publish.yml:11 build-and-publish with id-token: write at :19-20 runs make verify (:46-47), the version checks, uv publish (:85-86) and the smoke test; 0.12.0 was published through it (run 42653937221). |
| `mb-a1as` | Parser ingest completion: GIT binary payloads, REST bare hunks, mbox framing | title, description, parent → mb-ypme | (1) Still open: ‘GIT binary patch’ only sets binary (src/metabrowser/diff/adapters/patch_file.py:342-343). |
| `mb-a5ru` | Persist recent and added roots in metab, served by a roots route | description | Not started (no roots route in src/metabrowser). |
| `mb-azg2` | SSE routes are exempt from parity; bounded frame capture would cover them | description, parent → mb-n9xg | The description says --api ‘bounds the request and fails’; main now detects text/event-stream on http.response.start, disconnects, and fails at once (src/metabrowser/cli/asgi_client.py:242, :301-305), which is the detection half of the proposed option. /api/events and /api/stream are still exempt rows. |
| `mb-b34e` | A file-type label breaks mid-word in a narrow pane | description | Rule still present but moved and its surface changed: src/metabrowser/builtin_plugins/folder/file_type_summary.css:104-107 .file-type-summary-type { overflow-wrap: anywhere } (was line 65), with the type column at width 24% (:94-96); the class is set in distribution-view.js:435 on the table. |
| `mb-b4j3` | Keep the 0.11.0-differential harnesses, and make their live counters deterministic | parent → mb-425f | Still undecided; the harnesses are still outside the repository (mb-2g6f notes). |
| `mb-bi2c` | Acquire SSH Git URLs into the shared mirror | description | Description is stale: it says #217 supports file:// only and child mb-s1lt gates HTTPS, but HTTPS shipped in mb-bgs7 (#231, merged 2026-10-03) and mb-s1lt is closed. ssh stays closed on main (src/metabrowser/cache/acquire.py:6). |
| `mb-brys` | Author declarations for /api/file and the plugin hook envelopes | description | ‘Plugin hook envelopes have no TypedDict at all’ is no longer true for the built-in GitHub plugin: PullEnvelope (builtin_plugins/github/pull_route.py:118), PullFilesEnvelope (pull_files_route.py:125), PullListEnvelope, StackEnvelope, PrefetchEnvelope; TypeAdapter(PullEnvelope) emits 20 required keys (checked 2026-11-14). /api/file still has none. |
| `mb-cds1` | WS-1: workspace hygiene: gh stack metadata, unpushed feat/git-graph-view and #13-folder-treemap, .pnpm-store ignore | spec → none, description | The .pnpm-store item is done (#226, per the 2026-09-22 note). |
| `mb-cf6y` | Run the 0.12 release rehearsal against published 0.11.0 | status → open, parent → mb-425f | in_progress; last note 2026-11-09T06:46Z (quiet preflight deferred, no capture). explorations/performance-loop/experiments/ has exp-056-previous-release-rehearsal.md and no exp-057. 0.12.0 published 2026-11-09; mb-4bd2 notes: ‘Timed previous-release comparison and remaining owner QA were deferred by the owner and retain separate open beads.’ Both blocks targets closed (mb-n2ro, mb-4bd2). |
| `mb-cz5s` | Diagnose native Chrome keyboard stall and restore final browser coverage | status → open | in_progress since creation 2026-11-08T17:11Z with no notes. |
| `mb-d1uo` | Detached LRU of file surfaces with a suspend and resume view contract | description | Description says ‘SDK suspend()/resume() hooks with a version bump’; the plan’s API Changes (plan-2026-11-11-ui-apparent-performance.md, ‘The hooks are additive, so PLUGIN_SDK_VERSION does not change’, commit 1756ac8c) says no bump. |
| `mb-dbue` | Optional cleanup of local PR-sizing shortcut copies | description, parent → mb-ge1b | #219 merged 2026-10-26 (gh pr view 219) and added the forks under .tbd/doc-forks/base/shortcut/ and docs/tbd/shortcuts/. tbd v0.10.0 (2026-10-02) and v0.11.0 (2026-11-09) were released after upstream tbd #316 merged (2026-09-20), so the comparison the notes wait for is now possible. |
| `mb-dc51` | Coordinate duplicate missing GitHub CLI notices across Pulls and PR detail | parent → mb-8rpp | Still valid (inferred from code; not reproduced): the Pulls panel and PR page each render their own install action, src/metabrowser/builtin_plugins/github/pulls-panel.js:3813 and pull-page.js:4554 (plus pull-files-view.js:397), with no shared coordination. |
| `mb-djo1` | Re-measure the 220 KB eager-script validation on a quiet host for the careful 1.1x | parent → mb-ww58 | Still open: explorations/performance-loop/performance-budgets.toml:239-242 startup_script_transfer_kb maximum = 220; explorations/performance-loop/tier-probe.mjs:878-883 pools on {page, network, cpu, warm} only, no Chrome version. |
| `mb-dwo6` | Surface and retry a failed filesystem watch | parent → mb-8127, spec → plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md | Still unbuilt. |
| `mb-e22r` | Wiki resolver suffix-query keys can exceed the content-hash bound | parent → mb-u3pb | Still as described: src/metabrowser/builtin_plugins/markdown/wiki-resolver.js:229-231 suffixQueries/suffixSummaries; :573-578 keyed on plan.lookup; :8 MAX_NORMALIZED_TARGET_LENGTH = MAX_AUTHORED_TARGET_LENGTH * 3 + 3 versus :17 MAX_MEMO_KEY_LENGTH = 16_383. |
| `mb-e9fm` | Developer ID signing, notarization, a DMG, and a Homebrew cask | status → open, description | The pipeline is on main since #341: apps/macos/scripts/release.sh, notarize.sh:25-26 (tri-state NOTARIZE), :68-79 (notarytool --wait --output-format json, saved log, staple, validate), make-dmg.sh, check-dmg.sh, packaging/metabrowser-app.rb.template; publish.yml:12-16 runs only on v tags. apps/macos/README.md:1287 and :1292 say no Developer ID build has been notarized and no release job exists. |
| `mb-e9vy` | Add diagram copy button and visible Mermaid parse-error state | description | Description is null; scope is Mermaid plan Phase 2 items 2-4. |
| `mb-ed9h` | #101 R3.6: provider-internal modules live outside providers/ | parent → mb-8127 | src/metabrowser/walker.py and src/metabrowser/watch_backends.py are still top-level and import the contract (walker.py:40, watch_backends.py:53); providers/ holds only python_inventory.py; tests/test_inventory_provider_ownership.py exists. |
| `mb-egnj` | Carry changed_files in the pull record, so a filling file list says N of M | parent → mb-8rpp, description | Still not done: src/metabrowser/builtin_plugins/github/pull_record.py:55 PULL_RECORD_SCHEMA = 2 and no changed_files anywhere in builtin_plugins/github (grep -i changedFiles/changed_files finds none outside comments); pull-files-tree.js:470 describeFileList says ‘N files so far, P of L pages’ and :234 initialExpansion estimates from last_page * 100. |
| `mb-etqi` | Complete human release sign-off: browser matrix, private auth and external plugin | parent → mb-425f | It is the general 0.12 human release sign-off the owner deferred (browser matrix, private auth, external plugin), one of the deferred QA beads mb-4bd2 named; mb-425f holds the other four. |
| `mb-f42e` | Expose scan progress and recent directories | title, description | Scan progress shipped: /api/index/progress reports status, indexed_files, max_files, truncated, complete, active (src/metabrowser/events_route.py:959; tests/golden/cli-api-shell.tryscript.md:286-298), and TODO.md:19 records scan status as implemented. |
| `mb-ffo9` | Ratchet legacy browser JavaScript to noImplicitAny | description | Work still open: tsconfig.legacy.json files lists 10 JavaScript modules (static/app.js, charts.js, icons.js, perf.js, plugin-sdk.js; agent_log/index.js, markdown/index.js, structured/index.js, preview.js, tree.js), now 13,683 lines against the description’s 7,124. docs/development.md:814-820 says the files array is the allowlist, to read it there rather than from a count, and gives the command for remaining diagnostics. |
| `mb-fhfh` | H19: reproduce or retire the 3,669 ms /api/events stall | parent → mb-ww58, spec → plan-2026-08-21-load-time-performance.md | Open in the load-time plan (H19 row: ‘Open (mb-fhfh), needs reproduction before any change’). |
| `mb-fzm7` | Call kpressInitDiagrams from the Markdown rendered view with disposal | description | Description is null. rendered.js:119 disposeToc and :232 mb.kpressInitToc(container) are the integration point. |
| `mb-ge1b` | [epic] Minor cleanups for the next minor release | title, description | Its stated batch shipped: #50 (branch claude/minor-cleanups) merged 2026-08-16 (merged-prs.tsv) and released in v0.5.0 (CHANGELOG.md ‘## 0.5.0’). 12 of 14 children are closed. |
| `mb-gluj` | #3 review D: add a strict Content Security Policy | title, description | Partly done and the stated blocker is gone. src/metabrowser/capabilities.py:150-186 untrusted_shell_csp ('the shell’s inline scripts only by nonce; no inline handler runs'), applied in src/metabrowser/server.py:2168-2181 only when active content is off; added by 386e3bb09 (2026-09-24, ‘a Content-Security-Policy for the page under the untrusted profile’), in v0.12.0 and its CHANGELOG breaking note (CHANGELOG.md 0.12.0 section). |
| `mb-gqci` | Push aggregate deltas over SSE instead of client rollup polling | status → deferred | Labelled ‘deferred’ and its description ends ‘RECOMMENDATION: defer’, but the status is open. |
| `mb-gs41` | Flaky: tests/test_transitions_instrument.py Chrome recorder on CI | description, parent → mb-1qsn | Half fixed. |
| `mb-gvtw` | Run and record the WebKit measurement gate in the app | status → open | The run-and-record part is on main: #363 merged 2026-11-13 (8f447c61); docs/large-content-rendering.md:501 ‘Measured in WebKit’ has the method and results, and :705-709 ends 'The choice is the owner’s, and this gate leaves it open.' The bead’s note: ‘Left open until the user decides.’ Since then mb-551q merged (#367) and mb-dl7d records the remaining 2.25-2.46x; the rerun is mb-76nv. |
| `mb-gwlw` | Provider contract returns browser wire models for rollup and navigation | description, P2, parent → mb-8127 | Still valid: src/metabrowser/inventory_engine/contract.py:95 imports NavigationTallies and RollupResult from metabrowser.wire_models; contract.py:1237-1239 RollupProjection.payload: RollupResult \| None; contract.py:1246-1248 NavigationProjection.payload: NavigationTallies; wire_models.py:246 mtime: NotRequired[float], :249 children: list[Any] \| None, :253 ExtensionTallyRow unused, :261-265 tally rows list[list[object]]. |
| `mb-gy9b` | Diff: one tree materializer, batched blob reads | status → open, parent → mb-ypme, title, description | The shared-parser half landed in #276 (b73f5a62, 2026-11-01): cli/diff_cli._materialize (src/metabrowser/cli/diff_cli.py:189-203) and tests/diff_fixture_repo.materialize_tree (:96-110) both use git/tree_source.iter_ls_tree_records. |
| `mb-h31g` | Plan a standard browser contributor toolchain migration | P2, parent → mb-0b2h | P1 since 2026-07-18, last touched 2026-08-27, nothing depends on it. |
| `mb-h6qz` | gh runner: huge Retry-After values and deeply nested bodies raise past the typed failures | title, description | Half fixed. b416cb7c ‘fix(github): an absurd rate-limit header is a limit with no time, not an exception’ (2026-11-02, reached main 2026-11-04 via da87bb13, in v0.12.0): builtin_plugins/github/gh.py:393-401 rate_limit_reset catches OverflowError/ValueError/OSError and answers ‘unknown’. |
| `mb-hhmb` | Diff P2: intraline, context expansion, whitespace, and virtualization | title, description | Intraline is done: builtin_plugins/diff/diff-intraline.js; spec Phase 4 checklist all [x]; #81 (merged to main 2026-08-26). |
| `mb-hmwo` | Ratchet remaining Python strict-type debt | description | Work still open: pyproject.toml:201 typeCheckingMode = “strict” with scoped executionEnvironments at :206-214 for src (reportPrivateUsage, reportUnknownArgumentType, reportUnknownMemberType, reportUnknownVariableType, reportUnusedFunction off) and tests. |
| `mb-hr37` | Content typing: record sniff results during the inventory crawl | P3 | Accurate: FileContext still takes content_class= and lazily calls sniff_artifact (src/metabrowser/file_kinds.py:133-168). |
| `mb-i5i4` | Diff view: mark file as viewed | parent → mb-ypme, description | No viewed state in builtin_plugins/diff or github (grep -i viewed finds only an unrelated note_viewed prefetch hint). |
| `mb-i9ll` | Walk the owner through reviewing real PRs and record what they find | −release:v0.12.0 | Open, P1, last note 2026-11-03; nothing depends on it. |
| `mb-inad` | Agent-edit adapter: SEARCH/REPLACE and V4A blocks into v1 documents | parent → mb-ypme, P3 | Not started: src/metabrowser/diff/adapters/ holds only base.py, git.py, patch_file.py. |
| `mb-itzy` | Design a Files workflow for working trees and cached branch snapshots | spec → none | Still valid and paused by the user (docs/project/qa/qa-2026-11-07-v012-release-preparation.md:390: ‘future workflow mb-itzy, explicitly paused by the user’). |
| `mb-iyu7` | #101 R3.5: metab --walk bypasses the coordinator in both modes | description, parent → mb-8127 | The description’s walk.py:401 claim is fixed: build_tree_envelope uses InventoryRuntime(provider=inventory_provider_from_environment(), ...) at src/metabrowser/walk.py:411, as the 2026-09-08 note says. |
| `mb-jt6l` | Dismiss the narrow Markdown Contents drawer with Escape | +markdown, description | Still valid: src/metabrowser/builtin_plugins/markdown/inert-toc.js registers no keydown listener; KPress 0.3.5’s toc.js (.venv/lib/python3.14/site-packages/kpress/format/static/js/toc.js) has no Escape handling either; docs/e2e-testing.md:466 expects ‘dismiss it with Escape’. |
| `mb-jwfx` | Re-run large-PR wall-clock claims on a quiet machine | −release:v0.12.0 | Open; the quiet re-run has not happened (no experiment for the #29817/#29121 cases after exp-041). 0.12.0 shipped 2026-11-09 without it, so release:v0.12.0 no longer fits. |
| `mb-k0x3` | Diff P3: multi-file review surface and renderer library decision gate | description | Multi-file surface exists: Commits-tab comparison and PR Changes mount one diff view with sticky file bars (builtin_plugins/diff/styles.css:61-63), deferred per-file hydration (diff-view.js deferredPath), go to a file by path (c709213c, #284 via #283). |
| `mb-k7zy` | Repository library and hosted-review roadmap | description, P2 | Description describes the pre-thin-mirror v0.12 slice (provider mirror, hosted-review records, gh api acquisition), which the thin-mirror plan replaced (epic mb-hall; #228 Simplify, #246 removed hosted-review code); v0.12.0 tagged 2026-11-08. |
| `mb-k8os` | Markdown: deferred review findings (transclusion deadline, task-box pairing, truncated catalog, worker reuse, real-browser coverage) | title, description | Four of the six findings in the title were fixed by #114 (merged 2026-09-14), as the bead’s own notes say: per-claim transclusion clock (src/metabrowser/builtin_plugins/markdown/transclusion.js:12-16), shared Worker (markdown-worker-client.js:15-36). |
| `mb-kccm` | Transient JS heap is 2.5-3.2x v0.9.1 on a repository-shaped tree | parent → mb-ww58 | exp-034 (experiments/exp-034-v0100-quiet-machine-rejects-the-candidate-on-300k.md:330-336) explains the heap by the 4,096-item delivery batch bound and tracks it as mb-kccm; explorations/performance-loop/run.py:259 still reports inventory_delivery_batch_items_max. |
| `mb-kicj` | Residual: inventory walk still 28% slower than main after the perf fixes | description, parent → mb-odrb | Still valid: the double representation remains on main (python_inventory.py:515 _internal_entry converts InventoryEntry to FsEntry; dataclasses.replace on walker and aggregate paths at python_inventory.py:3363, 3621, 3854). |
| `mb-l2eh` | #101 R3.4: change batches are invalidation-only, so the host re-buys facts | parent → mb-8127 | ChangeBatch still carries only dirty paths, non-file paths, dirty queries, all_dirty, reset, and work, with no facts field (src/metabrowser/inventory_engine/contract.py:1422-1434); Python provider mutations still dirty DIAGNOSTICS (providers/python_inventory.py:858, :3486, :4080). |
| `mb-lv46` | Serving waits for watcher registration, so the socket opens late on a deep tree | description, parent → mb-ww58 | Still valid on main: src/metabrowser/events_route.py:199-201 the lifespan awaits runtime.open(root) before yield; inventory_engine/providers/python_inventory.py:4137-4140 open() starts the watcher and awaits wait_until_watcher_started(). |
| `mb-m20f` | Execute the full v0.12 QA runbook on a pinned post-landing candidate | status → open, title, description | Claim not live: started 2026-11-08T03:02, last update 2026-11-09T01:24; no commit on origin/main since 2026-11-05 names it (`git log origin/main --since=2026-11-05 --grep=mb-m20f` is empty). |
| `mb-m4u9` | #277 B2: duplicate attributes: the server keeps the last, a browser keeps the first | parent → none, +security, description | Still valid: src/metabrowser/inert_html.py:440 values = dict(attrs) (the description cites line 421 at c934a0b4); tests/test_inert_html.py has no duplicate-attribute case (grep ‘duplicate’ finds none). |
| `mb-migx` | Measure walk throughput and find where the ~50 us per file goes | description | Description is empty. |
| `mb-mjc0` | H89 follow-up: parallel loading with a preload cap or low fetch priority | description | Three stale facts. |
| `mb-mpm3` | App icon: an MB mark in the sister app’s style | title, description, status → open, P3 | The icon merged in #341: apps/macos/AppIcon/ (masters, parameter files, make-glyphs.swift), apps/macos/Resources/AppIcon.icns and AppIcon-Dev.icns, apps/macos/scripts/build-icon.sh; chosen design sym-drop19-gap34 (commit 1721e583, on main). apps/macos/AppIcon/README.md:3-5: ‘Hand-tuned small sizes (16 and 32 px) still wait on review.’ That is the only remaining item (bead notes, 2026-11-11). in_progress since 2026-11-11T03:18Z with no update since 2026-11-11T20:26Z, while the same session shipped other app work through 2026-11-13. |
| `mb-mw0t` | Invisible-character and PR-header follow-ups from the #244 review | parent → mb-k7zy | Still open: no dedicated invisible_chars test file; the dead base.isspace() term is now src/metabrowser/invisible_chars.py:166 (cited as :92); ‘deleted fork’ wording at src/metabrowser/builtin_plugins/github/pull-page.js:489 and pulls-panel.js:252. |
| `mb-nbc6` | H18: batch walker entry emission per directory instead of per file | parent → mb-ww58, spec → plan-2026-08-21-load-time-performance.md | Still open in code: walk_tree still yields one entry at a time (src/metabrowser/walker.py:381-506). |
| `mb-nbvk` | H40: native parallel walker over ripgrep’s ignore crate | parent → mb-ww58, spec → plan-2026-08-21-load-time-performance.md, description | Open in the plan’s H40 row ('Large, and blocked behind H39'). |
| `mb-nebu` | PR page: kept conversation sections keyed by digest alone, and first-paint span modes | title, description | The description inverts review B6 of #369. |
| `mb-npkt` | Implement the reserved *mb* query namespace in the URL codec | description, P3 | Still unimplemented: no *mb* handling in src/ (grep); tests/golden/cli-ui-navigation.tryscript.md:645 ‘reserved keys are carried, not yet interpreted’. |
| `mb-nqgs` | Add a provider conformance case for aggregate payload shape | title, description, parent → mb-8127 | Partly stale: test_provider_semantic_digest is a registered, factory-parametrized conformance case (tests/test_inventory_provider_contract.py:107-113, :1046) and already asserts the rollup payload’s keys and runs validate_rollup_result (lines 1131-1137; added in fdb69a0a). |
| `mb-nu1s` | Zoom: re-root the nav tree at any container | spec → arch-nav-containers.md | Still future work per docs/project/architecture/arch-nav-containers.md:153-158 ('This is future work'). |
| `mb-obm2` | Flaky: gh_account stopped-while-asking test sees the 15 s timeout instead of SIGKILL | parent → mb-1qsn | Still as described: tests/test_github_pulls.py:1838 expects ‘gh exited -9’ inside test_gh_runs_in_a_group_the_stop_path_can_kill (line 1811), against gh’s own answer deadline (src/metabrowser/builtin_plugins/github/gh.py:295 ‘gh did not answer within … s’). |
| `mb-od5n` | H41: columnar index representation to make the tally pass vectorized | parent → mb-ww58, spec → plan-2026-08-21-load-time-performance.md, description | Open in the plan’s H41 row ('The heavier alternative to H34'). |
| `mb-odrb` | [epic] v0.10.1: pay down the flat-tree delivery cost | title, spec → plan-2026-09-15-flat-tree-delivery-cost.md, −release, description | No v0.10.1 tag: `git tag` lists v0.10.0, v0.11.0, v0.12.0. docs/project/specs/active/plan-2026-09-15-flat-tree-delivery-cost.md:1-8 is this epic’s plan (names mb-qvw4, mb-qtgj, mb-zc3p at :32-34, mb-nuhb at :83, mb-ma3x at :131) and :146-150 says tier 1 ‘was planned for 0.10.1 and in the event ships with 0.11.0’ via #129; CHANGELOG.md:2239 (0.11.0) ‘At 300,000 rows the step drops from 62 ms to 41 ms’; src/metabrowser/settings.py:123 INVENTORY_WALKER_EMIT_BATCH = 256 (mb-nuhb not taken). |
| `mb-ojvf` | Menu and overlay primitives: anchored placement, action menu, action registry, inline edit | description | Modal half done: src/metabrowser/static/overlay-layer.js createModal (commit bd50b30d, #35, 8c52e582), used by search-palette.js:96 and keyboard-help.js:300. |
| `mb-pn95` | Watcher can silently miss kernel event-queue overflow (watchfiles drops notify’s Rescan flag) | parent → mb-8127, spec → plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md | watchfiles is still 1.2.0 (uv.lock:1136-1137), and run_watcher has no rescan handling (src/metabrowser/watch_backends.py:320-420). |
| `mb-q1wo` | Remove scoped Biome legacy rule exceptions | description | Work still open: biome.json overrides keep noDescendingSpecificity off for src/metabrowser/static/styles.css and noInnerDeclarations off for static/app.js, charts.js, perf.js and builtin_plugins/structured/preview.js and tree.js. |
| `mb-qdr1` | Validate every golden envelope against its generated schema | title, description | The spec’s Phase 2 scopes this to the Git transcripts (cli-api-git.tryscript.md) against the strict variant, names the normalization problem, and stops the plan if validation cannot be made to work; the bead says ‘every golden’ and omits both. tests/golden/cli-api-git.tryscript.md exists. |
| `mb-qlsx` | Quick file finder and search providers | description | Description says Phase 2 is ‘complete server filename fallback over InventoryIndex’: Phase 2 was redefined as the client-complete catalog (mb-ci04, closed), and InventoryIndex no longer exists in src/metabrowser. |
| `mb-qz51` | Render Mermaid diagrams in rendered Markdown, GitHub-equivalent or better | description | Not started: no mermaid in src/, package.json, NOTICE.md, static/vendor (grep); only plan/research merged (#63). |
| `mb-qzny` | Host mode: ready line after bind, sticky port, stdin token, stdin-EOF exit, idle exit | title, description | The stdin-EOF exit already landed: #366 ‘feat(cli): metab --exit-on-eof stops serving when stdin closes’ merged 2026-11-13 (617a94a9); src/metabrowser/cli/stdin_lifeline.py:1, src/metabrowser/cli/main.py:654, golden tests/golden/cli-serve-exit-on-eof.tryscript.md, tests/test_stdin_lifeline.py; the app passes it to every server (apps/macos/README.md, After a Crash). |
| `mb-r4bm` | Reduce whole-tree /api/tree cost: 4,990 ms and 3.68 MB at 1M files | description | Description is empty. |
| `mb-rldc` | Hosted review Phase 4: anchored review threads over comparisons | title, description, P3 | User’s 2026-09-23 decisions defer ‘inline thread anchoring’ (docs/project/specs/done/plan-2026-09-23-v012-thin-mirror.md, Decisions). |
| `mb-rtgh` | App: metabrowser:// scheme, rendezvous handler, and attach | description | Not started: no CFBundleURLTypes in apps/macos/Resources/Info.plist (grep), and apps/macos/README.md:9-25 says the app has no URL scheme. |
| `mb-s0e4` | Transition recorder can place the input’s own frame before the input | parent → mb-mpo0 | Still open and documented as a limit: explorations/performance-loop/README.md:1014-1019 (frames placed by rAF begin time, which Chrome can set before the input’s timeStamp; such a transition reads framesToReady 0). accountFrames/regionMovement at explorations/performance-loop/transitions-recorder.mjs:1215, 1326 are unchanged in that respect. |
| `mb-s4y1` | Native app v1: a usable app that meets the tbd coding guidelines | description | Description says the milestone lives on claude/macos-app-spike and merges only when the user says; the whole stack merged to main on 2026-11-13 (#341, #359, #361, #362, #363, #377; gh pr view). |
| `mb-s8zj` | Segment-trie catalog index for subtree removal (deferred) | parent → mb-qlsx, status → deferred | No parent, but its spec is the file-search plan, whose feature bead is mb-qlsx (Phase 2.1, ‘Deferred behind the measurement checkbox above’, now with this bead’s id). |
| `mb-squq` | H47: the 64-worker executor is sized for I/O waiters, not CPU-bound offloads | parent → mb-ww58, spec → plan-2026-08-21-load-time-performance.md, description | Open in the plan’s H47 row. |
| `mb-t8py` | Generate JSON Schema for the Git envelopes, with a drift check | description | Description cites ‘31 TypedDicts’ (now 35 across the two files) and frames strictness as one choice, while the spec’s ‘Two strictness choices, not one’ section requires a permissive served schema and a strict golden-validation variant. |
| `mb-tcub` | Remote mode’s --ssh-options passes raw SSH flags, so metab cannot be blanket-exempted from an agent sandbox | parent → mb-1apq, +security | Still valid (read, not executed): src/metabrowser/cli/main.py:757-759 --ssh-options; src/metabrowser/cli/ssh_utils.py:72-73 and :111-112 cmd += shlex.split(ssh_options). |
| `mb-tdk6` | Submodules end-to-end: fixture, adapter, apply semantics, corpus | parent → mb-ypme | Partly covered since 2026-08-19. tests/diff_view_file_fixture.py:10 builds a submodule move for the View file golden, and builtin_plugins/diff/diff-view-file.js:20 leaves a submodule side out of View file. |
| `mb-udtl` | Review #338 research corrections and standing-policy readiness | status → open | A1 and A2 are delivered: #342 ‘docs: clarify native research authentication and acceptance’ merged 2026-11-08 (merged-prs.tsv), as the bead’s notes record. |
| `mb-uem0` | fdu: read File Rollup registry schema 5 (chroma_ratio) after #404 | +upstream | Still open: this repository is at schema 5 (src/metabrowser/data/file-rollup-format/recommended-file-types.toml:28 schema_version = 5, :95 chroma_ratio). |
| `mb-unt6` | H56: first_row_ms rewards painting something early and is indifferent to what follows | description | The description’s last line ('Blocked in practice by H51') is stale: mb-qf2p (H51) closed 2026-08-24 with visible LCP and CLS in exp-014. |
| `mb-v30u` | Execute terminal tree reconciliation DOM contract | parent → mb-43f0 | Still valid: reconcileMountedTree is defined at src/metabrowser/static/app.js:1478; the only coverage is the source-string check tests/test_initial_tree_inline.py:95 (assert “reconcileMountedTree(data.tree” in load_tree) and a stub in tests/dom/page-reconnect-behavior.js:196. |
| `mb-v6rw` | Decide: combined (merge) diff representation | parent → mb-ypme | Still undecided: the parser marks combined input unsupported (src/metabrowser/diff/adapters/patch_file.py:258-263, :344-345). diff-sources-and-anchoring.md records first-parent for history (:35) but no decision on N-parent diffs. |
| `mb-vbnn` | A mirror location under home has an unexpanded tilde that breaks a quoted git -C | −release:v0.12.0 | Still undecided; /api/source/status still reports location with ~ by design (src/metabrowser/source_routes.py:102-110). |
| `mb-vif4` | #59 review R4: tbd npx fallback fails for 14 days after every tbd release | parent → none | Still true: .claude/scripts/tbd-session.sh:67 and .claude/hooks/tbd-closing-reminder.sh:45 run ‘npx --yes get-tbd@<fallback>’ without --min-release-age=0, while .npmrc sets min-release-age=14. |
| `mb-vknc` | #101 R4: host-side debts behind the inventory boundary | description, parent → mb-8127 | Item (a) in the description was fixed in the #101 final review, per the bead’s own note; (b) to (e) remain: reconnects start from a snapshot (src/metabrowser/events_route.py:714-716), the UNKNOWN-path loop sleeps 5 ms and retries (src/metabrowser/server.py:2384-2396), and the coordinator history is a deque of change_queue_size. |
| `mb-w2f3` | H43: viewport-first walk ordering so the visible subtree settles first | parent → mb-ww58, spec → plan-2026-08-21-load-time-performance.md, description | Open in the plan’s H43 row ('Composes with H33'). walker.py has no viewport or priority ordering. |
| `mb-w3va` | H54: the tally row’s reservation cannot cover a row that wraps | parent → mb-ww58, spec → plan-2026-08-21-load-time-performance.md | Still open in code. |
| `mb-w4kd` | Native shell: one host spelling and a persistent data store with the sticky port | title, description | Description says ‘Deferred: apps/macos stays unmerged’; apps/macos is on main through #341 (merged 2026-11-13, 2e569c25). |
| `mb-w5rc` | Share the diff plugin’s kept manifest with the changed-files list | parent → mb-8rpp, description | Half done: the accessor the description asks the diff owner for now exists. src/metabrowser/builtin_plugins/diff/sidekick.py:117 shared_comparison_manifest reads through _COMPARISONS; github/pull_manifest.py:253 shared_pull_manifest wraps it with comparison_cache_key and an on-disk manifest bank (commit 7b5d27ad5 in #348, merged 2026-11-11), used by pull_rendered_diff.py:227 and the comparison route’s manifest_loader (github/sidekick.py:332). |
| `mb-weez` | Tooling tests and explorations: drop live-repo re-runs of lint, table-drive gate tests, and mark the superseded repository-cache measurements | −release:v0.12.0 | Steps 4 and 5, the reason for the release label, missed 0.12.0: explorations/repository-cache/README.md:3 still reads ‘Accepted on 2026-09-16 as the measured basis’; pyproject.toml [tool.hatch.build] exclude (lines 108-125) and devtools/check_distribution.py:16-30 still do not name explorations/. explorations/fdu-inventory-adapter/evidence.json still has 3 codex/worktrees paths. |
| `mb-wpqq` | Catalog sort and Recent pass hold the GIL without cooperative yields during a walk | title, description | The bead’s own notes say parts 1 (sort key, rejected) and 2 (content hash, #129) are settled and only the Recent pass remains. _recent_projection (src/metabrowser/inventory_engine/providers/python_inventory.py:2320-2370) still filters and sorts every entry with no cooperative yield. |
| `mb-x0sv` | Expose a public KPress API for per-block token maps and rendering | parent → mb-2iok, +kpress, +upstream | Still valid: src/metabrowser/diff/markdown_projection.py:39-41 import _mark_standalone_image_figures, _markdown_it, _postprocess_html from kpress; :130 and :531 use them; guard test tests/test_markdown_diff_projection.py:652; pin kpress==0.3.5 (pyproject.toml:46). |
| `mb-xl14` | Remove the unreachable catalog GitHub-footer projection | parent → mb-8rpp, description | Still valid: src/metabrowser/builtin_plugins/github/pulls-panel.js:409 initializes github: null in describePulls and nothing assigns model.github (grep: only :220 typedef, :409, :3828, :3831); the ‘See the rest on GitHub’ branch at :3828-3832 is unreachable; tests/dom/github-pulls-panel-session.js:84 copies model.github. |
| `mb-xm9c` | Cover Mermaid lazy mount, replacement, disposal, and theme change in tests/dom | description | Description is null; scope is the Mermaid plan’s Testing Strategy section. |
| `mb-xzb1` | API envelope contract: a generated schema the CLI can show | description, P2 | The description’s open decision is closed: child mb-d7ne (Decide whether /api/* stays an internal contract) is closed and the spec status says ‘The gating decision is closed: the envelopes stay internal’. |
| `mb-y06t` | Git status goldens: dirty-tree states and honest truncation | spec → plan-2026-08-26-git-status-and-working-tree-diffs.md | Still open and valid: no cli-git-status*.tryscript.md and no /api/git/status route on main; blocked by mb-u4mf. |
| `mb-y7zh` | Load Mermaid lazily and add kpressInitDiagrams to the plugin SDK | description | Stale names: file is static/plugin-sdk.js (5fd1ab42), _loadKpressTocModule at plugin-sdk.js:1137, kpressInitToc at :1304. optional_script_assets (server.py:1821) is now the prefetched tier; the on-demand tier is on_demand_script_bundles (server.py:1831) via static/asset-loader.js, which loads classic scripts only (no module support in asset-loader.js). |
| `mb-ycf2` | H44: measure and engineer the remote-link regime (RTT knob, batched prefetch, zstd) | parent → mb-ww58, spec → plan-2026-08-21-load-time-performance.md, description | Open, P0, in the plan’s H44 row, and last (row 19) in its Next table. |
| `mb-ypme` | General diff rendering: source-agnostic comparison model, renderer, and adapters | description, P2 | Description names a spec that does not exist (plan-2026-07-18-git-diff-view.md); spec_path is plan-2026-08-17-general-diff-rendering.md. |
| `mb-yth5` | Tests leave process-global state changed: reader pools, probe results, ignore cache, catalog revision | title, description, status → open | The resets landed in #276 (merged 2026-11-04), commit 8e56775d: tests/conftest.py:272-286 resets probe._RESULTS, tree._IGNORE_CACHE and events_route._CATALOG_REVISION and states why _POOLS, dotenv._reported and _EXTRA_ALLOWED_HOSTS are left alone. |

## Dependency Changes

Each edge reads “blocker blocks blocked”.

| On bead | Change | Edge |
| --- | --- | --- |
| `mb-2g6f` | removed | mb-2g6f blocks mb-n2ro |
| `mb-2g6f` | removed | mb-2g6f blocks mb-4bd2 |
| `mb-32en` | added | mb-32en blocks mb-mbd3 |
| `mb-34oi` | added | mb-5fp7 blocks mb-34oi |
| `mb-3arq` | removed | mb-3arq blocks mb-wzy6 |
| `mb-56nq` | added | mb-56nq blocks mb-idri |
| `mb-6aa8` | added | mb-6aa8 ↔ mb-jwfx |
| `mb-6d4r` | removed | mb-6d4r blocks mb-3o3h |
| `mb-cf6y` | removed | mb-cf6y blocks mb-n2ro |
| `mb-cf6y` | removed | mb-cf6y blocks mb-4bd2 |
| `mb-etqi` | removed | mb-etqi blocks mb-4bd2 |
| `mb-fzm7` | removed | mb-fzm7 blocks mb-3jt8 |
| `mb-h31g` | added | mb-h31g blocks mb-725d |
| `mb-k0s0` | added | mb-k0s0 ↔ mb-k8os |
| `mb-k7zy` | removed | mb-k7zy ↔ mb-6394 |
| `mb-k7zy` | removed | mb-k7zy ↔ mb-dzib |
| `mb-k7zy` | removed | mb-k7zy ↔ mb-2f7r |
| `mb-kicj` | removed | mb-kicj blocks mb-i57d |
| `mb-npkt` | removed | mb-npkt blocks mb-281d |
| `mb-rldc` | removed | mb-rldc ↔ mb-mx8q |
| `mb-tcub` | added | mb-tcub blocks mb-ko5d |
| `mb-19em` | added | mb-omhf blocks mb-19em |

## Audit Notes Added

These beads kept their fields and got a dated note recording what the audit confirmed or
what moved (line numbers, landed prerequisites, measurements): `mb-06p9`, `mb-06up`,
`mb-097x`, `mb-0cmt`, `mb-0d6a`, `mb-0u3p`, `mb-1jq3`, `mb-1nbg`, `mb-273l`, `mb-2g6f`,
`mb-2iok`, `mb-2wdh`, `mb-2zp3`, `mb-32y6`, `mb-3hwh`, `mb-3s45`, `mb-43f0`, `mb-43v7`,
`mb-479j`, `mb-48vd`, `mb-5no9`, `mb-5rth`, `mb-6aa8`, `mb-6koa`, `mb-6w5n`, `mb-81sr`,
`mb-8k5g`, `mb-8oy4`, `mb-8rpp`, `mb-9n12`, `mb-a9ek`, `mb-aj7y`, `mb-an7c`, `mb-apni`,
`mb-b4j3`, `mb-c7ck`, `mb-cf6y`, `mb-cz5s`, `mb-czrw`, `mb-dqvj`, `mb-dwo6`, `mb-e500`,
`mb-etqi`, `mb-f33i`, `mb-f38n`, `mb-f3mw`, `mb-fbm2`, `mb-fkt5`, `mb-fvs1`, `mb-ge1b`,
`mb-gluj`, `mb-i9ll`, `mb-jalf`, `mb-jt6l`, `mb-jybd`, `mb-k0s0`, `mb-k7zy`, `mb-k8os`,
`mb-kp6c`, `mb-m1mw`, `mb-m20f`, `mb-m4u9`, `mb-mpo0`, `mb-mw0t`, `mb-n43q`, `mb-n50b`,
`mb-n5r6`, `mb-n9xg`, `mb-nbc6`, `mb-odrb`, `mb-ot8o`, `mb-pk2l`, `mb-rldc`, `mb-s5ay`,
`mb-tdk6`, `mb-th8a`, `mb-toru`, `mb-touu`, `mb-u3pb`, `mb-u4mf`, `mb-udtl`, `mb-uem0`,
`mb-vibn`, `mb-wcb0`, `mb-weez`, `mb-wgka`, `mb-wnrv`, `mb-x0sv`, `mb-xfqb`, `mb-y3uh`,
`mb-y4do`, `mb-ycf2`.

## Held for the Owner

None of these was applied; each needs a product or policy decision.

- **Policy grant (`mb-udtl`).** #338 added `subagents: granted` to the policy grants in
  `AGENTS.md` without the owner’s by-name confirmation, and it is in effect on `main`:
  confirm it or revert it.
- **Deferred 0.12 checks.** The owner deferred `mb-2g6f` (with `mb-cz5s`), `mb-8pyc`,
  `mb-cf6y`, `mb-m20f`, and `mb-etqi` at the release: run them against 0.12.x, or close
  them.
- **Performance campaign Phases 2 and 3.** exp-079 closed the campaign summary `mb-ep8a`
  after Phase 1. Fourteen beads that nobody has run yet still block it (`mb-mbd3`,
  `mb-16d7`, `mb-fejb`, `mb-88mp`, `mb-a1nu`, `mb-touu`, `mb-d1uo`, `mb-1bh1`,
  `mb-jak8`, `mb-y04k`, `mb-4ufj`, `mb-e500`, `mb-b7ru`, `mb-yyja`): continue the phases
  with a new closing round and retarget the edges, or park them and remove the edges.
- **Hosted roadmap.** GitHub releases (`mb-7srn`), issues (`mb-9rrc`), and GitLab
  (`mb-51uj`): keep each as a deferred bead to re-plan on the thin mirror, or drop it.
  The releases plan’s R0–R4 beads were closed either way; they build on code #246
  removed.
- **Idle priorities.** The load-time P0s (`mb-ww58`, `mb-jalf`, `mb-6yh2`, `mb-8yqt`,
  `mb-ycf2`, `mb-609b`), untouched since August, and the P1 Git-status (`mb-097x`,
  `mb-r5gn`, `mb-u4mf`, `mb-vibn`), Mermaid (`mb-qz51`), modal (`mb-ojvf`), and fdu
  provider (`mb-hej8`) beads: keep or demote.
- **Native app.** After the WebKit rerun (`mb-76nv`), keep the WKWebView app or take the
  Electron fallback (`mb-gvtw`); and whether the app trusts executables the admin group
  can change, such as a standard Homebrew prefix (`mb-6d4r`).
- **Unpushed local branches (`mb-cds1`).** Two local branches, named in the bead, have
  commits their remotes lack: push or drop them.
- **Smaller questions.** Whether the owner’s own pass over real pull requests is still a
  task (`mb-i9ll`); whether to commit the landing-gate harnesses for the next release
  (`mb-b4j3`); keep or drop the deferred server filename search (`mb-3arq`) and SSE
  aggregate deltas (`mb-gqci`); whether an explicit-path wiki link the truncated index
  lacks navigates anyway (`mb-fvs1`); and what Commits shows under Changes on a pinned
  revision, which has no working tree (Git-status plan).

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
