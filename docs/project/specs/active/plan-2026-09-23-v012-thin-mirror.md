# Plan: v0.12 Thin Mirror for Git and GitHub Browsing

**Status:** Delivered on the unmerged v0.12 stack.
The design was decided on 2026-09-23 and revised the same day after an independent
design review. [Delivery](#delivery) maps each step and follow-up to its pull request.
Nothing is merged: the
[alpha test plan](plan-2026-09-22-v012-alpha-testing.md#landing-status) lists what
remains before landing, which waits for the user’s approval (`mb-n2ro`).

This plan supersedes the remaining v0.12 phases in
[Open Repositories from Git URLs](plan-2026-08-11-open-repo-from-git-url.md) (2A onward)
and
[GitHub Provider and Pull Requests](plan-2026-08-27-github-provider-and-pull-requests.md)
wherever they disagree.
Those documents stay as background.
The repository foundation they record (Phases 0–1B) stays as built, as changed by the
Simplify step below; the hosted-review foundation was removed, as
[Retired From Earlier Plans](#retired-from-earlier-plans) records.

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
  an isolated environment, and does not reimplement transport, authentication, ref
  updates, or object storage.
- **The cache is a mirror.** One bare repository per source, updated with `git fetch`.
  Metabrowser invents no branches and no private refs; the only refs beyond branches and
  tags are GitHub’s own `refs/pull/<n>/head`, fetched on demand.
- **Read-only.** There are no working trees and no local changes.
  Every view is pinned to a full commit ID, so a moving branch never changes a page
  under a reader.
- **No Git object is deleted in v1.** Garbage collection, pruning, and automatic store
  reclamation stay off, so a commit that was ever shown stays readable, even after a
  force-push upstream.
  Staging directories left by a crash are still swept.
- **Seamless caching, never blocking a request.** A cached page opens from the mirror.
  Network work runs only in background jobs: a server request starts or joins one and
  returns at once. Only a first visit, which has nothing to show yet, waits for its
  clone.
- **`gh` owns GitHub authentication.** Metabrowser never reads, stores, or logs a token.
- **Thin plugin boundary.** GitHub support lives in a built-in plugin, reached through
  the existing reducer hook and plugin routes; core code does not branch on GitHub.
  No new public SDK surface is added for the alpha.
- **Acquired content is untrusted.** The forced untrusted profile applies to every
  mirrored page, and pull-request text renders through the existing sanitizer.

## Architecture

```
URL ──> GitHub reducer (plugin) ──> Target(source, rev?, path?, lines?, pr?)
                                        │
          ┌─────────────────────────────┴──────────────────┐
          v                                                 v
   Git mirror (core, git)                          PR records (plugin, gh api)
   init/fetch, refs/pull/<n>/head                  one JSON file per pull request
          │                                                 │
          └────> pinned subject + background refresh <──────┘
                 existing routes, renderers, CLI parity
```

| Layer | Owns | Where |
| --- | --- | --- |
| URL reducer | GitHub URL grammar, canonical source, what a URL points at | `builtin_plugins/github/`, through `classify_root_argument(reducers=)` |
| Git mirror | Store, fetch, ref and path resolution, freshness | `cache/`, `git/` |
| Refresh coordinator | Background jobs, single flight, status | Core, one small module |
| Pin switching | Replace the served subject within one repository | `source.py` session lifecycle |
| PR records | Pull-request data as validated JSON | `builtin_plugins/github/` |
| Views | Code, history, commits, diffs, PR pages | Existing routes and renderers; the PR page in the GitHub plugin |

### URL reducer

The GitHub plugin supplies a reducer through the existing
`classify_root_argument(reducers=)` hook in `cache/urls.py`. It runs before generic
source classification, so it repeats that classifier’s checks for control characters and
credentials in URLs.
It claims only `github.com` and `raw.githubusercontent.com`.

| URL | Target |
| --- | --- |
| `github.com/<o>/<r>` (with or without `.git`, trailing slash, `www.`) | repository, default branch |
| `…/tree/<ref-and-path>` | ref and directory |
| `…/blob/<ref-and-path>[#L10][#L10-L20][#L10C5-L20C8]` | ref, file, and lines (`?plain=1` kept) |
| `…/commit/<oid>`, `…/pull/<n>/commits/<oid>` | commit |
| `…/pull/<n>[/files\|/commits]` | pull request |
| `raw.githubusercontent.com/<o>/<r>/<ref>/<path>` (and `refs/heads/<ref>/…`) | ref and file |
| `git@github.com:<o>/<r>.git` | rewritten to the HTTPS repository URL |

- Any other github.com path, `http://github.com`, and reserved owners are refused with a
  typed error that names the shape and offers the repository URL.
- Owner matches `[A-Za-z0-9-]{1,39}`; repository matches `[A-Za-z0-9._-]{1,100}` and is
  never `.` or `..`; a pull-request number matches `^[1-9][0-9]{0,9}$`.
- The canonical source is `https://github.com/<owner>/<repo>` with owner and repository
  lowercased and `.git` removed, so URL variants share one mirror.
- Tracking and display query parameters are dropped.
- A web URL is read as a browser sends it: a space or a visible character outside ASCII
  in its path, query, or fragment is percent-encoded as UTF-8, so a pasted `…/docs/雪.md`
  opens what `…/docs/%E9%9B%AA.md` opens (decided 2026-09-24, `mb-tals`). Controls,
  other whitespace, format and default-ignorable characters, the blank braille pattern,
  unassigned and private-use code points, a trailing space, and a `%` that starts no
  escape stay refused; a refused character is named by code point, with the encoded
  spelling where one exists.
- Other `https://` and `file://` Git URLs need no reducer, clone anonymously, and open
  their default branch.

### Git mirror

- **Layout.** The source-alias and repository-store records built in Phase 1B-a stay.
  A source alias names one bare store; the store identity derives from the canonical
  source. The existing `last_fetch_at` records the last successful fetch.
- **Create.** Keep the built acquisition: `git init --bare --template=` in staging with
  the store configuration (`gc.auto=0`, `maintenance.auto=false`, no submodule
  recursion, no bundle URI, no hooks), fetch, validate, publish, then the alias.
  Full objects only.
- **Update.** `ls-remote --symref -- origin HEAD` to track the default branch, then
  `fetch --prune --atomic --no-write-fetch-head origin +refs/heads/*:refs/remotes/origin/* +refs/tags/*:refs/tags/*`.
  Pruning these refspecs never touches `refs/pull/*`. Protocols: `protocol.allow=never`,
  with HTTPS and `file` allowed.
- **Pull-request refs.** `fetch origin +refs/pull/<n>/head:refs/pull/<n>/head` with the
  validated number. Fork commits arrive through it.
- **Locks.** Network work holds no hierarchy lock.
  A fetch takes a side lock, `<store-key>.fetch.lock`, tried without blocking; if
  another process holds it, the job reports “refreshing elsewhere”.
  Within a process, one job per store runs at a time and later requests join it.
  Only rewriting the store record takes the short store lock.
- **Interrupted fetches.** A killed Git can leave `packed-refs.lock` or `refs/**.lock`.
  Under the fetch side lock, stale lock files are removed before the next fetch.
- **Resolve.** Split `<ref-and-path>` into one candidate per path segment, up to a
  segment cap, and check each candidate with `show-ref --verify` after validating Git
  ref-name rules. Precedence: branch, then tag, then full or abbreviated commit ID. User
  text is never passed to `rev-parse`, which would evaluate `:/text`, `@{…}`, or
  `^{/…}`. A missing ref or commit ID starts one background fetch; until it finishes the
  page answers a typed pending state, then found or not-found.
- **Offline.** Every read works from the mirror alone.
  A failed refresh leaves the page as it was and reports the failure in its status.
- **Large repositories.** A full clone is slower than a blobless one.
  The earlier measurement (mypy: 5.8–5.9 s to serve the default tree blobless, 8.8–17.8
  s full;
  [architecture](../../architecture/arch-repository-sources-and-provider-mirrors.md)) is
  the baseline. When `gh` is available, the repository size from `repos/<o>/<r>` is
  checked first, and a clone that cannot finish inside the acquisition deadline is
  refused with a typed state rather than killed partway.
  The first clone says on stderr where it goes, then reports Git’s own progress, read as
  numbers and never passed through as text, with the elapsed time (`mb-4cg7`).

### Serving and pin switching

- A server serves one repository at a time, as today.
  Opening another repository is a new `metab <url>` run.
- Within that repository, `POST /api/source/pin` with a ref or commit ID re-attaches the
  subject: it closes the old tree source, opens the new one, bumps the session
  generation, and the browser reloads the view.
  Branch and tag selection and “newer revision available” both use it.
- History cursors over all branches are fingerprinted by the public refs, so a refresh
  that moves a ref turns an open cursor into a typed stale state with a reload action.
- `repository_context` is supplied for GitHub mirrors, so github.com links inside a
  rendered README open locally.

### Background refresh

- **Coordinator.** A dictionary of background tasks on the application state, keyed by
  store key or by store key and pull-request number, so requests join a running refresh;
  a global semaphore of two bounds concurrent network jobs.
- **Routes.**
  - `GET /api/source/status` (with an ETag): pin, ref, latest commit ID for that ref,
    generation, last fetch time, last outcome, whether a refresh is running, and the
    pull request if any.
  - `POST /api/source/refresh`: start or join a refresh; returns at once.
  - `POST /api/source/pin`: see above.
- **Browser.** While the page is visible, poll the status route: quickly while a refresh
  runs, slowly otherwise.
  Show a quiet stale label and, when the ref moved, an offer to switch to the newer
  revision. Pull-request conversation and checks update in place; code and diff views
  keep their pin and offer the newer revision.
  No server-sent events are added for the alpha.
- **Freshness.** A refresh starts on open when the data is older than a window (default
  about one minute, tuned by measurement), and only while a page is visible.
- **CLI.** One-shot `--show` and `--api` read the cache as it is; only the explicit
  refresh route touches the network.
  This keeps goldens deterministic.
- **Route safety.** Every route that starts network work or changes the pin is a POST
  with a JSON body behind the existing same-origin guard, so content inside an untrusted
  page cannot trigger it with a plain link or image.

### Pull-request records

- One JSON file per pull request under its source,
  `cache/sources/<slug>/pulls/<n>.json`, written with the existing private atomic file
  write, with a schema integer (a mismatch refetches; there is no migration) and a
  bounded read. Cache layout checks learn the path.

- Contents: the pull request, issue comments, reviews, review comments, check runs, and
  statuses, each read with `gh api`, with the fetch time and the reader (`anonymous` or
  `gh:<login>`).

- Pydantic models validate on write and parse on read; there is no separate
  artifact-format or resource-profile layer.

- Bounds: comment, review, check, and body sizes are capped per record, measured on real
  pull requests, with truncation reported.

- The changed-file list comes from Git, not the API. Comparison endpoints are pinned
  commit IDs stored in the record:
  - open pull request: `merge-base(<base branch in the mirror>, head.sha)..head.sha`;
  - closed or merged: `merge-base(base.sha, head.sha)..head.sha`.

  Both match GitHub’s “Files changed” (decided 2026-09-23); the merged case is checked
  in the live smoke test.
  The existing comparison route passes its base policy through.

- `mergeable: null` is shown as unknown.
  A review comment on an older commit shows the API’s `diff_hunk`.

### Authentication and `gh`

- **Git.** When `gh` is on `PATH`, every GitHub fetch and `ls-remote` runs with
  `-c credential.helper= -c credential.https://github.com.helper=!'<abs-gh>' auth git-credential`.
  Git asks the helper only after a server challenge, so public repositories stay
  anonymous without knowing their visibility first.
  The empty `credential.helper=` clears the user’s global helpers; the helper answers
  only `https://github.com`. Other hosts get no helper.
- **Account.** `gh auth status --active --hostname github.com --json hosts` gives
  `login`, `state`, and `active`; a non-success state is not treated as logged out,
  because offline also reports an error, and it is never called before an offline read.
  A pull-request record is discarded if the active account changed while it was read; a
  Git fetch cannot be rolled back and is not.
  Cached private content stays viewable after a logout or account switch.
- **Running `gh`.** Fixed arguments, no stdin, an environment with
  `GH_PROMPT_DISABLED=1`, `GH_NO_UPDATE_NOTIFIER=1`, and `NO_COLOR=1` and without
  `GH_DEBUG`, `GH_HOST`, or `GH_REPO`; a deadline, an output cap, and process-group
  kill; stdout is never logged.
  No `--paginate` and no `--cache`: pages are requested explicitly with `per_page=100`
  and a page cap, with `--include` for status, ETag, and rate-limit headers.
  A `gh` too old for `auth status --json` is a typed state.
- **Rate limits.** Requests send `If-None-Match`, honor `Retry-After` and
  `x-ratelimit-reset`, and stay under the global job cap.

## Capability Map

The Alpha column is delivered on the stack.
[QA: v0.12 alpha acceptance](../../qa/qa-2026-09-24-v012-alpha-acceptance.md) records
the run against it.

| GitHub web | Alpha | Later |
| --- | --- | --- |
| Code tree and file view, with line links | Yes |  |
| Branch, tag, and commit selection | Yes (pin switching: a branch and tag selector, and commits by URL) |  |
| Commit history and commit detail with diff | Yes (existing Git views) |  |
| Raw file | Yes (sandboxed) |  |
| Pull request: description, labels, state, merge status | Yes |  |
| Pull request: conversation, reviews, review comments | Yes (review comments listed with file and line) | Inline anchoring in the diff |
| Pull request: checks and statuses summary | Yes | Logs |
| Pull request: Files changed | Yes (merge-base diff) |  |
| Diff: View file at either side of a changed file | Yes (a side not at the served commit switches the pin) | An address for a file at another commit |
| Pull request list for a repository |  | Yes |
| Issues, Actions, releases, blame |  | Yes |
| SSH remotes, GitHub Enterprise hosts |  | Yes |

## Retired From Earlier Plans

| Earlier design | Why it is not needed |
| --- | --- |
| Blobless clones, default-tree prefetch, convergence states and jobs | Full clones; every object is present after the first fetch |
| Private subject refs, revision leases, maintenance locks, automatic store reclamation | No Git object is deleted in v1 |
| Job refs, staged fetch records, compare-and-swap publication, coalescing keys | `fetch --atomic` writes objects before refs; a fetch side lock and in-process single flight |
| Authorization contexts, principals, visibility partitions | One user; the recorded reader is enough |
| Token broker, credential leases, askpass bridge | `gh` is the credential helper |
| Provider snapshot store, manifests, resource profiles for pull-request data | One JSON file per pull request |
| Binding and rebind state machine | Records are refetched; canonical sources are stable |
| New public URL-reducer, router, address-space, and nav-panel SDKs | Existing reducer hook and plugin routes |
| Attaching user checkouts; fork mirrors | Deferred; `refs/pull/<n>/head` carries fork commits |

`GIT_NO_LAZY_FETCH` and the store-spawn guard stay as defensive settings.
The Hosted Review Format and `provider_resources` code that was in the stack was removed
in [#246](https://github.com/jlevy/metabrowser/pull/246), with what existed only for it:
browser-parser evidence, the `metabrowser.capabilities.v1` entry-point group, the
frontmatter Markdown artifact profile, and the cache’s reservations for a provider
store. It is preserved as unused reference code, not on the critical path and not
maintained, on the `reference/v012-hosted-review` branch, tagged
`reference/v012-hosted-review-2026-09-30`.

## Delivery

Each step is one stacked pull request, implemented and reviewed by separate agents, with
`make verify` and green CI before the next step starts from its head.

| PR | Scope | Checkpoint | Delivered |
| --- | --- | --- | --- |
| 1. Design | This plan, bead changes, superseded notes | Plan agreed | [#227](https://github.com/jlevy/metabrowser/pull/227) (`mb-4izu`) |
| 2. Simplify | Full clones; remove convergence, subject refs, leases, maintenance locks, and store reclamation; edit the unreleased records and fixtures in place | T0 still passes, with less code | [#228](https://github.com/jlevy/metabrowser/pull/228) (`mb-raep`) |
| 3. Serve a pin | Browser serving of a `file://` pin, forced untrusted profile, served `/raw` decision; `repository_context` moved to step 5, since only a GitHub mirror has one | Open a `file://` source in the browser and browse it; no network | [#229](https://github.com/jlevy/metabrowser/pull/229) (`mb-doao`) |
| 4. Refresh and pin switching | Coordinator, status, refresh and pin routes, browser stale label and newer-revision offer, stale history cursors, fetch side lock and stale-lock cleanup | Push to a `file://` origin, see the offer, switch; no network | [#230](https://github.com/jlevy/metabrowser/pull/230) (`mb-i5ln`) |
| 5. GitHub URL open | Reducer plugin with network-free goldens for every URL shape, HTTPS with the `gh` helper, error classification, measured stall bound, ref and path split, line anchors, SIGHUP handling, `repository_context` for GitHub mirrors | Opt-in live smoke on a public repository | [#231](https://github.com/jlevy/metabrowser/pull/231) (`mb-bgs7`) |
| 6. PR data | `gh` runner and account checks, PR records, `refs/pull/<n>/head`, comparison endpoints, CLI inspection | `metab <pr-url> --api …` shows the pull request, including offline | [#232](https://github.com/jlevy/metabrowser/pull/232) (`mb-nkmq`) |
| 7. PR view | Pull-request page: conversation, reviews, review comments, checks, Files changed | Paste a PR URL and read it in the browser; reload and reopen offline | [#233](https://github.com/jlevy/metabrowser/pull/233) (`mb-vrl7`) |

Follow-up pull requests extend those steps, in stack order:

| Pull request | Scope | Beads |
| --- | --- | --- |
| [#234](https://github.com/jlevy/metabrowser/pull/234) | Inert Markdown and a Content-Security-Policy for untrusted sources | `mb-a0za`, `mb-2rg9` |
| [#235](https://github.com/jlevy/metabrowser/pull/235) | Line numbers and `#L` anchors in source views | `mb-rlf3` |
| [#239](https://github.com/jlevy/metabrowser/pull/239) | Line anchors on the Markdown Source tab, `?plain=1`, and keyboard anchors | `mb-gkrr` |
| [#242](https://github.com/jlevy/metabrowser/pull/242) | Removal of an unused DOM test harness | `mb-y3z4` |
| [#236](https://github.com/jlevy/metabrowser/pull/236) | Branch and tag selector for a served mirror | `mb-eezo` |
| [#238](https://github.com/jlevy/metabrowser/pull/238) | Pull-request page follow-ups | `mb-7kqx`, `mb-f9s2` |
| [#237](https://github.com/jlevy/metabrowser/pull/237) | Backslash filenames, Load more on a pin, and owner-stamped delegated controls (Plugin SDK 0.7) | `mb-yhso`, `mb-clkn`, `mb-w2vx` |
| [#240](https://github.com/jlevy/metabrowser/pull/240) | GitHub-style heading anchors and a table of contents for untrusted documents | `mb-39uq`, `mb-rzjh` |
| [#241](https://github.com/jlevy/metabrowser/pull/241) | Alpha acceptance record | `mb-gnr9` |
| [#243](https://github.com/jlevy/metabrowser/pull/243) | Acceptance fixes: table-of-contents toggle, raw GitHub URLs, pull-request header state | `mb-ddbe`, `mb-tals`, `mb-5wqg` |
| [#244](https://github.com/jlevy/metabrowser/pull/244) | Fork-qualified pull-request header; default-ignorable characters escaped in displayed paths | `mb-v8sb`, `mb-1bpe` |
| [#246](https://github.com/jlevy/metabrowser/pull/246) | Removal of the unused Hosted Review Format and provider-resource code | `mb-whmn`, `mb-31qs` |
| [#248](https://github.com/jlevy/metabrowser/pull/248) | View file at either side of a changed file, from a commit’s diff or Files changed | `mb-zb5t` |
| [#249](https://github.com/jlevy/metabrowser/pull/249) | Existing folders with URL-like names are served; a state for an unfetched commit; not-found wording | `mb-n80y`, `mb-4kuc`, `mb-2nu0` |
| [#250](https://github.com/jlevy/metabrowser/pull/250) | Plans, roadmap, architecture documents, and changelog brought in line with the delivered stack | `mb-myum` |

Later: pull-request list, inline review anchoring, SSH, Enterprise hosts, issues,
checkout attachment, and rebind.

## Testing

- **Network-free first.** URL-to-target goldens need no network.
  Mirror behavior uses `file://` origins.
  The credential arguments are tested with a `git credential fill` test.
  Pull-request data uses a fake `gh` on `PATH` with recorded responses.
- **Real HTTPS** is covered by the opt-in live smoke test, because trusting a local test
  certificate would need an escape hatch the environment allowlist rightly removes.
- **Parity.** Every new route and state has a `metab --api` or `--show` golden, and the
  browser freshness and pin-switching behavior has a functional-aspect row and a
  browserless session, per [AGENTS.md](../../../../AGENTS.md).
- **Live smoke, opt-in.** Outside `make verify`: anonymous clones of small public
  repositories and read-only `gh api` reads of public data.
  Nothing is ever written to GitHub.
- **Admitted Git.** The admitted-Git CI job keeps running the mirror paths on Git 2.43.7
  and 2.50.1.

## Decisions (2026-09-23, by the user)

- The cache is a plain mirror: full objects, `git fetch`, no invented refs, no Git
  object deletion, views pinned by commit ID, read-only.
- Authentication is external: `gh` is the credential helper and the API client.
- An unrecognized github.com URL shape is refused with a typed error.
- github.com only for the alpha.
- Pull-request comparison uses the merge base, as GitHub does.
- GitHub support is internal; no new public SDK for it yet.
- Plain Pydantic records for pull-request data, and fewer, merged phases.
- Deferred: SSH, the pull-request index and panel, inline thread anchoring, checkout
  attachment, rebind.
- Browsing should feel like the GitHub web interface, served from a seamless cache:
  instant from the mirror, refreshed in the background.
  This replaces the earlier default of explicit refresh only.
- Opt-in live smoke tests may clone public repositories and make read-only `gh api`
  calls.

## Open Engineering Choices

Settled by measurement during implementation, each with a documented default:

- Freshness windows and polling intervals.
- First-clone time and size limits for large repositories.
- Disk growth with no object deletion; `repack -a -d --keep-unreachable` consolidates
  packs without deleting objects if lookups slow down.
- Bounds on pull-request records: settled in `builtin_plugins/github/pull_record.py`,
  measured on ten public pull requests.
- The minimum `gh` version for `auth status --json`: 2.81.0, the release that added it.
  The reader is never `anonymous` in practice, because `gh api` refuses requests while
  signed out (checked with gh 2.98.0).

Step 4 set the freshness window and the browser’s polling intervals over `file://`; each
default and its measurement sits beside its constant, `FRESHNESS_WINDOW_S` in
`mirror_refresh.py` and `FAST_POLL_MS` and `SLOW_POLL_MS` in
`static/source-freshness.js`. HTTPS may tune them in step 5.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
