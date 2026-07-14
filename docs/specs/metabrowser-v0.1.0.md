# Feature: MetaBrowser v0.1.0 Standalone Package

**Date:** 2026-07-14

**Author:** Joshua Levy and contributors

**Status:** In Review

## Overview

Publish MetaBrowser as an MIT-licensed Python package with a self-contained source,
test, documentation, and release workflow.
The package provides a local browser for files and structured artifacts, supports
trusted extensions through its plugin API, and uses KPress as its Markdown renderer.

## Goals

- Publish the `metabrowser` package for Python 3.12 and newer
- Depend on the exact audited `kpress==0.1.0` release
- Preserve the Python, server, browser, file-format, and plugin contracts covered by the
  test suite
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

## Design

### Package Boundary

MetaBrowser owns the generic file browser, server, browser shell, inventory and event
APIs, built-in renderers, and plugin runtime.
Application-specific behavior belongs in separate plugin distributions.
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
- **File formats:** Continue reading the formats covered by compatibility tests
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
- [x] Declare `kpress==0.1.0` as a required runtime dependency and remove alternate
  Markdown rendering paths
- [x] Apply the simple-modern-uv structure, committed uv lockfile, MIT license, and
  package metadata
- [x] Add CI, tag-driven publishing, dependency policy, and artifact inspection
- [x] Align Python and JavaScript quality gates with KPress and tbd guidance using
  strict BasedPyright, correctness-oriented Ruff rules, recommended Biome rules, strict
  TypeScript check-JS, exact npm locks, Lefthook, and SHA-pinned actions
- [x] Apply CLI configuration before server initialization, call the documented plugin
  entry-point factory, report incomplete installed plugins, and enforce JavaScript-only
  operator-directory plugins in both runtime behavior and diagnostic output
- [x] Reject duplicate data-hook routes before server startup so manifest order cannot
  silently shadow a plugin endpoint
- [x] Normalize and validate plugin paths across commands and direct server imports,
  load dotenv configuration consistently for serve, walk, plugin diagnostics, and remote
  mode, and use readiness-gated, platform-neutral browser launching
- [x] Expand home-relative served roots and reject traversal or symlink paths from both
  server deep links and standalone tree walks when they resolve outside the root; reject
  walk path flags in output modes that cannot apply them
- [x] Anchor Codex hooks to the git root and Claude hooks to the project root, and
  delegate legacy module execution to the canonical CLI before bootstrap side effects
- [x] Keep optional GitHub CLI setup non-fatal on unsupported platforms and enforce the
  repository’s exact tbd v0.4.0 pin across generated agent guidance
- [x] Isolate test discovery from operator plugin environment variables before tests
  import the server
- [x] Add public documentation for installation, development, architecture, plugins,
  design, testing, debugging, publishing, security, and contribution
- [x] Configure Flowmark and tbd v0.4.0 with the `mb-` issue prefix
- [x] Add tracked-file, source-distribution, and wheel public-hygiene checks
- [x] Complete review of the initial pull request with all GitHub Actions checks green

### First Release

- [ ] Make the repository public after the hygiene and artifact gates pass
- [ ] Configure the PyPI trusted publisher for the repository workflow
- [ ] Publish the GitHub `v0.1.0` release and verify the PyPI files and metadata
- [ ] Verify `uvx --from metabrowser==0.1.0 metabrowser`, server startup, built-in
  plugins, extension discovery, and KPress rendering from published artifacts
- [ ] Confirm the release remains available and is not yanked

## Testing Strategy

- Run Ruff, BasedPyright, codespell, npm policy, Biome, TypeScript check-JS, Flowmark,
  and public-hygiene checks
- Install Python and JavaScript tooling from committed locks, run JavaScript tools with
  `npx --no-install`, and audit the npm lock for moderate-or-higher vulnerabilities
- Run the full pytest and browser contract suites on every supported Python version
- Build and inspect the source distribution and wheel
- Install the wheel in an isolated uv environment and import the package
- Exercise command-line, server, plugin, filesystem, event, and KPress integration
  behavior through tests
- Require GitHub Actions to pass before merge and rerun the same gates against release
  artifacts before announcing publication

## Validation Evidence

The complete local `make verify` gate passes on the initial pull-request tree:

- Ruff and BasedPyright report no diagnostics
- Biome passes for every shipped browser module, and TypeScript check-JS passes for both
  the fully strict new-module configuration and the explicit legacy-module allowlist
- Flowmark and public-hygiene checks pass for the repository
- 615 Python and browser contract tests pass
- The source distribution and wheel contain the required assets and no repository-only
  tbd or agent metadata
- An isolated uv environment installs the wheel and exercises its command, packaged
  assets, built-in plugins, and KPress rendering

The pull request is ready to merge only when its latest commit has green lint,
distribution, and Python 3.12 through 3.14 jobs.

## Rollout Plan

1. Review and merge the complete standalone repository import
2. Change repository visibility only after repeating public-hygiene checks
3. Configure trusted publishing and create the `v0.1.0` GitHub release
4. Verify installation and runtime behavior from PyPI
5. Track future features and fixes in this repository using `mb-*` issues

## Decisions

- Package and import name: `metabrowser`
- License: MIT
- First release: `v0.1.0`
- Supported Python: 3.12 through 3.14
- Markdown renderer: exact `kpress==0.1.0`
- Dependency manager and build workflow: uv and simple-modern-uv
- Browser development toolchain: exact npm lock with Node 24.18.0 and npm 11.10 or newer
- Issue prefix: `mb-`

## References

- [Architecture](../architecture.md)
- [Development](../development.md)
- [Plugin authoring](../plugins.md)
- [Publishing](../publishing.md)
- [Supply-chain security](../../SUPPLY-CHAIN-SECURITY.md)
- [KPress](https://github.com/jlevy/kpress)
- [simple-modern-uv](https://github.com/jlevy/simple-modern-uv)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
