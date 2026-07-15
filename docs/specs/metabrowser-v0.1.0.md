# Feature: MetaBrowser v0.1.0 Standalone Package

**Date:** 2026-07-14

**Author:** Joshua Levy and contributors

**Status:** Release Candidate

## Overview

Publish MetaBrowser as an MIT-licensed Python package with a self-contained source,
test, documentation, and release workflow.
The package provides a local browser for files and structured artifacts, supports
trusted extensions through its plugin API, and uses KPress as its Markdown renderer.

## Goals

- Publish the `metabrowser` package for Python 3.12 and newer
- Expose `metab` as the primary CLI and retain `metabrowser` as a compatibility alias
- Make zero-install, global-tool, plugin, and agent onboarding immediately discoverable
  from the top-level README
- Publish a portable MetaBrowser Agent Skill that delegates to the pinned zero-install
  runner and treats CLI help as the command reference
- Depend on the exact audited `kpress==0.2.2` release
- Declare and enforce a tested minimum version for every other direct runtime dependency
- Preserve the Python, server, browser, file-format, and plugin contracts covered by the
  test suite
- Keep transparent compression in core while placing specialized binary readers in
  separately installed plugins
- Use the simple-modern-uv project structure with uv, Ruff, BasedPyright, pytest, Biome,
  TypeScript check-JS, and tag-driven releases
- Apply the 14-day dependency cool-off, frozen lockfile, SHA-pinned GitHub Actions, and
  PyPI trusted publishing
- Keep every tracked file and distribution artifact free of private repository names,
  internal issue identifiers, local paths, credentials, customer data, and operational
  artifacts
- Make the initial repository import reviewable as one complete pull request

## Non-Goals

- Build an editor extension
- Redesign the browser UI or rewrite the backend
- Add a second Markdown renderer or a local copy of KPress
- Add application-specific plugins, schemas, routes, fixtures, or operational docs to
  the generic package
- Ship specialized binary-store readers or their native dependencies in the core wheel

## Design

### Package Boundary

MetaBrowser owns the generic file browser, server, browser shell, inventory and event
APIs, built-in renderers, and plugin runtime.
Application-specific behavior belongs in separate plugin distributions.
Transparent compression belongs in core because it precedes file classification;
format-specific binary interpretation belongs in external plugins.
KPress owns Markdown-to-HTML rendering and is consumed only through its published
package interface.

The source distribution and wheel must build and test without sibling repositories or
workspace source overrides.
The built wheel must include every static asset, manifest, and typed-package marker
required at runtime.

### Compatibility

- **Python and JavaScript plugin APIs:** Preserve the documented manifest, entry-point,
  SDK, and lifecycle contracts
- **Server APIs:** Preserve documented routes and observable response shapes
- **File formats:** Preserve generic file and gzip behavior; add bounded zlib streams
  before release; keep specialized binary formats available through plugins
- **Internal module paths:** No stability guarantee beyond documented public APIs
- **Database schemas:** Not applicable

### Release Model

The first release is `v0.1.0`. The Git tag supplies the package version through
uv-dynamic-versioning.
GitHub Actions builds from the committed lockfile and publishes to PyPI through OpenID
Connect trusted publishing without a package token.

## Implementation Plan

### Standalone Repository

- [x] Add package source, built-in plugins, browser assets, typed-package metadata, and
  behavior-focused tests
- [x] Declare `kpress==0.2.2` as a required runtime dependency and remove alternate
  Markdown rendering paths
- [x] Consume the KPress v2 asset manifest end to end, including dependency-only
  resources, browser entry-point roles, stylesheet/module/classic loading modes, and
  import maps
- [x] Preserve gzip transparency across bounded text previews, logical-byte pagination,
  frontmatter-driven classification, Markdown rendering, and KPress static export;
  degrade malformed gzip size and read failures into endpoint error contracts
- [x] Remove specialized binary-store code and native dependencies from the core wheel;
  retain the manifest, browser SDK, and installed-entry-point seams needed by external
  format plugins
- [x] Add bounded zlib artifact support with logical-extension handling, streaming
  previews, rendering and export integration, malformed-stream errors, and
  decompression-bomb limits
- [x] Apply the simple-modern-uv structure, committed uv lockfile, MIT license, and
  package metadata
- [x] Publish `metab` as the primary console script while retaining `metabrowser` for
  existing callers and the `uvx metabrowser` package-name shorthand
- [x] Simplify the README around `uvx metabrowser`, the globally installed `metab`
  command, plugin discovery, and command help; publish the L1 Agent Skill at
  `skills/metabrowser/SKILL.md` with a pinned `uvx metabrowser@0.1.0` runner
- [x] Add CI, tag-driven publishing, artifact inspection, and a package policy that
  enforces the reviewed runtime floors and exact KPress compatibility pin
- [x] Align Python and JavaScript quality gates with KPress and tbd guidance using
  strict BasedPyright, correctness-oriented Ruff rules, recommended Biome rules, strict
  TypeScript check-JS, exact npm locks, Lefthook, and SHA-pinned actions
- [x] Pin Node 24.18.0 for nvm and fnm, require npm 11.10 or newer, and isolate Make
  targets from conflicting host-level npm release-cutoff configuration
- [x] Apply CLI configuration before server initialization, call the documented plugin
  entry-point factory, report incomplete installed plugins, and enforce JavaScript-only
  operator-directory plugins in both runtime behavior and diagnostic output
- [x] Reject duplicate data-hook routes before server startup so manifest order cannot
  silently shadow a plugin endpoint
- [x] Normalize and validate plugin paths across commands and direct server imports,
  load dotenv configuration consistently for serve, walk, plugin diagnostics, and remote
  mode and before direct ASGI server initialization, and use readiness-gated,
  platform-neutral browser launching
- [x] Expand home-relative served roots and reject traversal or symlink paths from both
  server deep links and standalone tree walks when they resolve outside the root; reject
  walk path flags in output modes that cannot apply them and file targets that cannot
  form subtrees
- [x] Anchor Codex hooks to the git root and Claude hooks to the project root, and
  delegate legacy module execution to the primary CLI before bootstrap side effects
- [x] Keep optional GitHub CLI setup non-fatal on unsupported platforms and enforce the
  repository’s exact tbd v0.4.0 pin across generated agent guidance
- [x] Isolate test discovery from operator plugin environment variables before tests
  import the server
- [x] Add public documentation for installation, development, architecture, plugins,
  design, testing, debugging, publishing, security, and contribution
- [x] Configure Flowmark and tbd v0.4.0 with the `mb-` issue prefix
- [x] Add tracked-file, source-distribution, and wheel public-hygiene checks
- [x] Complete final review reconciliation with all tracked findings closed, the full
  local release gate passing, no unresolved review threads, and all GitHub Actions
  checks green on the reconciliation commit
- [x] Apply tbd Common Documentation Guidelines across project-authored Markdown, format
  it with Flowmark, and enforce the standard footer without modifying generated template
  copies or rendering fixtures

### Final Review Reconciliation

- [x] Inventory every top-level review, formal review, inline thread, and merged
  follow-up finding and map each item to a tbd issue
- [x] Resolve every accepted runtime, security, performance, tooling, documentation, and
  public-hygiene finding, or record a tested disposition where the existing boundary is
  intentional
- [x] Add a public-safe manual browser corpus and verify every documented view against a
  running source checkout
- [x] Preserve KPress sanitization as an explicit dependency contract and keep its
  auxiliary browser assets non-fatal after the rendered document is available
- [x] Enforce frozen, explicitly repository-configured uv execution in Make targets,
  hooks, workflows, and executable documentation; make parallel verification ordering
  safe and publish without mutable dependency caches
- [x] Run `make verify`, confirm zero unresolved review threads, publish the complete
  bead-to-finding reconciliation, and close and sync the review bead tree

### First Release

- [x] Make the repository public after the hygiene and artifact gates pass
- [ ] Configure the PyPI trusted publisher for the repository workflow
- [ ] Publish the GitHub `v0.1.0` release and verify the PyPI files and metadata
- [ ] Verify `uvx metabrowser@0.1.0`, the globally installed `metab` command, server
  startup, built-in plugins, extension discovery, and KPress rendering from published
  artifacts
- [ ] Install the public skill with
  `npx skills add jlevy/metabrowser --skill metabrowser` and confirm it invokes the
  published pinned runner and routes agents to current CLI help
- [ ] Confirm the release remains available and is not yanked

## Testing Strategy

- Run Ruff, BasedPyright, codespell, npm policy, Biome, TypeScript check-JS, Flowmark,
  and public-hygiene checks
- Require the package-policy check to reject missing, weakened, or unreviewed direct
  runtime requirements
- Install Python and JavaScript tooling from committed locks, run JavaScript tools with
  `npx --no-install`, and audit both frozen dependency graphs for known vulnerabilities
- Run the full pytest and browser contract suites on every supported Python version
- Build and inspect the source distribution and wheel
- Validate the public Agent Skill metadata and confirm it is included in the source
  distribution
- Install the wheel in an isolated uv environment, import the package, and invoke both
  console scripts
- Exercise command-line, server, plugin, filesystem, event, and KPress integration
  behavior through tests, including the complete KPress asset-manifest closure and
  compressed preview, frontmatter, render, and export paths
- Require GitHub Actions to pass before merge and rerun the same gates against release
  artifacts before announcing publication

## Validation Evidence

The complete local `make -j4 verify` gate passes on the release-candidate working tree:

- Ruff and BasedPyright report no diagnostics
- Biome passes for every shipped browser module, and TypeScript check-JS passes for both
  the fully strict new-module configuration and the explicit legacy-module allowlist
- Flowmark and public-hygiene checks pass for the repository
- The MetaBrowser skill passes the Agent Skills structure validator and uses the pinned
  first-release `uvx` runner
- 674 Python and browser contract tests pass
- The source distribution and wheel contain the required assets and no local
  environments, build trees, or repository-only tbd and agent metadata
- The frozen Python and npm dependency graphs have no known vulnerabilities
- The checked-in nvm and fnm version files select Node 24.18.0, and the Make targets use
  repository-owned npm policy even when the host exports a conflicting cutoff
- An isolated uv environment installs the wheel and exercises `metab`, the `metabrowser`
  compatibility alias, packaged assets, built-in plugins, and KPress rendering
- A clean synthetic `v0.1.0` tag builds version `0.1.0` source and wheel distributions,
  passes distribution inspection, and installs both console scripts under Python 3.12
- A running source checkout renders the public Markdown, structured, source, JSONL,
  image, and binary fixtures; live create/delete updates Files and Recent; direct hash
  links, light/dark themes, a 480-pixel viewport, keyboard focus, and print handoff are
  usable without browser warnings or errors
- The exact public `kpress==0.2.2` wheel resolves from PyPI under the package-scoped
  first-party exception; its host-decoded export seam adds no transitive dependency

The pull request is ready to merge only when its latest commit has green lint,
distribution, and Python 3.12 through 3.14 jobs.

## Rollout Plan

1. Review and merge the release-readiness pull request
2. Configure trusted publishing and create the `v0.1.0` GitHub release
3. Verify installation, the Agent Skill, and runtime behavior from PyPI
4. Track future features and fixes in this repository using `mb-*` issues

## Decisions

- Package and import name: `metabrowser`
- Primary CLI and compatibility alias: `metab` and `metabrowser`
- License: MIT
- First release: `v0.1.0`
- Supported Python: 3.12 through 3.14
- Markdown renderer: exact `kpress==0.2.2`
- Compression boundary: gzip and zlib in core; specialized binary readers in external
  plugins
- Dependency manager and build workflow: uv and simple-modern-uv
- Browser development toolchain: exact npm lock with Node 24.18.0 and npm 11.10 or newer
- Issue prefix: `mb-`
- Agent integration: portable L1 skill with a pinned zero-install runner and no hooks or
  project mutation

## References

- [Architecture](../architecture.md)
- [Development](../development.md)
- [Plugin authoring](../plugins.md)
- [MetaBrowser Agent Skill](../../skills/metabrowser/SKILL.md)
- [Publishing](../publishing.md)
- [Supply-chain security](../../SUPPLY-CHAIN-SECURITY.md)
- [KPress](https://github.com/jlevy/kpress)
- [simple-modern-uv](https://github.com/jlevy/simple-modern-uv)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
