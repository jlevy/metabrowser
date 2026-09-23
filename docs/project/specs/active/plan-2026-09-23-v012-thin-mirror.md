# Plan: v0.12 Thin Mirror for Git and GitHub Browsing

**Status:** Active design, decided 2026-09-23. It supersedes the remaining v0.12 phases
in [Open Repositories from Git URLs](plan-2026-08-11-open-repo-from-git-url.md) (2A
onward) and
[GitHub Provider and Pull Requests](plan-2026-08-27-github-provider-and-pull-requests.md)
wherever they disagree.
Those documents stay as background, and their built foundation (Phases 0–1B) stays as
built until the simplification PR below changes it.

## Goal

Paste a GitHub repository, file, commit, or pull-request URL and browse it the way the
GitHub web interface shows it: code, history, commits, diffs, and a pull request’s
description, conversation, reviews, checks, and changed files.
Everything is served from a local mirror, so a page that was seen once opens instantly,
keeps working offline, and refreshes itself in the background.

Metabrowser is a thin, flexible wrapper.
Git and `gh` own the data and the credentials.
Metabrowser decides where mirrors live, turns URLs into what to show, keeps the mirror
fresh without making anyone wait, and renders it.

## Principles

- **Git and `gh` do the work.** Metabrowser runs `git` and `gh` with fixed arguments and
  an isolated environment, and never reimplements what they already do: transport,
  authentication, ref updates, object storage.
- **The cache is a mirror, nothing more.** One bare clone per repository, updated with
  plain `git fetch`. Metabrowser invents no branches and no private refs; the only refs
  it adds are GitHub’s own `refs/pull/<n>/head`, fetched on demand.
- **Read-only.** There are no working trees and no local changes.
  Every view is pinned to a full commit ID, so a moving branch never changes a page
  under a reader.
- **Nothing is deleted in v1.** Garbage collection and pruning of objects stay off, so a
  commit that was ever shown stays readable, even after a force-push upstream.
- **Seamless caching.** A cached page opens from the mirror without touching the
  network. If its data is older than a short freshness window, one background refresh
  runs, and the page updates when it finishes.
  Only a first visit waits.
- **`gh` owns GitHub authentication.** Public repositories need no credentials.
  A private fetch runs with `gh` as the only credential helper for that one command, and
  API data comes from `gh api`. No token ever enters a Metabrowser process.
- **Internal extension points, no public SDK yet.** A small host interface lets GitHub
  support live in one module and another host follow later.
  Core code does not branch on GitHub.
- **Acquired content is untrusted.** The forced untrusted profile from the foundation
  applies to every mirrored page.

## Architecture

```
URL ──> host resolver ──> Target(repo, rev?, path?, line?, pr?)
                               │
          ┌────────────────────┴───────────────────┐
          v                                        v
   Git mirror (git)                       Hosted records (gh api)
   clone / fetch / refs/pull/<n>          PR, reviews, comments, checks
          │                                        │
          └──────────> pinned views <──────────────┘
                 existing routes, renderers, CLI parity
```

| Layer | Owns | Built on |
| --- | --- | --- |
| Host resolver | URL grammar, clone URL, what a URL points at | One module per host; GitHub first |
| Git mirror | Clone, fetch, ref and path resolution, freshness | `git`, the existing process boundary |
| Hosted records | Pull-request data as validated JSON records | `gh api`, Pydantic models |
| Views | Code, history, commits, diffs, PR pages | Existing routes, `GitRevisionSubject`, renderers |

### Host resolver

`resolve_url(url) -> Target | Refusal` is an internal function backed by a small `Host`
interface: `claims(url)`, `parse(url)`, `clone_url(target)`, and
`fetch_pull_request(target)`. GitHub (github.com only for the alpha) is the one built-in
host. A plain `https://` or `file://` Git URL needs no host module and opens its default
branch.

GitHub URL shapes, reduced to a `Target`:

| URL | Target |
| --- | --- |
| `github.com/<o>/<r>` (and `.git`) | repository, default branch |
| `…/tree/<ref-and-path>` | ref and directory |
| `…/blob/<ref-and-path>[#L10-L20]` | ref, file, and line range (`?plain=1` kept) |
| `…/commit/<oid>` | commit |
| `…/pull/<n>[/files\|/commits]` | pull request |
| `raw.githubusercontent.com/<o>/<r>/<ref>/<path>` | ref and file |

Any other github.com path is refused with a typed error that names the shape and offers
the repository URL (decided 2026-09-23). Tracking and display query parameters are
dropped. A `<ref-and-path>` is split after the mirror exists, against its branches and
tags, longest match first, so a branch with slashes resolves correctly.

### Git mirror

- **Layout.** One directory per repository under the application home, holding a bare
  repository and a small record (source URL, last fetch time, `gh` account if any).
  The existing source slug is the directory name.
- **Clone.** `git clone --bare` with full objects into a staging directory, then an
  atomic rename into place.
  A crash leaves only staging, which the next open sweeps.
- **Refs mirrored.** Branches and tags.
  For a pull request, fetch `refs/pull/<n>/head` into the same name.
  Fork commits arrive through it, so forks need no mirror of their own.
- **Update.** `git fetch --prune` of branches and tags, under one lock per mirror, so
  concurrent opens share one fetch.
  Git writes objects before it moves refs, so readers never see a ref without its
  objects.
- **Resolve.** A ref, tag, or abbreviated ID resolves to a full commit ID locally.
  If it is missing, one fetch runs and the lookup is retried; then it is a typed
  not-found.
- **Offline.** Every read works from the mirror alone.
  A failed refresh leaves the page as it was and marks it stale.

### Seamless caching

| Situation | Behavior |
| --- | --- |
| First visit | Clone (or first `gh api` read), with progress; the page opens when ready |
| Cached, fresh | Open from the mirror; no network |
| Cached, stale | Open from the mirror at once; one background refresh; the page updates in place when it lands |
| Offline or refresh failed | Open from the mirror; a quiet stale label with the last refresh time |
| Explicit refresh | Always fetches, with the same in-place update |

Freshness windows are engineering defaults to tune by measurement: about one minute for
Git refs and pull-request data on an open page.
Only one refresh per mirror or pull request runs at a time; later requests join it.
The browser learns about updated data through the existing server events.
A view pinned to a commit ID never changes under the reader.
Only the “latest” pointers (a branch, a pull request’s head) move, and the page offers
the newer revision rather than swapping it silently.

### Hosted records (pull requests)

Pull-request data is fetched with `gh api` and stored per pull request as JSON records:
the pull request itself, issue comments, reviews, review comments, check runs and
statuses, and the changed-file list.
Each record keeps its fetch time and the `gh` account that read it.
Pydantic models validate the records on write and parse them on read; there is no
separate artifact-format or resource-profile layer.
A record set is replaced as a whole with an atomic rename, so a reader sees either the
old set or the new one.

The changed-files comparison is `merge-base(base, head)..head`, which matches GitHub’s
“Files changed” (decided 2026-09-23). Git computes it from the mirror once
`refs/pull/<n>/head` and the base branch are present.

### Authentication

- Public repositories: anonymous HTTPS, with no credential helper at all.
- Private repositories: the fetch runs with
  `-c credential.helper= -c credential.https://github.com.helper=!gh auth git-credential`,
  so Git asks `gh` directly and nothing else.
  The user’s own global helpers stay out.
- API data: `gh api --hostname github.com …` with `gh`’s own login.
- Account: `gh auth status --active --json` is read before an operation, and the account
  is recorded with its results.
  If the active account changed by the end, the results are discarded with a typed
  error.
- `gh` missing or logged out: public content still works; private content and pull
  request data answer a typed state with the command that fixes it.

## Capability Map

| GitHub web | Alpha | Later |
| --- | --- | --- |
| Code tree and file view, with line links | Yes |  |
| Branch and tag selection | Yes |  |
| Commit history and commit detail with diff | Yes (existing Git views) |  |
| Raw file | Yes (sandboxed) |  |
| Pull request: description, labels, state, merge status | Yes |  |
| Pull request: conversation, reviews, review comments | Yes (review comments listed with file and line) | Inline anchoring in the diff |
| Pull request: checks and statuses summary | Yes | Logs |
| Pull request: Files changed | Yes (merge-base diff) |  |
| Pull request list for a repository |  | Yes |
| Issues, Actions, releases, blame |  | Yes |
| SSH remotes, GitHub Enterprise hosts |  | Yes |

## Retired From Earlier Plans

These pieces answered concerns a read-only, single-user mirror does not have.
Their beads are closed as superseded or rescoped when this plan lands.

| Earlier design | Why it is not needed |
| --- | --- |
| Blobless clones, lazy-fetch policy, convergence states, background convergence | Full clones; every object is present after the first clone |
| Private subject refs, revision leases, maintenance locks | No garbage collection in v1, so nothing can remove a shown commit |
| Job refs, staged fetch records, compare-and-swap publication, job coalescing keys | `git fetch` already writes objects before refs; one lock per mirror |
| Authorization contexts, principals, visibility partitions | One user; the recorded `gh` account is enough |
| Token broker, credential leases, askpass bridge | `gh` is the credential helper |
| Provider snapshot store, manifests, resource profiles for PR data | JSON records per pull request, replaced atomically |
| Binding and rebind state machine | Records are keyed by GitHub’s node ID and refetched |
| Public URL-reducer, router, address-space and nav-panel SDKs | Internal host interface; the SDK comes later |
| Attaching user checkouts to the mirror | Deferred |
| Fork mirrors | `refs/pull/<n>/head` carries fork commits |

The Hosted Review Format work already in the stack stays in place, but new code does not
build on it for the alpha.

## Delivery

Each step is one stacked pull request, implemented and then reviewed by separate agents,
with `make verify` and green CI before the next step starts from its head.

| PR | Scope | Checkpoint |
| --- | --- | --- |
| Design | This plan, bead changes, notes in the superseded specs | Plan agreed |
| Simplify | Full clones; remove lazy-fetch, convergence, subject refs, leases, and maintenance locks; keep the pinned subject and batch readers | T0 still passes; less code |
| URL open (2A+2C) | HTTPS clone and fetch, GitHub resolver, ref and path splitting, line anchors, seamless refresh, browser serving of a pinned revision | Paste a repository, tree, blob, or commit URL; browse it in the browser and CLI; reopen offline |
| PR data | `gh` runner and auth checks, PR records, `refs/pull/<n>/head` fetch, merge-base comparison, CLI inspection | `metab <pr-url> --api …` shows the PR, reviews, checks, and files, including offline |
| PR view | Pull-request page: conversation, reviews, review comments, checks, and Files changed | Paste a PR URL and read it in the browser; reload and reopen offline |

Later: pull-request list, inline review anchoring, SSH, Enterprise hosts, issues.

## Testing

- **Hermetic first.** `file://` origins, a local smart-HTTP Git server for the HTTPS
  path, and a fake `gh` executable with recorded responses for pull-request data.
- **Parity.** Every new route and state has a `metab --api` or `--show` golden, per
  [AGENTS.md](../../../../AGENTS.md).
- **Live smoke, opt-in.** Outside `make verify`: anonymous clones of small public
  repositories and read-only `gh api` reads of public data.
  Nothing is ever written to GitHub.
- **Admitted Git.** The admitted-Git CI job keeps running the mirror paths on Git 2.43.7
  and 2.50.1.

## Decisions (2026-09-23, by the user)

- The cache is a plain mirror: full clones, `git fetch`, no invented refs, garbage
  collection off, views pinned by commit ID, read-only.
- Authentication is external: `gh` is the credential helper and the API client.
- An unrecognized github.com URL shape is refused with a typed error.
- github.com only for the alpha.
- Pull-request comparison is `merge-base..head`.
- GitHub support is internal; no public SDK for it yet.
- Plain Pydantic records for pull-request data, and merged phases.
- Deferred: SSH, the pull-request index and panel, inline thread anchoring, checkout
  attachment, rebind.
- Browsing should feel like the GitHub web interface, served from a seamless cache:
  instant from the mirror, refreshed in the background.
  This replaces the earlier default of explicit refresh only.
- Opt-in live smoke tests may clone public repositories and make read-only `gh api`
  calls.

## Open Engineering Choices

These have documented defaults and are settled by measurement during implementation:

- Freshness windows for refs and pull-request data (default about one minute).
- First-clone time for large repositories; blobless clones return only if a measurement
  shows a full clone is too slow for common repositories.
- Disk growth with garbage collection off; a purge command can follow the alpha.
- Bounds on pull-request records: comment, review, and file counts, and body sizes.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
