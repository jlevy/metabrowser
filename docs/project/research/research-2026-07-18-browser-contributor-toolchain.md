# Research: Browser Contributor Toolchain and Distribution

**Date:** 2026-07-18 (last updated 2026-08-27)

**Author:** Metabrowser maintainers with research assistance

**Status:** Current recommendation; implementation requires a dedicated plan

## Decision

Keep Metabrowser’s current raw-source browser build until a dedicated shell
modernization project can measure the migration against it.
When that project begins, evaluate TypeScript, Vite, and Vitest as the first
full-toolchain candidate.

The contributor toolchain and the shipped artifact are separate decisions:

- The **contributor plane** covers authored source, type checking, local development,
  unit and component tests, browser tests, and build feedback.
- The **distribution plane** is the browser asset tree inside the wheel.
  It must remain offline, same-origin, reproducible from exact inputs, inspected by the
  distribution gate, and usable without Node or npm after installation.

A full toolchain can improve the contributor plane without weakening the distribution
contract. It does not earn adoption merely because comparable projects use it.
The migration must reduce a measured maintenance or feedback cost and must preserve the
wheel’s auditability.

This conclusion updates the stronger July recommendation from pull request #12. Since
then, the project has shipped the diff renderer, expanded its strict JavaScript module
set, and built a dependency-free Chrome performance harness.
The diff renderer is no longer an appropriate toolchain pilot, and the existing test and
performance work is an asset to retain rather than a scaffold to replace.

## Current Metabrowser Baseline

Metabrowser serves first-party browser files directly from `src/metabrowser/static/` and
the built-in plugin directories.
The wheel contains those same files; there is no first-party transpilation or bundling
step.

The current contributor plane has:

- TypeScript `checkJs` with `strict`, `noImplicitAny`, and `strictNullChecks` for the
  main static and built-in plugin trees
- an explicit legacy allowlist for files not yet under that strict gate
- Biome formatting and linting
- Node `vm` DOM shims and focused contract suites
- Python route, wire, packaging, and installed-wheel tests
- a dependency-free Chrome DevTools Protocol driver for trusted-input performance and
  convergence profiles

The current distribution plane has:

- raw first-party JavaScript with mtime-derived cache-busting URLs
- exact-pinned third-party browser packages copied from the locked npm installation
- a committed SHA-256 manifest, copied license texts, and per-file and total size caps
- tests that compare the vendor tree with the manifest and reject external browser
  origins
- wheel inspection and an isolated installed-wheel smoke test

Since July, the project has added strict modules, broader contract coverage, and a
repeatable Chrome performance loop.
The remaining cost is that `app.js` is still a large legacy composition root, while new
behavior is spread across a growing set of strict modules and bespoke Node harnesses.
A migration should measure whether standard module, test, and development tooling lowers
that cost.

## Evidence from Python-Backed Web Applications

The following table records the browser toolchains in six Python-backed applications.
It is a precedent survey, not a popularity score.
Links are pinned to the revisions inspected on 2026-08-27.

| Application | Browser build | Test runner | Relevant evidence |
| --- | --- | --- | --- |
| Streamlit | Vite 8, React, TypeScript | Vitest; browser and Lighthouse tooling | [`frontend/app/package.json`](https://github.com/streamlit/streamlit/blob/2ac0d77d3aedf9e7fee58147ecf7cda1dc47492a/frontend/app/package.json) |
| Gradio | Vite 8, Svelte, TypeScript | Vitest Browser and Storybook tests | [root workspace](https://github.com/gradio-app/gradio/blob/44f8712bfc11d53b714c9fc9b44cd7486a407777/package.json), [`js/app`](https://github.com/gradio-app/gradio/blob/44f8712bfc11d53b714c9fc9b44cd7486a407777/js/app/package.json) |
| Airflow UI | Vite 8, React, TypeScript | Vitest and Playwright | [`package.json`](https://github.com/apache/airflow/blob/f727ea8544d1b0b7759e78e5dfcb257dd8292957/airflow-core/src/airflow/ui/package.json) |
| marimo | Vite 8, React, TypeScript | Vitest, Playwright, and Storybook | [`frontend/package.json`](https://github.com/marimo-team/marimo/blob/59ef0a9b6939db13f2d27950479e9e722eef405d/frontend/package.json) |
| Home Assistant frontend | Rspack 2, Lit, TypeScript | Vitest and Playwright | [`package.json`](https://github.com/home-assistant/frontend/blob/29cd46eb9e49cf2a5beb67db9108ed6c065c7331/package.json) |
| JupyterLab | Custom webpack-based Yarn workspace, TypeScript | Package-level tests and Galata browser tests | [`package.json`](https://github.com/jupyterlab/jupyterlab/blob/8f4050aba7f6716aaa748c4fe79c9c1dedfe2669/package.json) |

Four of the six use Vite, five use Vitest, and all six have a build step between
authored source and distributed browser assets.
The newer applications cluster around Vite and Vitest; Home Assistant and JupyterLab
show that neither is a prerequisite for a large Python-backed UI.

The precedent that transfers to Metabrowser is the separation of contributor and
distribution concerns.
These projects give contributors a standard browser development environment while
shipping built assets with the Python application.
The survey does not establish that Metabrowser should adopt their frameworks, monorepo
scale, or dependency counts.

## Options

### Continue Serving First-Party Source Directly

First-party `.js` files remain the files reviewed, tested, packaged, and debugged.
TypeScript checks them without emitting code.

**Advantages:**

- no generated first-party asset tree or source-map dependency
- direct correspondence between a reviewed line and the line a browser executes
- no Node build step in the wheel build
- current supply-chain, distribution, and performance gates remain unchanged

**Costs:**

- no native `.ts` authoring
- no standard component-test runner or hot-module development loop
- browser and DOM tests keep using repository-specific harnesses
- worker entries and ESM-only third-party graphs need relative imports or a separate
  bundling mechanism
- the legacy composition root remains outside the fully strict project

This is the current choice.
It stays valid while its maintenance and feedback costs are lower than the cost of a
generated asset boundary.

### Bundle Only Third-Party Graphs and Worker Entries

First-party code stays directly served.
A pinned bundler emits one or more reviewed vendor artifacts for an ESM-only package or
a worker whose dependency graph cannot use relative imports alone.

This option extends the existing `vendor_assets.py` model, but a bundle is not the same
as a copied upstream file.
The repository would need to record:

- the exact entry point and build configuration
- the complete locked input graph and licenses
- the emitted file list, hashes, and size limits
- whether a rebuild must be byte-identical or only semantically equivalent
- source maps and a review path back to upstream source

The July spike produced byte-identical unminified esbuild output for one exact entry,
version, and platform.
That is useful evidence for the mechanism, not a general determinism guarantee.

### Adopt a Full TypeScript, Vite, and Vitest Contributor Plane

Authored browser code moves to `.ts` or typed framework-free modules.
Vite supplies the development server and production build; Vitest owns DOM-free and
component-level tests.
The existing Python server remains the API and production host.
Built assets, not Node, ship in the wheel.

**Advantages:**

- native TypeScript authoring and module graphs
- a standard test runner with watch mode and browser-oriented tooling
- hot-module development and ordinary support for workers and ESM dependencies
- a familiar path for browser contributors and coding agents
- one build graph that can emit source maps, chunks, workers, and CSS assets

**Costs:**

- reviewed source and executed distribution files become different artifacts
- the wheel build or committed-output workflow gains a Node build boundary
- source-map correctness, chunk naming, caching, and asset inventory become release
  contracts
- Vite brings Rolldown, PostCSS, Lightning CSS, and their transitive graphs into the
  build
- migrating the current Node shims and global shell seams is real project work even if
  the tool installation is small

This is the preferred candidate when a dedicated modernization project starts.
It is not approved by this research alone.

### Use Rspack, Bun, or a Library Bundler

Home Assistant demonstrates Rspack in a large browser application, but its webpack model
would add a less familiar configuration surface for this repository.
Bun combines runtime, package manager, bundler, and test runner, but would add another
runtime beside the pinned Node toolchain.
Library-oriented bundlers such as tsdown do not supply the application development and
testing workflow at issue here.

These remain alternatives if a concrete constraint rules out Vite.
None currently does.

## Browser and Platform Constraints

### Workers and Import Maps

Import maps let directly served modules resolve bare specifiers in documents.
They do not currently solve bare-specifier resolution inside workers; the WHATWG issue
for [import maps in worker environments](https://github.com/whatwg/html/issues/8173)
remains open. A buildless worker must use relative module specifiers, or its dependency
graph must be bundled.

### Content Security Policy

Production output must work with same-origin scripts, styles, workers, connections, and
images. A tool’s general Content Security Policy compatibility is not enough.
The gate must inspect and run the exact emitted assets, reject external URLs and runtime
code generation, and exercise workers under the production policy.

### Offline Distribution

`pip install` must continue to provide every browser asset.
Development servers, registry access, and runtime CDN imports are contributor
conveniences or rejected designs; none may become an installed-product requirement.

### Asset Loading Tiers

Bundling does not erase the eager, prefetched, and on-demand tiers in
[development](../../development.md#asset-loading-tiers).
A generated chunk is still a browser cost.
The build manifest must preserve enough ownership to show which route or feature loads
each emitted asset and why.

## Supply-Chain Review

No dependency is added by this research.
Any implementation must follow
[supply-chain security](../../../SUPPLY-CHAIN-SECURITY.md) and review exact versions
after the repository’s 14-day cool-off.

The July draft understated one risk.
The [esbuild 0.28.2 package manifest](https://registry.npmjs.org/esbuild/0.28.2)
declares a `postinstall` script.
The July spike showed that its selected release worked with `--ignore-scripts`; it did
not show that esbuild has no lifecycle script or that every future release works without
one. The implementation review must inspect the selected package tarballs and prove the
locked install and build under the repository’s disabled script policy.

The same exact-version review applies to Vite, Rolldown, Lightning CSS, TypeScript, and
Vitest. Package counts and script behavior change too often to preserve as architectural
facts. The implementation PR should report them from its actual lockfile.

## Migration Conditions

Open a toolchain implementation only when it names the present cost it will reduce and
can measure that cost before and after.
The plan should include these conditions:

1. Preserve the current raw-source build as the comparison baseline.
2. Choose an isolated strict module or new surface as the pilot.
   Do not migrate the production diff renderer merely to prove the toolchain.
3. Define whether built output is committed or created during the wheel build.
   Either choice needs one source of release truth and a reproducibility check.
4. Keep the existing Node contract suites and Chrome performance scenarios until the
   replacement tests prove the same behavior and timing boundaries.
5. Exercise source maps, offline startup, strict Content Security Policy, workers,
   themes, disposal, and installed-wheel behavior against emitted assets.
6. Measure development feedback time, production parse and execution time, wheel size,
   emitted request count, and reviewability of generated changes.
7. Migrate incrementally behind existing shell boundaries.
   Remove each old path when its consumers have moved; do not maintain speculative dual
   systems.

The implementation is successful when contributors get a simpler browser development
loop and the shipped wheel remains at least as inspectable and responsive as the
baseline.

## Methodology and Limits

The July version of this research surveyed diff products, renderer packages, build
tools, and Python-backed web applications.
The diff-product material is already covered by
[Web Diff Viewer Architecture and Intermediate Representations](research-2026-07-17-web-diff-viewer-architecture.md);
this document retains only the contributor-toolchain question.

The 2026-08-27 update inspected current Metabrowser source, configuration, test, vendor,
and distribution paths.
It also read the pinned package manifests linked in the precedent table, the npm
registry manifests for Vite, Vitest, esbuild, and TypeScript, and the open WHATWG
worker-import-map issue.
Package versions and transitive graphs are observations at that date, not
recommendations.

The survey covers six established applications selected for architectural similarity.
It does not measure contributor productivity or control for application size, framework,
team structure, or release process.
Its evidence supports the feasibility of separating the two planes, not a causal claim
that a particular bundler grows a community.

## References

- [Vite guide](https://vite.dev/guide/)
- [Vitest guide](https://vitest.dev/guide/)
- [TypeScript documentation](https://www.typescriptlang.org/docs/)
- [esbuild getting started](https://esbuild.github.io/getting-started/)
- [Import maps](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/script/type/importmap)
- [Import maps in worker environments](https://github.com/whatwg/html/issues/8173)
- [npm `min-release-age`](https://docs.npmjs.com/cli/v11/using-npm/config#min-release-age)
- [Supply-chain security](../../../SUPPLY-CHAIN-SECURITY.md)
- [Development](../../development.md)
- [Historical Diff View Spike Results](archive/research-2026-07-18-diff-view-spike-results.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
