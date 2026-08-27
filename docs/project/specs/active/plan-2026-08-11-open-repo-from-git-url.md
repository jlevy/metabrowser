# Feature: Repository Library and Open from a Git URL

**Date:** 2026-08-11 (rewritten 2026-08-26)

**Author:** Joshua Levy (with LLM assistance)

**Status:** Draft

## Vision

Metabrowser should open a remote repository as easily as a local directory:

```shell
metab https://github.com/pallets/flask
```

The first open acquires the repository into a versioned application cache.
Later opens reuse a pinned, read-only working tree immediately, without waiting for the
network. The cache becomes a local repository library: durable enough to support recent
and favorite repositories, structured enough to hold provider metadata, and disposable
enough that a damaged entry can be rebuilt from its source.

The repository library should let a reader move between repositories, branches, commits,
diffs, and provider objects such as GitHub pull requests without first managing
checkouts in an editor.
Git remains the authority for repository content and history.
Provider adapters add hosted metadata and views without changing the Git data model.

Phase 1 accepts a repository URL, clones or reuses one cache entry, and routes its
`gitroot` through the existing serve path.
Later phases add refresh, an in-app repository chooser, provider caches, and
pull-request views.

The
[repository-cache research](../../research/research-2026-08-11-repo-cache-and-git-url-open.md)
contains the acquisition measurements and prior-art survey.
Its 2026-08-26 addendum separates the dated evidence from the current design after Git
diff and revision navigation shipped through v0.8.0.

## Goals

- Accept GitHub repository URLs and ordinary safe Git clone URLs anywhere the CLI
  currently accepts a root path.
- Preserve the root argument as a string at the Click/Typer boundary, then classify it
  before any `Path` construction can rewrite URL syntax.
- Derive one stable cache identity from the credential-free source identity, then reuse
  the same entry on every later open.
- Keep the browsed working tree pinned and read-only from the product’s perspective.
  Fetching remote refs must not dirty or silently advance it.
- Make a cache hit an offline operation.
  Network refresh starts only when requested or under an explicit refresh policy.
- Publish a clone only after its checkout and metadata are complete, so an interrupted
  clone is never mistaken for a usable repository.
- Establish `~/.metabrowser/` as a versioned application home with a durable user
  config, a separately stamped cache layout, and an explicit migration contract
  beginning at `f01`.
- Keep repository acquisition provider-neutral while reserving a bounded namespace for
  provider-owned metadata such as cached GitHub pull requests.
- Reuse the shipped Git history and diff surfaces.
  A cached repository must behave like the same repository opened from a user-managed
  path.
- Keep credentials in the user’s existing Git and provider credential stores.
  No cache record, log message, or browser response may contain a token or
  credential-bearing URL.
- Make list, inspect, refresh, and purge operations possible without teaching each
  future provider its own cache-management system.

## Non-Goals

- Editing a cached working tree.
  Cached roots never enable file mutations.
- Automatically advancing the browsed checkout whenever a remote branch moves.
  Fetching and choosing which revision to browse are separate operations.
- A hosted or multi-user service.
  The design retains the single-user localhost model.
- Supporting arbitrary Git transports.
  Phase 1 accepts HTTPS and SSH forms; unsafe helpers such as `ext::` remain disabled.
- A full GitHub object model in the first release.
  The provider namespace and refresh contract are designed now; pull-request fields and
  views arrive in later phases.
- Storing provider credentials in `config.yml` or provider records.
- Automatic LRU eviction before real cache-growth measurements establish a defensible
  size and age policy.
  Phase 1 provides explicit inspection and purge.
- Replacing Git with provider APIs for content or diffs.
  Provider metadata references immutable Git object IDs already held by the repository
  cache.
- Treating a repository’s own `.metabrowser/` directory as trusted configuration.
  Content under `gitroot` is untrusted input, including files with that name.

## Current Git and Trust Boundaries

As of v0.8.0:

- `metabrowser.git.process` is the only Git subprocess path and already provides fixed
  argument vectors, bounded output, timeouts, concurrent stream draining, cancellation
  cleanup, repository-environment scrubbing, and typed failures.
- `/api/git/log` renders repository history, and selecting a revision starts commit
  detail and the diff plugin’s comparison work concurrently.
- `metabrowser.diff.adapters.git` resolves comparisons, reads raw changes and line
  counts, produces bounded patches, and reads content by object ID.
- Git revision routes use full object IDs.
  Provider records can resolve their base, head, and merge revisions to IDs before a
  view renders them.
- The trust-profile work remains open.
  A fetched repository is third-party content, so URL-opened roots still depend on the
  `--untrusted` capability profile (`mb-vib1`).
- The general diff plan already assumes one repository-acquisition workflow for remote
  URLs, local reference clones, and pull-request refs.
  This plan owns that workflow.

The 2026-08-11 measurement covers only part of the current click path.
The history list still needs only commit and tree objects, but a revision view also
starts a complete comparison.
Its manifest uses `--raw` and `--numstat`, and its patches need blobs.
Blobless clone plus background backfill remains the leading strategy, but Phase 0 must
remeasure the exact v0.8.0 routes before using the 0.49-second commit-detail sample as a
product claim.

## Design Principles

### One stable source identity, one readable path

The cache key is not a display string.
It is a SHA-256 digest of a normalized, credential-free source identity.
The directory name combines a readable slug with a short digest:

```text
github-com--pallets--flask--7d5c1a2e4b90
```

The full digest in `repo.yml` is authoritative.
If the proposed directory already holds a different full digest, path derivation extends
the suffix deterministically.
Path claim and publication use no-replace semantics, so concurrent sources with the same
short prefix cannot alias or overwrite one another.

Normalization removes query strings, fragments, a terminal `.git`, and redundant slashes
where doing so preserves Git identity.
It rejects embedded credentials.
It does not lowercase every path segment: GitHub repository identity is
case-insensitive, but a generic Git host need not be.
Provider adapters may apply a provider-proven canonicalization rule; the
provider-neutral path does not guess.

HTTPS and SSH spellings are distinct identities in Phase 1 unless a provider adapter can
prove they name the same repository.
`repo.yml` may record additional source aliases later without changing the primary
identity.

### Repository content is pinned; refs and provider data may refresh

`gitroot/` is an ordinary checkout pinned to `active_revision`. Metabrowser never edits
files under it, stages changes, pulls, merges, resets, or checks out another revision in
place. The product’s read-only guarantee is an ownership rule rather than blanket file
permissions, which would make cleanup unreliable across platforms.

A Git refresh runs `git fetch --prune` under the cache manager.
Fetch may add objects and atomically move remote-tracking refs, but it does not touch
`gitroot` or change `active_revision`. A later “open latest” operation builds a complete
replacement in staging and promotes it only while the entry is not being served.
A live session remains pinned to the revision it opened.

If an integrity check finds a dirty cached worktree, the cache manager does not reset it
or absorb the changes.
It reports the entry as externally modified and builds a new entry or asks for explicit
purge. A supposedly read-only cache becoming dirty is a boundary failure, not a state to
normalize silently.

### A cache hit wins the race with refresh

Opening an existing entry serves its current `gitroot` first.
A configured or user-requested refresh is separate work and cannot hold first paint
hostage. This keeps offline behavior deterministic and makes the repository chooser
useful even when the network is slow or unavailable.

### Provider data is a projection, not repository authority

GitHub pull-request data is mutable and may be stale.
It lives beside, not inside, `gitroot`, with fetch time, validators, and resolved base
and head object IDs.
The Git object database remains the authority for content and diffs.

Provider code belongs in a built-in plugin.
Core owns safe cache namespaces, refresh-job coordination, and Git acquisition; a GitHub
plugin owns GitHub API schemas, routes, renderers, and styles.
This keeps Metabrowser core consumer-agnostic and allows another provider to implement
the same contracts without adding GitHub branches to core code.

## Application Home and Format `f01`

The application home starts with this layout:

```text
~/.metabrowser/
├── config.yml
└── cache/
    ├── layout.yml
    ├── locks/
    ├── staging/
    └── repos/
        └── <uniquified-slug>/
            ├── repo.yml
            ├── gitroot/
            └── github/                 # Future; absent until provider data exists
                └── pull-requests/
                    └── <number>.yml
```

`METABROWSER_HOME` may override the application home for tests and advanced use.
`METABROWSER_CACHE_DIR` remains a narrower cache-root override if compatibility with the
existing proposed interface is useful; the implementation should choose one authority
and reject conflicting values rather than silently split state.

Paths in config expand `~` against the operator’s home and resolve relative paths
against the application home.
The parser does not apply shell expansion or execute environment-variable syntax found
in YAML.

### Durable config

`config.yml` is user-owned and durable.
The minimal initial file is:

```yaml
format: f01
written_by: 0.9.0
upgrades:
  - version: 0.9.0
    at: 2026-08-26T00:00:00Z
cache:
  root: ~/.metabrowser/cache
  refresh: manual
```

The release version above illustrates the shape; implementation stamps the version that
actually creates the file.
`format` is the functional compatibility marker.
`written_by` and `upgrades` are informational.
Unknown top-level and nested keys are preserved on read and write so a compatible older
client cannot erase a newer setting.
Credentials are forbidden.

### Cache layout marker

`cache/layout.yml` carries the same home-layout marker:

```yaml
format: f01
created_by: 0.9.0
```

The two markers have different durability.
`config.yml` contains user choices and must be migrated losslessly.
The cache can be rebuilt, but it should be quarantined rather than deleted when offline
or when a source may no longer be reachable.

The format contract adapts the model reviewed in `jlevy/tbd`:

1. One module owns `CURRENT_FORMAT`, `FORMAT_HISTORY`, the sequential migration
   functions, and the standard upgrade error.
2. An older client that sees a future format fails before writing.
   It never strips fields, downgrades a marker, or guesses at a cache layout.
3. A newer client migrates each prior format in order.
   Every step is idempotent and safe to resume after interruption.
4. Migration holds one application-home lock.
   It migrates or quarantines cache state, writes `cache/layout.yml`, verifies the
   result, and atomically replaces `config.yml` last.
   The durable config write is the publish step.
5. A config/cache marker mismatch is diagnosed explicitly.
   Normal mutations stop until repair either completes the migration or restores the
   last complete layout.
6. Purely additive fields do not require a format bump once all schemas preserve unknown
   keys. Renames, removals, semantic changes, and incompatible directory changes do.

Machine-owned record types use independent schema IDs, such as `repo-f01` and
`github-pr-f01`. A provider-record change should not force an application-home migration
when that record can be refreshed or invalidated independently.

## Repository Entry Format

`repo.yml` is machine-owned and written atomically.
Its initial shape is:

```yaml
format: repo-f01
id: sha256:<full-source-identity-digest>
slug: github-com--pallets--flask--7d5c1a2e4b90
source:
  display_url: https://github.com/pallets/flask
  clone_url: https://github.com/pallets/flask.git
  provider: github
git:
  object_format: sha1
  default_branch: refs/remotes/origin/main
  active_revision: <full-object-id>
  clone_strategy: blobless
  object_state: backfilling
created_at: <RFC-3339 timestamp>
last_opened_at: <RFC-3339 timestamp>
last_fetch_at: null
pending_revision: null
```

The source URLs are credential-free.
Timestamps are UTC. Object IDs are full SHA-1 or SHA-256 IDs, never branch names.
The record is beside `gitroot` so it is not served as repository content and survives
replacement of the working tree.

Clone publication uses `cache/staging/<operation-id>/` on the same filesystem.
The cache manager validates the checkout, verifies `HEAD`, writes `repo.yml`, and only
then renames the complete entry into `repos/`. Per-source locks prevent duplicate
clones. Purge moves an entry to a recoverable trash location before deletion and reports
exactly what it will remove.

## URL and Source Resolution

Phase 1 accepts:

- `https://host/owner/repo` and a terminal `.git`
- `ssh://user@host/owner/repo.git`
- SCP-like `git@host:owner/repo.git`
- GitHub repository pages with query strings or fragments, after removing presentation
  decorations

The current CLI annotates `root` as `Path | None`, so Typer converts the value before
the command body and collapses `https://` into path syntax.
Phase 1 changes that command boundary to `str | None`. Mode validation and URL
classification run on the original string; modes that require a local path construct and
resolve `Path` only after remote source resolution has declined the input.
This ordering is part of the CLI contract, not an implementation detail left to
`run_serve`.

Inputs beginning with `-`, containing credentials, using unknown schemes, or resolving
to Git helpers such as `ext::` are rejected before Git sees them.
The clone command also sets `protocol.allow=never` and explicitly enables only the
supported transports.

Repository-root GitHub URLs are core inputs because they are ordinary clone sources.
GitHub tree, blob, commit, issue, and pull-request URLs are provider inputs.
Phase 1 may reject them with a message naming the repository URL; later phases resolve
them to a repository entry plus a provider or Git navigation target.

Local paths keep their existing behavior.
A later acquisition phase may create reference clones for local repositories when a
provider or comparison needs an isolated object store, as the general diff plan
describes.

## Acquisition, Refresh, and Git Execution

The initial acquisition remains blobless clone followed by background backfill:

```text
resolve source → lock identity → clone to staging → validate → publish → serve
                                                        └→ background backfill
```

Phase 0 remeasures this strategy against the current history and diff routes.
If a full clone is faster for a measured small-repository class, the selected strategy
is recorded in `repo.yml`; a hidden heuristic does not choose without evidence.

All Git work continues through `metabrowser.git.process.run_git`. The runner gains
explicit execution policies rather than a second wrapper:

- request policy: the existing short timeout and response-size cap
- acquisition policy: clone-scale timeout and bounded progress capture
- background policy: server-lifetime ownership, cancellation, and cleanup

Every policy keeps fixed arguments, no shell, capped output, child reaping, and scrubbed
repository-pinning environment variables.
Acquisition also uses `stdin=DEVNULL`, `SSH_ASKPASS_REQUIRE=never`,
`GCM_INTERACTIVE=never`, SSH batch mode, and disabled Git terminal prompts.
User Git config and credential helpers remain available; Metabrowser does not read their
secrets.

The clone disables submodule recursion, hooks, automatic maintenance, unsafe transports,
and symlink materialization.
`.git` is excluded from serving.
Git version and partial clone capability are recorded.
A failed backfill leaves the entry usable online and honestly marked partial; it does
not convert a successful open into a fatal error.
Fallback to a full clone is a pre-publication strategy decision for an unsupported Git
version or a remote that rejects partial clone.
Once a blobless entry is published, a later backfill failure is retried or reported as
partial; it never replaces a live entry with an in-place full clone.

Refresh is one coordinated job with separately reported stages:

1. fetch and prune Git remote refs;
2. continue or retry object backfill when needed;
3. ask enabled provider plugins to refresh their metadata conditionally;
4. fetch any provider refs required by selected provider objects;
5. atomically update machine-owned records and publish one result summary.

A failure in one provider does not roll back a successful Git fetch, and the UI does not
report the whole refresh as successful when any requested stage failed.

## GitHub Provider Direction

GitHub support is a later built-in plugin over the provider cache contract.
It may use the GitHub API for repository metadata, pull requests, checks, and review
conversations. Content, commit graphs, and diffs continue to come from Git.

A cached pull-request envelope can begin with:

```yaml
format: github-pr-f01
repository_id: github:<stable-provider-id>
number: 123
fetched_at: <RFC-3339 timestamp>
etag: <HTTP validator or null>
base_revision: <full-object-id>
head_revision: <full-object-id>
merge_revision: <full-object-id or null>
data: {}
```

The exact `data` schema is deferred until the first PR view is designed.
The envelope establishes the invariants that matter now: stable identity, freshness,
conditional refresh, and immutable Git references.
Tokens remain in `gh` or the operating-system credential store and never enter YAML.

The plugin stores records under `<entry>/github/pull-requests/`, registers
GitHub-specific tabs and views, and asks the core cache service to fetch
`refs/pull/<n>/head` and `/merge` into a Metabrowser-owned ref namespace.
A refresh button runs the coordinated job above.
A PR view renders through the existing File Diff Format and diff plugin, then layers
mutable provider state such as title, checks, and review threads around that comparison.

## Security and Trust

A remote repository is third-party content.
URL-opened entries automatically use the untrusted profile and never expose edit
capabilities. This remains a release blocker for the URL-to-serve phase, even though
cache and clone components can land earlier.

Repository files cannot configure the host application.
App config and provider records are outside `gitroot`; a fetched
`.metabrowser/config.yml` is ordinary browsed content.
The existing safe-path and no-follow traversal rules remain mandatory, with
`core.symlinks=false` as defense in depth.

Clone inputs are untrusted.
The transport allowlist, option separator, no-prompt environment, timeouts, output caps,
no submodules, disabled hooks, patched-Git floor, and atomic publication are part of the
security boundary.
Provider responses are also untrusted: their YAML records are bounded,
schema-validated, and rendered through text or sanitized view components.

## Product and CLI Surface

The first phases add:

```shell
metab https://github.com/owner/repo    # clone or reuse, then serve immediately
metab --repos                          # list cached repositories
metab --repo-refresh <repo>            # fetch Git and enabled provider metadata
metab --repo-purge <repo>              # dry-run first; explicit removal
```

Implementation will select option names in the flat CLI’s declarative mode table, which
owns conflicts and help text.
The command contract is fixed: list reports identity, source, active revision, object
state, size, last open, and last refresh; refresh reports each stage; purge names the
exact entry and recoverability window.

The future repository chooser consumes the same catalog.
It opens the active `gitroot` without network access, shows refresh state separately,
and can promote recent or favorite repositories without inventing a second index.

## Phased Implementation Plan

### Phase 0: Revalidate and freeze the contracts

- [ ] Remeasure full, blobless, and blobless-plus-backfill acquisition against the
  current v0.8 history list, commit summary, comparison manifest, and deferred patches.
- [ ] Record the `f01`, `repo-f01`, source-identity, slug, and YAML field-order
  contracts as typed models and golden fixtures.
- [ ] Decide the supported HTTPS and SSH URL grammar and the patched-Git floor.
- [ ] Define the home lock, entry lock, staging, quarantine, and recoverable purge state
  transitions, including interruption at each publication boundary.
- [ ] Update the architecture map when repository acquisition registers a route, view,
  or new root-resolution surface.

### Phase 1: Versioned home and reusable repository cache

- [ ] Add the application-home resolver, `config.yml`, `cache/layout.yml`, format
  history, fail-closed compatibility check, and sequential migration harness.
- [ ] Add source normalization, full identity digest, readable uniquified slug, and
  collision verification.
- [ ] Extend `git/process.py` with version detection, `stdin=DEVNULL`, the complete
  non-interactive environment, and explicit request/acquisition/background policies.
- [ ] Add clone-to-staging, validation, atomic entry publication, `repo.yml`, and exact
  cache-hit reuse.
- [ ] Resolve URL roots before the existing serve path and report both display URL and
  local cache identity without leaking the cache path to browser error bodies.
- [ ] Change the CLI root boundary from `Path | None` to `str | None`; prove in goldens
  that URL spellings remain byte-for-byte intact until source normalization and that
  path-only modes still receive resolved `Path` values.
- [ ] Start backfill after serving and persist honest object state.
- [ ] Force the untrusted profile for URL-opened roots once `mb-vib1` lands.
- [ ] Add CLI goldens and documentation for first open, cache hit, failure, and offline
  reuse.

### Phase 2: Catalog, refresh, and cache management

- [ ] Build one catalog by scanning validated `repo.yml` records; no central mutable
  index is required for correctness.
- [ ] Add list, inspect, refresh, and recoverable purge commands.
- [ ] Add coordinated refresh jobs with stage-level progress, cancellation, and partial
  failure reporting.
- [ ] Fetch refs without mutating `gitroot`; stage an updated checkout separately and
  promote it only when no live session holds the entry.
- [ ] Add size accounting and measurements before choosing automatic eviction defaults.
- [ ] Add `CACHEDIR.TAG` and exclude cache data from backup tools that honor it.

### Phase 3: In-app repository chooser and switching

- [ ] Add a repository chooser over the catalog with recent, favorite, offline, partial,
  and refresh states.
- [ ] Make root selection session-scoped so switching repositories does not require a
  second cache model or an unsafe mutation of global settings.
- [ ] Preserve each repository’s selected path, Git scope, and revision navigation state
  as bounded client state.
- [ ] Measure first paint on a warm cache hit and keep the chooser off the eager asset
  path unless its measured use justifies prefetching.

### Phase 4: Provider cache and GitHub metadata

- [ ] Define the provider cache interface, bounded YAML envelope, conditional refresh,
  and provider namespace allocation.
- [ ] Add a GitHub built-in plugin that discovers GitHub repository identity without
  changing provider-neutral cache identity.
- [ ] Fetch repository and pull-request summaries with HTTP validators, writing records
  atomically and never storing credentials.
- [ ] Fetch selected PR refs into a Metabrowser-owned ref namespace and resolve every
  cached base, head, and merge revision to a full object ID.
- [ ] Add GitHub tabs or views through plugin contribution points, with explicit
  loading, stale, offline, and refresh states.

### Phase 5: Pull-request reading

- [ ] Render PR comparisons through the existing Git adapter, File Diff Format, and diff
  plugin.
- [ ] Add provider metadata around the comparison: title, author, state, checks, and
  freshness first; review conversations only after their anchor model is specified.
- [ ] Render changed Markdown at the PR head revision through the existing revision
  content path.
- [ ] Keep GitHub conversation writes out of scope until read-only refresh and caching
  are stable.

### Phase 6: Very large repositories

- [ ] Revisit shallow-plus-progressive-deepening only for repositories whose measured
  acquisition cost justifies the added state model.
- [ ] Mark truncated history and disable blame while `.git/shallow` exists.
- [ ] Coordinate deepening with the unbounded-history session design rather than adding
  a second pagination model.

## Testing Strategy

The ordinary suite uses local `file://` fixture repositories and an isolated
`METABROWSER_HOME`; no test requires the network or a real user credential store.
The test acquisition policy explicitly enables the `file` protocol for those fixtures.
Production policy cannot select that override and continues to allow only the supported
HTTPS and SSH transports.

- **Format and migration:** old config migrates step by step and idempotently; a future
  format fails before any write; unknown keys survive; interruption before and after the
  cache-layout and config publication points recovers deterministically.
- **Identity:** equivalent forms covered by an explicit normalization rule reuse one
  entry; non-equivalent forms do not; a forced short-digest collision extends the slug;
  credentials and unsafe schemes are rejected.
- **Publication:** an interrupted clone never appears under `repos/`; metadata and HEAD
  must agree before rename; a cache hit performs no clone and needs no network.
- **Read-only behavior:** opening and Git refresh leave `git status --porcelain` empty
  and `active_revision` unchanged; an externally dirtied entry is reported rather than
  reset.
- **Concurrency:** two opens of one source share the completed entry; clone, refresh,
  promotion, purge, and format migration cannot race across processes.
- **Git integration:** cached roots satisfy repository-root discovery, history, direct
  revision routes, commit summaries, and bounded diff rendering before and after
  backfill.
- **Trust:** URL roots always resolve the untrusted capability set, never serve `.git`,
  and cannot treat repository-local metadata as host config.
- **Provider boundary:** GitHub fixtures are schema-validated, conditionally refreshed,
  atomically replaced, bounded, and linked to full object IDs; provider failure does not
  corrupt Git refresh state.
- **Distribution:** the installed wheel contains the config schemas, migrations, and
  provider plugin assets, and `make verify` remains the handoff gate.

## Rollout and Compatibility

Cache formats and acquisition components can land while the untrusted-profile dependency
is open. The URL-to-serve path is enabled only when remote roots can be forced into that
profile. Local path behavior does not change.

`f01` is the first released application-home format, so there is no speculative legacy
reader. Once released, later incompatible changes add exactly one sequential migration
and an explicit format-history entry.
A future-format client error names the found and supported formats and the Metabrowser
upgrade action.

Cache records are recoverable data, but purge is not the default migration strategy.
When a record can be refreshed, quarantine the old form until the replacement is valid.
When the source is offline or gone, retain the last readable `gitroot` and report that
metadata needs repair.

## Open Decisions

- Whether the Phase 1 application home should follow platform directories by default or
  use the predictable cross-platform `~/.metabrowser/` path requested here.
- Whether the initial refreshed checkout is promoted only on the next open or may ask a
  live session to switch roots after staging completes.
- The measured threshold, if any, below which a full clone beats blobless plus
  background backfill.
- Whether SSH and HTTPS aliases for the same non-GitHub source should be user-configured
  or remain separate cache identities.
- The provider-record fields needed for the first GitHub PR summary view.
  The envelope and Git object references are fixed; the mutable presentation payload is
  not.
- Whether automatic eviction belongs in `f01` after measurement or should remain a later
  additive config block.

## Acceptance Criteria for the First Usable Phase

- `metab <supported-repository-url>` publishes one validated entry under
  `~/.metabrowser/cache/repos/<uniquified-slug>/gitroot` and serves it under the
  untrusted profile.
- Repeating the command opens the cached root without cloning, fetching, or requiring
  network access.
- The cache record names a credential-free source identity and full active revision; the
  working tree is clean and is never mutated by browsing or ref refresh.
- An interrupted clone, concurrent clone, future-format config, corrupt record, unsafe
  URL, missing credential, and offline backfill each produce a bounded, actionable, and
  truthful outcome.
- The existing Files, Git history, direct revision, commit summary, and diff views work
  against the cached root with the same contracts as a local repository path.
- Config and cache layout begin at `f01`, preserve unknown fields, migrate atomically,
  and fail closed on future formats.
- List and purge can identify the exact entry without a central index, and purge never
  removes a live or ambiguously resolved repository.

## References

- [Repository cache and open from a Git URL](../../research/research-2026-08-11-repo-cache-and-git-url-open.md)
  — acquisition measurements, prior art, and the dated research record
- [Git graph view](plan-2026-08-06-git-graph-view.md) — shipped Git history and the
  repository-root boundary
- [General diff rendering](plan-2026-08-17-general-diff-rendering.md) — comparison model
  and one acquisition workflow
- [Git revision navigation performance](plan-2026-08-25-git-revision-navigation-performance.md)
  — current revision loading and comparison behavior
- [Unbounded virtualized Git history](plan-2026-08-25-unbounded-virtualized-git-history.md)
  — future history continuation and virtualization
- [HTML rendering and trust model](plan-2026-08-06-html-rendering-and-trust-model.md) —
  untrusted-content dependency
- [tbd on-disk format versioning](https://github.com/jlevy/tbd/blob/v0.8.1/docs/tbd-format-versioning.md)
  — reviewed model for fail-closed formats and ordered migration publication

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
