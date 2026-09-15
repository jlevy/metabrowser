# Hosted Review Model and Provider Boundary

**Status:** Proposed for the v0.11.0 GitHub-first slice.
No hosted-review format, provider adapter, route, or view is implemented yet.

Hosted review is a domain above Git history and File Diff Format.
A pull request or merge request has Git endpoints and can produce a comparison, but it
also has a lifecycle, participants, reviews, threads, checks, merge state, and provider
freshness that neither Git nor a patch can express.

The first adapter targets GitHub.
The durable model remains provider-neutral so a future GitLab adapter can produce the
same documents without teaching views about GitHub or weakening the contracts into
provider payloads.

## Layers

```text
GitHub API and refs                 future GitLab API and refs
          │                                      │
          ▼                                      ▼
GitHub provider adapter                 GitLab provider adapter
          │                                      │
          └──────────────┬───────────────────────┘
                         ▼
              Hosted Review Format
        repository, change request, review,
         thread, comment, checks, freshness
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
 Repository Activity Format   Hosted-review views
 commits and change requests  summary and discussion
              │                     │
              └──────────┬──────────┘
                         ▼
       Git history, File Diff Format, and
               revision-content views
```

The dependency direction only points down.
Provider adapters may produce hosted-review documents and ask the repository service to
fetch selected refs.
Hosted-review views may resolve a document’s comparison reference through File Diff
Format. Git, diff, inventory, and the shell never import a GitHub model.

Repository and branch opening sit below this diagram.
A provider URL reducer may turn a GitHub web URL into a generic clone source plus a
selection, but the repository library resolves the branch to a full object ID and owns
any detached materialization.
The provider adapter is not required to browse repository content or branches.

## The Clean Format Boundary

Hosted Review Format is a closed, versioned, tool-neutral contract with the same
discipline as File Diff Format:

- deterministic schema and conformance fixtures;
- structural and semantic validation in both producer and consumer implementations;
- explicit identity, completeness, partiality, freshness, and unavailable states;
- immutable observations and atomic current-manifest pointers;
- no raw provider response, open extension mapping, or renderer-only field; and
- provenance that names the provider and retrieval without making its transport shape
  part of the domain model.

The format uses SoftSchema conventions so the Python producer, browser consumer, CLI
inspection path, and future provider adapters share one compiled structural contract.
Contract IDs name provider-neutral payloads, schemas ship with the hosted-review plugin,
and the host registry outranks any schema path found in cached content.
The first corpus may move from `permissive` to `enforced` while the producer and
consumer are developed together; v0.11.0 does not publish a contract until undeclared
fields fail consistently in both runtimes.

The v0.11.0 record set is deliberately PR-first:

| Record | Describes | Does not contain |
| --- | --- | --- |
| `HostedRepository/v1` | Provider-neutral repository identity, coordinates, URLs, visibility, default branch, and timestamps | Git objects or an API response |
| `ChangeRequestIndex/v1` | A bounded, paginated discovery list with query, freshness, completeness, and cursors | Full bodies, reviews, threads, checks, or fetched refs |
| `ChangeRequest/v1` | A pull or merge request’s identity, lifecycle, participants, labels, base/head, merge readiness, and aggregate state | Patch bodies or transport pagination |
| `ChangeRequestComment/v1` | One top-level conversation comment, author, timestamps, visibility state, and human URL | A diff anchor or rendered HTML as authority |
| `Review/v1` | One review act, its normalized disposition, and an optional reader-facing summary body | Provider-specific review payload |
| `ReviewThread/v1` | A bounded discussion anchored to an immutable comparison identity | A guessed current line |
| `ReviewComment/v1` | One comment, author, timestamps, state, and anchor | Rendered HTML as authority |
| `Check/v1` and `CommitStatus/v1` | CI and status conclusions attached to an immutable revision | Git commit content |
| `ProviderSyncManifest/v1` | Exact snapshots, retrieval metadata, bounds, failures, and collection states in one published observation | Secret material or mutable object bodies |

Issue and timeline records are the next domain extension, tracked by `mb-9rrc`.
Stacked-change projections are later derived records, tracked by `mb-glxc`. They extend
the registry with closed contracts; they do not add an `extra` object to the v0.11.0
records.

### Artifact profiles

`ChangeRequest/v1`, `ChangeRequestComment/v1`, `Review/v1`, and `ReviewComment/v1` use
SoftSchema’s `frontmatter-md` profile.
Their YAML envelopes hold every value software consumes: identity, lifecycle, actors,
timestamps, links, anchors where applicable, and bounded-collection membership.
The Markdown body is the reader-facing provider prose: the PR description, a top-level
conversation comment, an optional review summary, or an inline review comment.
No index, route, or view parses prose or tables from it to recover structured values.

This makes one cached PR both application data and an ordinary document.
The Markdown plugin can render the description under the untrusted-content profile,
while the hosted-review plugin composes validated metadata, review state, navigation,
and the resolved File Diff Format around it.
The serializer uses frontmatter-format’s fenced Markdown writer, preserves the provider
body as content, and computes snapshot identity from the complete normalized artifact.

Indexes, sync manifests, retrieval records, tombstones, threads, checks, and status
records use `pure-yaml` because their entire content is structured or they only refer to
a separately stored comment artifact.
A later issue artifact may use `frontmatter-md` for the same reason as a change request;
that decision belongs to `mb-9rrc` and does not alter the v0.11.0 PR contract.

## Provider Identity Without Provider-Shaped Views

Every durable object carries a `ProviderObjectRef` with:

- provider kind, such as `github`;
- provider instance, so public GitHub and an enterprise host do not collide;
- provider object kind and stable opaque ID;
- repository identity and repository-local number where applicable; and
- canonical human URL.

Every provider observation also carries a stable `AuthorizationContextRef` in its
retrieval record and sync manifest: provider instance, `anonymous` or `authenticated`
mode, a stable opaque principal ID for authenticated publications, and an optional
normalized capability-partition fingerprint only when those capabilities change which
objects the principal may observe.
Display login, observed scopes or capabilities, and observation time are retrieval
observations, not authorization-context identity.
Neither record carries a token, credential-store path, environment-variable value, or
command output.
An authenticated adapter that cannot resolve a stable opaque principal ID
returns a typed authorization-unavailable state instead of publishing into a shared
authenticated namespace.
Current pointers are scoped by an opaque digest of only the stable context fields so
repeat observations for one principal advance together, while validators and a
permission denial from one principal cannot overwrite another principal’s view.
A last-known observation from another context may be shown only as an explicit offline
fallback labeled with the context that fetched it; it is never treated as fresh or used
to infer deletion.

Normalized lifecycle values use the hosted-review vocabulary.
When GitHub returns a new enum value, the adapter maps it to `unknown` and may retain
the bounded original value in a declared provenance field.
When a GitHub concept has no honest provider-neutral meaning, it receives a closed
GitHub companion record with a named producer and consumer; it does not enter an opaque
extension bag or distort the common contract.

This boundary is reusable without pretending all hosts are identical.
The future GitLab adapter (`mb-51uj`) is a named consumer that justifies neutral
identity and lifecycle terms.
It does not justify fields for GitLab behavior that the implementation has not yet
measured.

## Activity Is a Projection, Not a Second History Authority

Repository Activity Format is a bounded view model over references to source records.
It lets the existing history navigation pattern present commits, change requests, or a
grouped combination without making a PR look like a commit.

Each activity item contains only what a paginated history surface needs: stable item
identity, kind, title, actors, event and update times, concise state, primary revision,
optional base/head revisions, comparison capability, detail target, and source
freshness. The full change-request document remains the authority for review state and
discussion; the Git history session remains the authority for commit ordering and graph
lanes.

Adapters project existing sources into this format:

- the Git history adapter projects commit summaries without changing `/api/git/log`;
- the hosted-review adapter projects `ChangeRequestIndex/v1` rows; and
- a composition service may group or interleave pages only when it can state a stable
  ordering and honest continuation rules.

The initial v0.11.0 view may use separate Commit and Pull Request groups if a stable
mixed cursor would require unbounded reads.
Shared view mechanics do not require a fabricated global order.

## Navigation Containers and Panels

The hosted-review plugin registers a Pull Requests nav panel backed by the bounded
`ChangeRequestIndex/v1`, not by DOM rows or live API data.
It reuses the proven Git-history interaction structure: paged loading, virtualization,
roving selection, explicit loading and stale states, and deterministic restoration.

The collection and its entries use the existing item-like/folder-like roles:

- **Pull Requests collection:** a virtual folder-like root whose children are cached
  change-request summaries; its overview reports query, freshness, completeness, offline
  state, and refresh diagnostics.
- **Change-request row:** item-like because selection opens the PR document and views;
  folder-like because expansion reveals its changed files after the selected bundle and
  comparison manifest are available.
- **Changed-file row:** an ordinary comparison child that opens the shared Diff view and
  the existing base/head revision-content views.

Rows may show only the compact values the index contract guarantees: PR number, title,
author, draft/open/merged/closed state, base and head labels, and updated time.
Description, review and check summaries, full review details, threads, and file changes
remain in the selected bundle and load only after selection.
Counts and folder visibility come from the complete bounded index model, never from the
currently mounted page.

The initial panel may group open, draft, merged, and closed entries or expose a query
control, but the selected query and its bounds are part of the index identity.
Changing the filter cannot relabel a cached page as though it answered another query.

## View and Plugin Ownership

All hosted-review UI consumes clean formats, never a GitHub response:

- a provider plugin recognizes URLs, authenticates, acquires provider data, normalizes
  it, and publishes snapshots;
- a hosted-review plugin validates the common documents and owns activity, repository,
  change-request, review, thread, and status projections;
- the diff plugin renders the resolved comparison as File Diff Format;
- existing revision-content views render a changed file at base or head; and
- the shell supplies routing, plugin mounting, navigation containers, and lifecycle, but
  no provider schema or renderer.

A GitHub-only badge or action belongs to a GitHub companion view registered by the
provider plugin. The common hosted-review renderer neither branches on
`provider == "github"` nor reads provider-specific fields.

The host discovers provider adapters through a closed capability registry.
An installed plugin declares a `ProviderAdapterSpec` with its provider and instance
claims plus a trusted factory callable.
Discovery rejects duplicate claims; application lifespan constructs adapters with only
provider-neutral repository, job, clock, and storage ports and awaits cancellation and
`close()` during root replacement and shutdown.
No server, cache, route, or renderer imports the GitHub adapter.

For v0.11.0, the provider port has one implementation: `gh api` behind the GitHub
adapter (`mb-p4sw`). The port owns repository resolution, auth diagnosis, one bounded
index page, selected PR acquisition, reviews/checks, and rate-limit observations.
It does not expose command output or GitHub response dictionaries to the format or view
layers. A later direct-HTTP or GitLab implementation may satisfy the same port without
changing the stored contracts or renderers.

## Ports and Addresses

Four provider-neutral ports keep URL parsing, acquisition, addressing, and rendering
independently replaceable:

- `ProviderUrlReducer.reduce(raw_url)` returns `NotApplicable`, `Reduced`, or
  `Rejected`. Each reducer declares the schemes and hosts it claims.
  Exactly one reducer may claim an input; overlapping scheme/host claims fail plugin
  discovery, and `Rejected` is terminal rather than falling through to another parser.
  `Reduced` carries a credential-free Git clone source plus a `RepositorySelection`. A
  selection may name ref/path candidates, a line range, or a provider object target.
  GitHub implements the first reducer; the cache only sees its output.
- `HostedReviewProvider` returns common repository, change-request, review, check, and
  index records plus typed retrieval outcomes.
  `GitHubGhAdapter` implements it through `gh api`; no route or renderer imports the
  adapter.
- `AddressSpaceSpec` declares a browser prefix plus its parser, formatter, selection
  application, preview claim, startup, popstate, root-replacement, and disposal hooks.
  The shell arbitrates address ownership before startup, refuses reserved or duplicate
  claims, and uses the same spec for href generation, browser navigation, and
  `metab --show`.
- the core repository service accepts a source or entry identity and an explicit ref,
  then returns a leased `RepositoryOpenTarget` pinned to a full Git object ID. Provider
  plugins may request selected PR refs through this port but cannot run Git or receive a
  cache filesystem path.

The common hosted-review plugin owns `/review/<provider>/<repository-key>/<change-key>`
and its resource routes through a mounted plugin sub-router.
The address identifies a provider-neutral record; GitHub’s `/pull/<number>` reducer
resolves to it.
The bounded index and a direct URL must produce the same record identity,
so navigation never needs an index-specific route.

Mounted routers and browser address spaces are separate plugin-host capabilities, not
hosted-review exceptions.
Each installed plugin declares a validated mount and router callable for HTTP plus an
`AddressSpaceSpec` for browser navigation; the host preserves methods, streaming,
headers, and honest status codes while the address owner controls parse/format/apply and
mounted-preview lifecycle.
Exact data hooks remain the smaller surface for one-segment model endpoints.
Operator-directory plugins remain JavaScript-only, and all mounted state has a shutdown
and root-replacement path.

## Cache Lifetimes

Four caches remain distinct:

1. the repository library durably owns Git objects and the pinned serving root;
2. the provider store durably owns immutable hosted-review snapshots and current
   manifests;
3. transient projections are owned by the subsystem that materializes them: the
   repository service owns detached Git worktrees and the archive plugin owns extracted
   trees, each keyed by immutable object identity and protected by leases; and
4. activity pages, diff manifests, file patches, and browser projections are bounded,
   recomputable session caches.

Only the second layer is the cache of PR-domain state.
It references the first by object ID, may use the third to serve filesystem content, and
never promotes the fourth into a released on-disk contract.
Review anchors are domain data in the second layer, not materialized bytes in the third.
Low-level lease or safe-path helpers may be shared only after two concrete owners prove
the same contract; ownership and reclamation remain explicit per projection type.

Provider publication has two independent axes.
A sync transaction is `staged`, `committed`, or `failed`; each collection inside a
committed manifest is separately `not_requested`, `partial`, `complete`, or
`unavailable`. An interrupted, invalid, or failed transaction cannot move a current
pointer. A structurally valid partial observation may become the newest current
observation so the UI can report what was observed, while a separate `last-complete`
pointer preserves the newest complete fallback.

Index observations also declare remote consistency: `provider_snapshot` when one
provider snapshot token covers every page, `best_effort_window` when pages were fetched
against moving state, or `unknown` when the provider cannot prove either.
They record first and last observation times, stable sort and tie-break rules, per-page
provenance, and deduplication by stable provider ID. `complete` means the provider
reported the requested query exhausted before any item, page, byte, or time bound was
hit. Hitting a bound yields `partial` plus its truncation reason and continuation.
Index completeness never means that separately hydrated PR resources are complete.

Provider storage uses a fixed lock order:

1. the application-home lock only for layout migration and global sweeps;
2. the repository-entry lock for entry purge, ref mutation, and object-database work;
3. a provider/resource lock for binding, staged publication, current-pointer changes,
   and provider reclamation.

No network process runs while any of those locks is held.
Publication reacquires the entry lock and then the provider/resource lock, revalidates
the entry lease and authorization context, then moves the manifest and pointer
atomically. Readers hold snapshot leases so reclamation cannot remove an object they are
serving. The provider store retains current, `last-complete`, one bounded diagnostic
predecessor, and any explicit archival pin regardless of source availability; it sweeps
older unreachable objects but never automatically removes the last validated reachable
observation.

All application-home directories containing repository or provider content are
owner-only: `0700` directories and `0600` files on POSIX, with the equivalent
current-user-only ACL on Windows.
Metabrowser refuses remote acquisition when a cache ancestor is a symlink, is owned by
another principal, is group/world accessible, or cannot be verified and repaired.
This refusal does not prevent read-only browsing of an ordinary local path outside the
application home.

## Acceptance Rules

The first GitHub slice is complete only when:

- GitHub API fixtures normalize into provider-neutral records before any view consumes
  them;
- no common record, route, or hosted-review renderer contains a GitHub-only field or
  branches on GitHub;
- a bounded PR index and a directly addressed PR both produce the same
  `ChangeRequest/v1` identity and selected bundle;
- top-level conversation comments and diff-anchored review comments remain distinct
  artifacts, and anchors cover file-level, single-line, and range forms without
  inventing a line;
- list acquisition fetches no PR Git refs, while selection fetches only the requested
  base, head, and optional merge refs;
- any advertised and authorized branch opens at its resolved full object ID through a
  leased materialization without changing the entry’s pinned root;
- a change request opens the same File Diff Format renderer as a commit comparison,
  while its review, check, thread, merge, and freshness details remain available in the
  hosted-review document and views;
- offline reuse preserves the last validated complete or explicitly partial provider
  observation; and
- every browser-consumed hosted-review record passes the packaged browser validator;
- hostile provider strings remain text or untrusted Markdown and provider links accept
  only validated HTTPS URLs; and
- every new format, route, persisted state, address lifecycle, and functional
  interaction appears in the architecture map and exact production-path goldens.

## Decisions for This Design Review

This design PR asks reviewers to accept or reject these boundaries before
implementation:

1. `ChangeRequest`, not GitHub Pull Request, is the durable common domain object; the
   provider-native kind remains explicit provenance.
2. `ChangeRequest/v1`, `ChangeRequestComment/v1`, `Review/v1`, and `ReviewComment/v1`
   are enforced SoftSchema `frontmatter-md` artifacts: YAML is the machine authority and
   the Markdown body is the untrusted provider prose, optional for a review summary.
3. Hosted Review Format, Repository Activity Format, Git, File Diff Format, and revision
   content stay separate and compose through references rather than a union document.
4. A hosted-review plugin owns common models and views; a GitHub provider plugin owns
   URL recognition, `gh api`, auth, normalization, and GitHub-only companion records.
5. The Pull Requests nav panel is a virtual folder-like collection backed by a bounded
   cached index; a selected PR is also a folder-like change container.
6. Durable Git objects, durable provider snapshots, transient materialization, and
   recomputable session caches have different owners and retention rules.
7. `gh api` is the only v0.11 transport, behind a provider port that can later support a
   direct GitHub or GitLab adapter without changing formats or views.
8. Provider URL reducers and mounted plugin routers are general host capabilities;
   GitHub URL syntax and hosted-review routes remain plugin-owned.
9. Direct PR acquisition and viewing ship before the bounded PR index and virtual nav
   collection; discovery is additive rather than a prerequisite for addressing.
10. Provider observations and validators are scoped by a non-secret authorization
    context; transaction state, collection coverage, and remote consistency are three
    separate claims.
11. Provider adapters and browser address spaces are general installed-plugin
    capabilities with duplicate-claim arbitration and awaited lifecycle, not implicit
    imports or router side effects.
12. Provider reclamation is reachability- and lease-based: current, last-complete, one
    diagnostic predecessor, and archival pins survive, while older unreachable objects
    remain bounded even for offline or deleted sources.

Implementation evidence still decides concrete page and collection bounds, exact REST
versus GraphQL queries, whether the initial activity panel groups commits and PRs or can
support an honest mixed cursor, and the measured physical snapshot layout.
Those decisions may tune cost and presentation; they may not collapse the accepted
format, plugin, identity, or cache boundaries.

The implementation plan and release scope live in
[Hosted Review Model and GitHub Provider](../specs/active/plan-2026-08-27-github-provider-and-pull-requests.md).
The lower layers live in
[Git and Comparison Sources](arch-git-and-comparison-sources.md) and
[File Diff Format v1](file-diff-format/file-diff-format.md).

## References

- [SoftSchema v0.8.1 guide](https://github.com/jlevy/softschema/blob/v0.8.1/docs/softschema-guide.md)
- [frontmatter-format](https://github.com/jlevy/frontmatter-format)
- [Nav Containers](arch-nav-containers.md)
- [Views, Models, and Routes](arch-views-models-routes.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
