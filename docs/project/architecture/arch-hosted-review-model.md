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
| `Review/v1` | One review act and its normalized disposition | Provider-specific review payload |
| `ReviewThread/v1` | A bounded discussion anchored to an immutable comparison identity | A guessed current line |
| `ReviewComment/v1` | One comment, author, timestamps, state, and anchor | Rendered HTML as authority |
| `Check/v1` and `CommitStatus/v1` | CI and status conclusions attached to an immutable revision | Git commit content |
| `ProviderSyncManifest/v1` | Exact snapshots, retrieval metadata, bounds, failures, and collection states in one published observation | Secret material or mutable object bodies |

Issue and timeline records are the next domain extension, tracked by `mb-9rrc`.
Stacked-change projections are later derived records, tracked by `mb-glxc`. They extend
the registry with closed contracts; they do not add an `extra` object to the v0.11.0
records.

### Artifact profiles

`ChangeRequest/v1` uses SoftSchema’s `frontmatter-md` profile.
Its YAML envelope holds every value software consumes: identity, title, lifecycle,
actors, labels, base/head refs, merge state, aggregate review/check state, freshness,
and links to bounded companion records.
The Markdown body is the provider’s PR description and remains reader-facing; no index,
route, or view parses prose or tables from it to recover structured values.

This makes one cached PR both application data and an ordinary document.
The Markdown plugin can render the description under the untrusted-content profile,
while the hosted-review plugin composes validated metadata, review state, navigation,
and the resolved File Diff Format around it.
The serializer uses frontmatter-format’s fenced Markdown writer, preserves the provider
body as content, and computes snapshot identity from the complete normalized artifact.

Indexes, sync manifests, retrieval records, tombstones, and compact review/check records
use `pure-yaml` because their entire content is structured.
A later issue artifact may use `frontmatter-md` for the same reason as a change request;
that decision belongs to `mb-9rrc` and does not alter the v0.11.0 PR contract.

## Provider Identity Without Provider-Shaped Views

Every durable object carries a `ProviderObjectRef` with:

- provider kind, such as `github`;
- provider instance, so public GitHub and an enterprise host do not collide;
- provider object kind and stable opaque ID;
- repository identity and repository-local number where applicable; and
- canonical human URL.

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

Rows may show compact values the index contract guarantees, such as PR number, title,
author, draft/open/merged/closed state, updated time, and bounded review/check summary.
Description, full review details, threads, and file changes remain in the selected
bundle and load only after selection.
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

For v0.11.0, the provider port has one implementation: `gh api` behind the GitHub
adapter (`mb-p4sw`). The port owns repository resolution, auth diagnosis, one bounded
index page, selected PR acquisition, reviews/checks, and rate-limit observations.
It does not expose command output or GitHub response dictionaries to the format or view
layers. A later direct-HTTP or GitLab implementation may satisfy the same port without
changing the stored contracts or renderers.

## Cache Lifetimes

Four caches remain distinct:

1. the repository library durably owns Git objects and the pinned serving root;
2. the provider store durably owns immutable hosted-review snapshots and current
   manifests;
3. container materialization temporarily owns worktrees or unpacked bytes; and
4. activity pages, diff manifests, file patches, and browser projections are bounded,
   recomputable session caches.

Only the second layer is the cache of PR-domain state.
It references the first by object ID, may use the third to serve filesystem content, and
never promotes the fourth into a released on-disk contract.

## Acceptance Rules

The first GitHub slice is complete only when:

- GitHub API fixtures normalize into provider-neutral records before any view consumes
  them;
- no common record, route, or hosted-review renderer contains a GitHub-only field or
  branches on GitHub;
- a bounded PR index and a directly addressed PR both produce the same
  `ChangeRequest/v1` identity and selected bundle;
- list acquisition fetches no PR Git refs, while selection fetches only the requested
  base, head, and optional merge refs;
- a change request opens the same File Diff Format renderer as a commit comparison,
  while its review, check, thread, merge, and freshness details remain available in the
  hosted-review document and views;
- offline reuse preserves the last validated complete or explicitly partial provider
  observation; and
- every new format, route, persisted state, and functional interaction appears in the
  architecture map and exact production-path goldens.

## Decisions for This Design Review

This design PR asks reviewers to accept or reject these boundaries before
implementation:

1. `ChangeRequest`, not GitHub Pull Request, is the durable common domain object; the
   provider-native kind remains explicit provenance.
2. `ChangeRequest/v1` is an enforced SoftSchema `frontmatter-md` artifact: YAML is the
   machine authority and the Markdown body is the untrusted provider description.
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
