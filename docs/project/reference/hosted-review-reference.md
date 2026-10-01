# Hosted Review Format and Provider Resources: Reference Code

**Status:** Unused reference code.
It is not on the critical path, not part of the v0.12 stack, and not maintained.
The `reference/v012-hosted-review` branch exists only so this code is not lost, and it
must not be merged.
The annotated tag `reference/v012-hosted-review-2026-09-30` marks the
same commit, so the code stays reachable if the branch or its pull request is closed.

## What Is Preserved

The branch restores what [#246](https://github.com/jlevy/metabrowser/pull/246) removed
from the v0.12 stack: every commit there that removes code is reverted here with
`git revert`. The fixes #246 also carries stay applied: the `--doctor` help text, the
`--doctor` check of the cache record contracts, the corrected address and route
documentation, and the changelog line for the cache’s dependencies.

| Area | Where | Came from |
| --- | --- | --- |
| Hosted Review Format models, contracts, artifact codecs, resource-profile declarations, and browser model | `src/metabrowser/builtin_plugins/hosted_review/` | #134, #136, #139 |
| Its packaged schemas and conformance corpora | `src/metabrowser/data/hosted-review-format/` | #134, #136, #139 |
| The resource-profile types and their registry | `src/metabrowser/provider_resources/`, `plugin_loader/artifact_contracts.py` | #136, #226 |
| The public capability surface: the `metabrowser.capabilities.v1` entry-point group, its discovery, nine exports from `metabrowser` and `metabrowser.plugin_api`, and the `metab --doctor` provider, contract, and profile counts | `plugin_loader/capability_discovery.py`, `plugin_loader/capability_types.py`, `pyproject.toml`, `cli/plugins.py` | #136, #140 |
| Browser-parser evidence for artifact contracts | `devtools/artifact-contract-browser-check.mjs`, `devtools/check_artifact_contracts.py`, `devtools/check_distribution.py` | #136 |
| The frontmatter Markdown artifact profile | `plugin_loader/artifact_contracts.py` | #136 |
| The cache’s reservations for a provider store: two directories, the provider-resource lock, and the provider-derived store identity | `cache/paths.py`, `cache/locks.py`, `cache/identity.py`, `tests/fixtures/repository-cache/` | #140 |
| The GitHub coverage oracle | `tests/fixtures/github/oracle/`, `tests/test_github_coverage.py` | #134 |
| Their tests | `tests/test_hosted_review_*.py`, `tests/test_capability_discovery.py`, and parts of the contract-registry and cache-lock tests | #134, #136, #139, #140 |

The design is in
[Hosted Review Model and Provider Boundary](../architecture/arch-hosted-review-model.md)
and
[External Resources, Artifact Contracts, and Views](../architecture/arch-external-resources-and-views.md).

## How It Was Wired

Only part of this code was a leaf.

- `builtin_plugins/hosted_review/` had no importer and no manifest, route, kind, or
  view. Its contracts were reached only through two capability entry points.
- The capability types and `provider_resources` were wired into live modules:
  `plugin_api.py` re-exported them, the contract registry and its inventory were built
  on them, `cache/contracts.py` declared the cache’s contracts through them, and
  `metab --doctor`, the format gate, and the distribution check read the discovered
  providers.

Restoring the code therefore restores that wiring.
On this branch the cache’s contract registry is again a capability provider,
`plugin_api` again imports `provider_resources` at every server start, and `--doctor`
again reports capability providers, contracts, and profiles.
Taking the Hosted Review Format alone from here means untangling those three first, as
#246 did.

## Why It Was Retired

[Thin Mirror for Git and GitHub Browsing](../specs/active/plan-2026-09-23-v012-thin-mirror.md),
decided 2026-09-23, makes Metabrowser a thin wrapper over `git` and `gh`. Pull-request
data is one validated JSON record per pull request in the GitHub plugin, with plain
Pydantic models and no separate artifact-format or resource-profile layer.
GitHub support is internal, with no new public SDK. That left this code with no
consumer, while its entry points, exports, and doctor output would have become public
surface on release.

## Before Reusing Any of It

Treat this as a starting point to re-plan, not as code to restore.

- **It does not track the stack.** Nothing rebases this branch, so it drifts from `main`
  as the cache, the GitHub plugin, and the plugin SDK change.
- **No provider adapter, store, route, kind, or view was ever built on it.** The format,
  contracts, and gates are the whole implementation; the provider snapshot store,
  bindings, authorization contexts, addresses, and views in the two design documents are
  designs only.
- **Decide the consumer first.** The pull-request page reads `PullRecord` in
  `builtin_plugins/github/pull_record.py`. A provider-neutral format needs a second
  provider or a second consumer that the plain records cannot serve.
- **Decide the public surface deliberately.** The entry-point group and the exported
  declaration types are a plugin SDK. Restoring them is a compatibility commitment once
  released; see
  [Compatibility and Legacy Code](../../development.md#compatibility-and-legacy-code).
- **Re-measure and re-review the bounds.** The record bounds, the coverage oracle’s
  recorded GitHub responses, and the SoftSchema release they were compiled with are as
  of September 2026.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
