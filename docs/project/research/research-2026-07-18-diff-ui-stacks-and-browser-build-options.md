# Research: Diff Interface Stacks and Browser Build and Packaging Options

**Date:** 2026-07-18 (last updated 2026-07-18)

**Author:** Metabrowser maintainers with LLM research assistance

**Status:** Complete

## Overview

Two questions motivated this brief.
First, what do the fast diff interfaces people actually use — VS Code, Cursor, the
Claude apps, Graphite, and the current generation of agent-review tools — ship under the
hood, and which of those stacks are reusable leads for Metabrowser’s
[Git diff view plan](../specs/active/plan-2026-07-18-git-diff-view.md)?
Second, if Metabrowser adopts TypeScript and ES modules for its own browser code, or
needs to consume ESM-only libraries, what are the packaging and build options that
respect the repository’s supply-chain policy, and what testing scaffold would make a
large browser-shell rewrite safe?
The
[diff viewer architecture brief](research-2026-07-17-web-diff-viewer-architecture.md)
remains the rationale for the diff data model; this brief covers implementation stacks,
build tooling, and rewrite testability.

A large rewrite is acceptable with agent labor.
The controlling constraints are therefore verifiability — contracts and tests that let a
rewritten shell prove it still behaves like the old one — and contributor scalability:
which toolchain lets people and agents who want to use and improve Metabrowser’s front
end work productively with standard skills.
Supply-chain discipline (lockfiles, cool-off, disabled lifecycle scripts, audits) is a
routine baseline that every finalist toolchain satisfies; it is checked throughout but
it is not an architectural shaping force and does not decide between options.

## Questions to Answer

1. What diff renderers, algorithms, and performance techniques do leading editors,
   review products, and agent tools ship, and which parts are reusable?
2. What build and packaging paths exist for TypeScript and ESM in a repo with no
   bundler, zero runtime npm dependencies, committed vendored assets, disabled npm
   lifecycle scripts, and offline-first serving?
3. What has to be true of the test suite before a browser-shell rewrite is safe to
   attempt?
4. Which toolchain best lets outside contributors and coding agents use and improve
   Metabrowser’s front end at scale, and what do comparable Python-served web
   applications actually use?

## Scope

Included: product and library survey with stack details, bundler and no-bundler
toolchain facts as of mid-2026, import-map and CSP constraints, vendored-artifact
precedents, a verified survey of the front-end toolchains of major Python-served web
applications, supply-chain tooling, and a testability strategy.
Excluded: the diff data model and API (covered by the prior brief) and any decision to
adopt a specific renderer library (owned by the plan’s phase 3 gate).

## Findings: What Fast Diff Interfaces Ship

### VS Code and Its Forks

VS Code’s diff stack is the most instructive verified reference.
The default “advanced” computer uses dynamic-programming diffing for files under about
1,700 combined lines and Myers beyond that, with heuristic post-optimizations and
moved-code detection.
Computation runs in a web worker behind a small URI-plus-version cache, with a
computation timeout that returns partial results.
The single-file widget is two editors aligned by view zones.
The multi-file diff editor virtualizes by viewport and recycles at most five pooled
`DiffEditorWidget` templates positioned with CSS transforms; Copilot Edits reviews ride
on it with per-edit keep/undo.
In 2026 Microsoft also published
[`@vscode/diff`](https://www.npmjs.com/package/@vscode/diff), a standalone MIT,
zero-dependency package exposing the VS Code diff algorithm with JavaScript and
Rust-to-WASM backends (still version 0.0.x). Monaco remains the only production-grade
embeddable descendant of this stack, at roughly five megabytes.

Cursor and Windsurf are VS Code forks.
Cursor’s differentiators are reported to be inline diff overlays patched into the
rendering pipeline, a speculative-decoding “fast apply” path, and Composer’s multi-file
review with a worktree per agent; none of it is reusable.
Cline and Continue, the open VS Code agent extensions, either delegate to the native
`vscode.diff` editor or paint custom inline decorations; both compute diffs with the
`diff` npm package.

### Claude, Zed, and JetBrains

Claude Code’s CLI renders word-level unified diffs in the terminal (reported: Ink,
lazily loaded highlight.js, per-file truncation around 400 lines).
The VS Code extension opens native diff tabs.
The desktop app bundles Monaco’s diff editor and shipped a redesigned diff viewer in its
April 2026 update.
Zed is fully native: GPUI rendering, multibuffers that splice excerpts
of many files into one reviewable surface, split diffs aligned by its block map, and an
agent review pane with per-hunk keep/reject.
Nothing is embeddable, but Zed and Copilot Edits define the interaction bar for agent
review: one surface, all files, per-hunk decisions.
JetBrains renders diffs in its own Swing platform viewer; Junie drives accept/reject
walkthroughs through it.

### Review Products

- **Graphite.** Next.js/React with a custom proprietary renderer and an internal
  `git-diff-parser` package; no public components.
  Graphite was acquired by Cursor in December 2025, which reinforces that agent-era
  review UIs are strategic property.
- **GitButler.** Svelte 5 plus Tauri; table-per-line DOM; three-layer laziness
  (virtualized file list, IntersectionObserver-mounted hunks with reserved heights, then
  progressive `requestAnimationFrame` batches); a 1,000-line “show anyway” gate; Shiki
  with per-line LRU caches; `gix` plus `imara-diff` in Rust behind typed IPC. License is
  FSL-1.1-MIT, so components are readable but not freely reusable for two years per
  release.
- **Sapling ISL.** React 19; custom split/unified table renderer; the server shells out
  to `sl diff` and the client refines intraline spans (capped at 300 characters per
  line) with the `diff` package; TextMate grammars tokenize in a web worker via
  oniguruma WASM; files beyond a 4,000-line cumulative budget start collapsed.
  The `addons/` tree is MIT and its shared diff utilities are the most liftable code in
  this survey.
- **GitLab.** The load-bearing 2025-2026 change: Rapid Diffs abandons client virtual
  scrolling entirely in favor of server-rendered diff HTML streamed over HTTP, custom
  `<diff-file>` web components for lifecycle, and Vue islands only for discussions.
  Diffs and intraline both come from Gitaly (JGit histogram) with Rouge highlighting
  server-side, under hard file and line limits.
- **Gerrit.** Lit 3 web components; `GrDiff` is explicitly built as a reusable
  Apache-2.0 diff component (light-DOM tables so selection works, pluggable annotation
  layers, a pool of three highlight workers) but is not published to npm and is coupled
  to Gerrit’s build.
- **Forgejo/Gitea and Sourcegraph.** Forgejo renders server-side Go templates with
  `sergi/go-diff` intraline; Sourcegraph ships Monaco (0.55) with its own `go-diff`
  parser and a 2026 compare page (file tree, viewed marks, thousands of files).
- **Linear Diffs** (May 2026) shows product direction: a project tracker shipped its own
  proprietary PR review surface with unified/split modes, “structural highlighting” that
  suppresses formatting-only edits, guided review chapters, and live updates while
  agents push changes.

### Local Agent-Review Tools

The niche Metabrowser’s Changes tab addresses is active:

- **difit** 5.0.8 (MIT, ~3k stars): React 19, Vite, Express, the `diff` package, Prism
  highlighting; GitHub-style local review with per-comment “copy prompt” for feeding
  findings back to agents.
- **diffx** (MIT): Shiki-highlighted split/unified local review; inline comments export
  as XML for agents; staged/untracked toggles.
- **diffity** (PolyForm Shield, not OSI-open): agent-integrated review with
  severity-tagged comments and slash-command skills.
- Workspace managers (Conductor, Sculptor, Nimbalyst, Pane, Vibe Kanban) each embed a
  per-worktree diff viewer; none exposes a reusable renderer.
- Aider remains a counterpoint: no viewer at all, just `git diff --color` passthrough
  and git-based undo.
- Lovable’s published postmortem is a useful performance lesson: CodeMirror-based diff
  instances cost 20-50 ms each to mount, and mounting many at once froze the page until
  they time-sliced mounting in small batches.

### Renderer Libraries, Mid-2026 State

| Library | Version | License | Notes |
| --- | --- | --- | --- |
| `@pierre/diffs` | 1.2.12 stable; 1.3.0-beta.11 | Apache-2.0 | `diff` v9 + Shiki; ~152 KB gzip plus multi-MB Shiki languages/themes; vanilla core with React peer for the React entry; dedicated `./worker` entry; ~1.77M weekly downloads |
| `@git-diff-view/core` | 0.1.7 | MIT | highlight.js/lowlight plus `fast-diff`; 4 deps, ~1.4 MB unpacked; React/Vue/Solid/Svelte bindings; bursty maintenance |
| `diff2html` | 3.4.56 | MIT | framework-free HTML-string output; mature maintenance mode; static rather than interactive |
| `@codemirror/merge` | 6.12.2 | MIT | editor-grade, framework-free; repository moved off GitHub to self-hosted Forgejo in April 2026 (supply-chain-relevant) |
| Monaco diff | 0.55.1 | MIT | full IDE semantics at ~5 MB |
| `@vscode/diff` | 0.0.2 | MIT | algorithm only, JS + WASM, zero deps; young |
| `diff` (jsdiff) | 9.x | BSD | the de facto client-side diff algorithm everywhere |

### Recurring Patterns

1. Diff computation is server-side or native nearly everywhere; the client at most
   refines intraline spans under strict caps.
2. Custom renderers converge on a table or grid with one row per line; selection-safe
   DOM beats clever structures.
3. Highlighting is tokenized off the main thread (worker pools in Gerrit and Pierre; ISL
   and GitLab likewise) with per-line caches and hard caps.
4. The trend is laziness over virtualization: progressive mounting and streamed server
   HTML (GitLab), IntersectionObserver mounting (GitButler, ISL), pooled widgets (VS
   Code) — full virtualization is reserved for extreme reviews.
5. Every serious tool gates large diffs behind explicit thresholds (1,000-10,000 lines)
   instead of rendering unconditionally.
6. Agent-review UX converges on one review surface, per-hunk keep/reject, and a
   comment-to-prompt loop back to the agent.

These patterns confirm the choices already recorded in the Git diff view plan
(server-computed patches, manifest-first lazy transport, custom bounded renderer,
enrichment later). GitLab’s Rapid Diffs additionally suggests a credible alternative
projection Metabrowser could add later without changing the wire contract:
server-rendered diff HTML streamed to the client, which fits a Python server well and
echoes the existing KPress server-render path.

## Findings: Build and Packaging Options

### Toolchain Facts (verified against npm and local experiments, July 2026)

| Tool | Version | Packages installed | Lifecycle scripts | Notes |
| --- | --- | --- | --- | --- |
| esbuild | 0.28.1 | 2 | none needed; works under `ignore-scripts` (verified) | single-entry unminified output byte-identical across runs (verified); splitting/minify ordering has known nondeterminism issues; MIT; single maintainer |
| rolldown | 1.2.0 | 4 | none | stable 1.0 May 2026; VoidZero-backed |
| Vite | 8.1.5 | 15 | none | rolldown-based since Vite 8; hard postcss/lightningcss deps; dev server + HMR |
| rollup | 4.62.2 | 3 (+14 with TS plugin) | none | most readable unminified output |
| tsdown | 0.22.9 | 31 | none | library bundler; heavy for this need |
| Bun | 1.3.14 | 0 (own binary) | n/a | second runtime to pin; LGPL-linked JavaScriptCore |
| TypeScript | 7.0.2 | 2 | none | `tsc` is now the Go-native compiler, 8-12x faster; license changed to Apache-2.0; repo currently pins 6.0.3 |

Notable environment shifts: TypeScript 7.0 GA (July 8, 2026) removes the historical “tsc
is too slow” motivation for transpile-only tools, and npm’s `min-release-age` (which
this repo already enforces at 14 days) shipped in npm 11.10.

### The No-Bundler Path and Its One Real Gap

Import maps are Baseline browser features and resolve bare specifiers to local files, so
first-party code can ship as native ES modules with zero build steps beyond what exists
today. Module-count overhead is irrelevant for a localhost tool (about 150-200 ms worst
case for 100-200 modules over HTTP/1.1, per public benchmarks).

The one hard gap: **import maps do not apply inside web workers** (WHATWG HTML issue
#8173, open since 2022, no implementation progress).
ES modules themselves work in workers; only bare-specifier resolution is missing.
Since diff highlighting and tokenization are exactly the code that belongs in workers,
any worker entry that touches third-party code must either use only relative imports or
be shipped as a bundled single-file artifact.

### CSP Compatibility

A strict
`default-src 'none'; script-src 'self'; style-src 'self'; worker-src 'self'; connect-src 'self'; img-src 'self'`
policy is compatible with: esbuild output (no `eval`), module workers from same-origin
files (their imports are governed by `script-src`), same-origin source maps (no CSP
interaction), and Shiki when using its pure-JavaScript regex engine (all 223 bundled
languages supported without WASM, so `wasm-unsafe-eval` is unnecessary).
This aligns with the roadmap’s strict-CSP goal instead of fighting it.

### Vendored-Artifact Precedents

Metabrowser’s `vendor_assets.py` (copy from lockfile-verified `node_modules`, SHA-256
manifest, license capture, size caps, CI check without `node_modules`) is already the
integrity pattern this research sought precedents for.
External prior art: Rails `importmap-rails` downloads and commits per-dependency ESM
files and serves them unbundled; Deno’s `"vendor": true` commits a dependency tree
enforced offline by `--cached-only`; Go commits `vendor/` with a `modules.txt`
consistency check while `go.sum` holds the cryptography; Django and Flask-Admin commit
vendored JS inside the Python package; and rebuild-and-compare CI (as practiced for
committed JavaScript GitHub Actions bundles) is the established way to keep committed
build artifacts honest.
Snowpack and Vite validated bundling each third-party dependency into a single ESM file
while leaving first-party code unbundled, though as ephemeral build caches.
No one has named the full combination (buildless first-party ESM plus esbuild-bundled,
committed, hash-manifested vendor ESM); every ingredient is proven separately.

Concrete sizing: a full Shiki bundle with all languages is about 9.5 MB as one ESM file,
so consuming Shiki or `@pierre/diffs` means selective language subsets or per-language
chunks and a deliberate raise of the vendor size caps (currently 1.7 MB per file, 3 MB
total). `@git-diff-view/core` (highlight.js-based) and reusing the already-vendored
highlight.js stay comfortably inside current caps.

### Supply-Chain Tooling

`npm audit signatures` verifies registry signatures and Sigstore provenance
attestations, with the known limitation that provenance proves build origin, not
maintainer intent (the May 2026 incident of malicious-but-attested packages).
Local-first CI scanners beyond `npm audit`: `audit-ci`, `lockfile-lint`,
`better-npm-audit`; Socket and Snyk CLIs require SaaS backends.
Bundling tools themselves add only 2-4 packages (esbuild, rolldown, rollup) and none
require lifecycle scripts, so the `ignore-scripts` posture holds.

## Findings: Toolchains of Python-Served Web UIs

Metabrowser’s shape — a pip-installed Python server shipping a browser UI — has a
well-populated precedent class.
Verified directly from each repository’s committed package manifests (July 2026):

| Application | UI framework | Build tool | Tests | Notes |
| --- | --- | --- | --- | --- |
| Streamlit | React 18 | Vite 8 | Vitest 4 | TypeScript 6 workspace |
| Gradio | Svelte 5 | Vite 8 (+esbuild utility) | Vitest browser (Playwright) | pnpm workspace |
| Airflow 3 UI | React | Vite 8 | Vitest 4 | TypeScript 6 |
| marimo | React | rolldown-vite | Vitest 3 | Storybook, WASM plugins |
| Home Assistant frontend | Lit | rspack 2 | Vitest 4 | TypeScript 7 native |
| JupyterLab | Lumino/React | own webpack-based builder | jest-era harnesses | oldest of the set |

The convergence is total: every serious Python-served web application ships a full
TypeScript toolchain with a modern bundler (Vite or a Vite-generation Rust bundler) and
Vitest, builds its assets at release time, and packages the built artifacts into the
Python distribution.
None is buildless, and none asks end users to run npm: `pip install` delivers prebuilt
assets, while contributors get a standard front-end workspace.
This is the pattern that has proven to scale contributor communities for exactly
Metabrowser’s architecture, and it cleanly separates two planes that the earlier options
analysis blurred: the **contributor plane** (how people build, run, and test the front
end) and the **distribution plane** (what the wheel ships and how users run it).
The distribution-plane invariants — offline-first, same-origin, no runtime npm, prebuilt
assets in the wheel — are compatible with any contributor-plane choice.

## Findings: Testability for a Rewrite

Current safety net, verified in-repo: Python route/lifespan tests, Node `vm` contract
tests with stubbed browser globals, wheel distribution inspection, vendor manifest
checks — and no real-browser tests of any kind (no Playwright or Puppeteer anywhere).
The shell is one 4,000-line classic script plus window-global helper scripts; only new
modules sit under the fully strict TypeScript gate.

The survey and repo facts imply a clear sequencing rule: **contracts and
characterization tests come before any rewrite, so agents can churn implementation
freely while the suite acts as referee.**

1. **Freeze the contracts.** Golden-snapshot the versioned API payloads the shell
   consumes (`/api/file`, `/api/tree`, `/api/events`, plugin envelopes), and turn the
   documented `window.metabrowser` SDK surface into an executable behavioral suite.
   These already have partial coverage; make them exhaustive and versioned.
2. **Add a real-browser layer first.** A pinned Playwright with bundled Chromium, driven
   from pytest against the real server and the manual corpus, covering navigation, tab
   lifecycle and disposal, live updates, keyboard focus, and both themes — the current
   manual release checklist, automated.
   Visual snapshots (light, dark, narrow) catch what DOM assertions miss.
   This is roadmap item “browser-grade DOM and payload contract coverage” and must
   precede, not follow, the rewrite.
3. **Characterize the old shell.** Where behavior is subtle (tree expansion budgets, SSE
   reconnect, disposal ordering), write tests against the current implementation first
   and require the new one to pass identical tests (contract parity), rather than
   writing aspirational tests for the new code.
4. **Strangler extraction, not big-bang.** Extract ESM modules from `app.js` one seam at
   a time behind the existing window-global facades; every extracted module enters the
   strict tsconfig include list and full Biome rules (the repository’s existing ratchet
   pattern). Old and new paths stay runnable until parity is proven.
5. **Performance budgets as tests.** The perf marks that exist in `perf.js` become
   Playwright-asserted budgets on the fixture corpus so a rewrite cannot silently
   regress first paint or interaction latency.
6. **Artifact honesty.** Any committed bundled vendor file gets the existing manifest
   treatment plus a CI job that rebuilds from the lockfile-verified inputs with the
   pinned tool and fails on any byte difference (feasible: esbuild single-entry
   unminified output verified byte-stable; keep minification off for auditability).
7. **Pilot on new code.** The diff view’s renderer module is new, self-contained, and
   contract-driven — it should be the first strict-TS ESM island and the proving ground
   for this scaffold before the shell migration begins.

## Key Insights

- The industry’s fast diff surfaces validate the existing plan: server-side computation,
  lazy per-file acquisition, bounded custom table rendering, worker highlighting later,
  gating everywhere, virtualization only at extremes.
- Reusable leads are narrower than the product landscape suggests: `@pierre/diffs` and
  `@git-diff-view/core` (as already gated in the plan), `diff2html` and
  `@codemirror/merge` for narrower roles, Sapling’s MIT diff utilities and Gerrit’s
  `GrDiff` as reference code, and the new `@vscode/diff` WASM algorithm as a
  future-watch item. Everything else is locked inside products.
- The deciding axis is contributor scalability, not supply-chain minimalism: every
  finalist toolchain passes the supply-chain baseline (no lifecycle scripts, small
  dependency trees, lockfiles, cool-off support), so hygiene checks are a minor, uniform
  cost rather than a differentiator between options.
- The Python-served web-app ecosystem has converged on one answer to “what scales for
  contributors”: TypeScript, a Vite-generation bundler, and Vitest, with built assets
  shipped in the Python package.
  Nobody in that class is buildless.
- The contributor plane and the distribution plane are separable: a standard dev
  toolchain for the people improving the front end, and an offline-first wheel with
  prebuilt, same-origin assets for the people running it.
  All distribution invariants survive any contributor-plane choice.
- Buildless native ESM remains technically viable (import maps are baseline; strict CSP
  intact; the only hard gaps are worker entry points and ESM-only dependency graphs) —
  but it optimizes for a minimal-toolchain value that the precedent class shows is not
  what makes front ends thrive.
  Its lasting value here is as the low-ceremony migration step for extracting modules
  from `app.js`, and esbuild single-entry vendor bundling (verified byte-deterministic)
  as the mechanism for committed artifacts wherever they are wanted.
- TypeScript 7’s native compiler (8-12x faster) and rolldown-era Vite (15 packages)
  removed the historical costs of the standard toolchain; Home Assistant already ships
  on TypeScript 7 native.
- The rewrite risk is concentrated in test debt, not code volume: the missing layer is
  real-browser coverage, and it is prerequisite work regardless of toolchain.
  Standard runners (Vitest, Playwright) also make that layer something new contributors
  already know how to extend, unlike the bespoke Node `vm` shims.

## Options Considered

The options are evaluated on contributor scalability first: familiarity to front-end
engineers and coding agents, dev-loop speed (edit-to-feedback, HMR), typed authoring in
real `.ts`, standard test runners, access to the ESM-only library ecosystem, the story
for plugin authors, and long-run maintenance.
Distribution invariants (offline-first wheel, same-origin prebuilt assets, no runtime
npm for users) and the supply-chain baseline are requirements every option must meet,
not scoring axes.

### Option A: Stay on Classic Scripts and Single-File Vendor Copies

**Description:** Keep window-global scripts and the current copy-one-file vendoring.

**Pros:**

- Zero new tooling; policy-proven today
- No emit step; wheel ships exactly what is in git

**Cons:**

- Cannot consume ESM-only libraries (Shiki, Pierre, CodeMirror 6)
- Blocks the shell modularization epic; `app.js` keeps growing monolithically
- Worker adoption stays ad hoc
- Alien to incoming front-end contributors: window globals, JSDoc-only typing, and
  bespoke test shims have no ecosystem on-ramp

### Option B: Buildless Native ESM for First-Party Code

**Description:** Split the shell into real ES modules served as-is (strict-checked `.js`
under the existing `tsc --noEmit` gate now; optional `.ts` authoring with native `tsc`
emit as a later ratchet), with an import map for any vendored bare specifiers.

**Pros:**

- No bundler, no emit pipeline, no artifact drift; debuggable served source
- Uses the existing strict TypeScript and Biome ratchets unchanged
- Fully compatible with strict CSP and offline serving

**Cons:**

- Worker entries cannot use import maps (must use relative imports or Option C
  artifacts)
- Import discipline (explicit extensions, no path magic) must be enforced by lint
- Nonstandard as a destination: no `.ts` authoring, no HMR, no Vitest — contributors and
  agents must learn a house style instead of using what they know
- No precedent among comparable Python-served web applications

### Option C: esbuild as a Vendor Compiler Only (Hybrid)

**Description:** Keep Option B for first-party code; for each ESM-only third-party
library and each worker entry, one pinned esbuild invocation produces a single
unminified ESM artifact committed under `static/vendor/` with the existing SHA-256
manifest, license capture, and a CI rebuild-and-byte-compare job.

**Pros:**

- Adds exactly two npm packages, no lifecycle scripts, MIT license
- Extends `vendor_assets.py` rather than replacing the policy
- Unminified deterministic output stays auditable and diffable
- Solves both real gaps (workers, ESM-only graphs) and nothing else

**Cons:**

- Vendor size caps must be raised deliberately for Shiki-class payloads
- Determinism must be re-verified per esbuild upgrade (no upstream guarantee)
- A second build input (bundle config) joins the review surface

### Option D: Standard Toolchain — TypeScript + Vite + Vitest (Contributor Plane)

**Description:** A conventional front-end workspace for Metabrowser’s browser code:
`.ts` sources under strict TypeScript, Vite 8 as dev server (proxying the Python API)
and release bundler, Vitest for unit and component tests, Playwright for end-to-end,
with `vite build` output shipped in the wheel as today’s static assets are.

**Pros:**

- The lingua franca: what front-end engineers and coding agents already know, and what
  every comparable Python-served application (Streamlit, Gradio, Airflow, marimo, Home
  Assistant modulo rspack) converged on
- Real `.ts` authoring, instant HMR for UI work, standard test runners that new
  contributors can extend without learning house mechanisms
- Trivial access to the ESM-only ecosystem and worker bundling; the renderer-library
  gate becomes an ordinary dependency decision
- Enables a typed, published plugin SDK and a plugin project template
- Rolldown-era Vite is lean (15 packages, no lifecycle scripts) and passes the
  supply-chain baseline like every other finalist

**Cons:**

- Served code is build output, so debugging leans on source maps, and the wheel build
  (or a committed-dist flow) gains a Node step
- Hard postcss/lightningcss dependencies and two native-binary families
- A config surface (vite.config, plugins) that can accrete if not curated

### Option E: rspack / Bun / tsdown Variants

**Description:** The same contributor-plane shape as Option D with a different engine.

rspack is proven in this class (Home Assistant) but is webpack-shaped and less common in
new projects than Vite; Bun consolidates package manager, bundler, and test runner into
one binary but adds a second runtime, has partial `node:vm` compatibility for the
existing shims, and buys nothing browser-visible; tsdown targets library bundling, not
applications. All are viable, none beats Vite on the familiarity axis that this
evaluation weights first.

### Eliminated Options

- **webpack:** legacy-generation tooling with eval-based dev defaults; the precedent
  class that used it (JupyterLab) is the oldest member, not the model.
- **CDN or downloaded-at-runtime modules:** violates offline-first and the
  no-external-origins test — a distribution invariant, not a preference.

## Recommended Direction

Optimize for the people who will build on this: adopt the standard toolchain (Option D)
as the contributor plane, while keeping today’s distribution plane intact — an
offline-first wheel of prebuilt, same-origin assets that end users get with
`pip install` and no npm.
This is the shape every comparable Python-served application landed on.

Staged adoption:

1. **Testability first, toolchain-independent.** Land the real-browser Playwright layer,
   payload and SDK contract suites, and perf budgets before any rewrite; then strangle
   `app.js` module by module with contract parity.
   This work transfers unchanged into the new toolchain.
2. **Stand up the front-end workspace with the diff renderer.** The Changes surface is
   the first substantial new UI: author it as `.ts` under strict TypeScript in a Vite
   workspace with Vitest, with `vite dev` proxying `metab serve` for HMR. New code
   proves the toolchain before legacy code migrates into it.
3. **Wire the distribution build.** `vite build` emits the assets the wheel ships
   (either built at release in CI, which already pins Node, or committed with the
   existing manifest-plus-rebuild-diff honesty mechanism — the esbuild determinism
   result generalizes the same gate to any pinned bundler).
   The offline, no-external- origins tests continue to enforce the invariants.
4. **Migrate the shell as the strangler proceeds**, retiring window globals, the
   JSDoc-only typing gate, and the Node `vm` shims in favor of `.ts` modules, Vitest,
   and Playwright as each seam moves.
5. **Grow the plugin ecosystem on top**: publish a typed `window.metabrowser` SDK
   package and a plugin template with the same toolchain, while keeping the zero-build
   plain-JavaScript plugin path as the low-ceremony on-ramp.

Buildless native ESM and the esbuild vendor mode remain useful mechanics inside this
direction — as the low-ceremony extraction format during the strangler phase and as the
committed-artifact mechanism where wanted — but they are stepping stones, not the
destination. The supply-chain baseline (exact pins, lockfiles, `ignore-scripts`,
cool-off, audits) carries over to the new toolchain as routine configuration; it
constrains how tools are installed, not which tools are chosen.
The UI framework question for the review surface (stay vanilla, adopt Lit-style web
components as GitLab and Gerrit did, or accept a framework island with a renderer
library) is deliberately left to the plan’s phase 3 gate, now unblocked by the toolchain
rather than constrained by it.

## Methodology and Evidence Limits

Product claims were verified where possible by cloning sources (VS Code, GitButler,
Sapling, Gerrit, gg, difit), reading official docs and engineering posts (GitLab, Zed,
Linear, Lovable, Graphite), and querying the npm registry; package counts and
esbuild/Shiki behavior were measured locally with `npm install --ignore-scripts` and
repeated builds on Linux x86_64. The Python-served toolchain table was verified from
each project’s committed package manifests fetched from its repository (Streamlit,
Gradio, Airflow, marimo, Home Assistant); JupyterLab’s builder architecture is
characterized from its documentation rather than a manifest hit.
Claude Code CLI internals and Cursor internals come from secondary write-ups and
reverse-engineering notes and are labeled reported, not verified.
Proprietary products (Cursor, Graphite, Linear) disclose no renderer internals; absence
of evidence there is noted rather than filled with inference.
Web-search quota limits in the research environment bounded some follow-up queries;
primary-source fetches and local measurements were unaffected.

## References

### Editors and Products

- [VS Code source](https://github.com/microsoft/vscode) (diff computers, multi-diff
  editor, object pool)
- [`@vscode/diff` package](https://www.npmjs.com/package/@vscode/diff)
- [VS Code: review Copilot edits](https://code.visualstudio.com/docs/copilot/chat/review-code-edits)
- [Zed: split diffs](https://zed.dev/blog/split-diffs)
- [Claude Code VS Code integration](https://code.claude.com/docs/en/vs-code)
- [GitButler source](https://github.com/gitbutlerapp/gitbutler)
- [Sapling ISL source](https://github.com/facebook/sapling)
- [GitLab Rapid Diffs frontend design](https://docs.gitlab.com/development/fe_guide/rapid_diffs/)
- [GitLab diff limits and backend](https://docs.gitlab.com/development/merge_request_concepts/diffs/)
- [Gerrit PolyGerrit source](https://gerrit.googlesource.com/gerrit)
- [Linear Diffs changelog](https://linear.app/changelog/2026-05-27-linear-diffs)
- [Lovable diff viewer performance postmortem](https://lovable.dev/blog/anthropic-sonnet-3-7-lovable-diff-viewer)

### Local Review Tools and Libraries

- [difit](https://github.com/yoshiko-pg/difit)
- [diffx](https://github.com/wong2/diffx)
- [`@pierre/diffs`](https://www.npmjs.com/package/%40pierre/diffs)
- [`@git-diff-view/core`](https://www.npmjs.com/package/%40git-diff-view/core)
- [diff2html](https://github.com/rtfpessoa/diff2html)
- [CodeMirror merge](https://code.haverbeke.berlin/codemirror/merge)

### Build, Packaging, and Platform

- [esbuild API and content types](https://esbuild.github.io/api/)
- [Rolldown 1.0 announcement](https://voidzero.dev/posts/announcing-rolldown-1-0)
- [Vite 8 announcement](https://vite.dev/blog/announcing-vite8)
- [TypeScript 7.0 announcement](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/)
- [Import maps (MDN)](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/script/type/importmap)
- [Import maps in workers, open gap (WHATWG)](https://github.com/whatwg/html/issues/8173)
- [Shiki regex engines](https://shiki.style/guide/regex-engines)
- [CSP `worker-src` (MDN)](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/worker-src)
- [npm `min-release-age`](https://docs.npmjs.com/cli/v11/using-npm/config#min-release-age)
- [Rails importmap-rails](https://github.com/rails/importmap-rails)
- [Go modules vendoring reference](https://go.dev/ref/mod)
- [Deno supply-chain and vendoring](https://docs.deno.com/runtime/packages/supply_chain/)

### Python-Served Web UI Precedents

- [Streamlit frontend](https://github.com/streamlit/streamlit/tree/develop/frontend)
- [Gradio js workspace](https://github.com/gradio-app/gradio)
- [Airflow 3 UI](https://github.com/apache/airflow/tree/main/airflow-core/src/airflow/ui)
- [marimo frontend](https://github.com/marimo-team/marimo/tree/main/frontend)
- [Home Assistant frontend](https://github.com/home-assistant/frontend)
- [JupyterLab](https://github.com/jupyterlab/jupyterlab)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
