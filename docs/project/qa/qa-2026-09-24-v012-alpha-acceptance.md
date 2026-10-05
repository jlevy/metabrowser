# QA Run: v0.12 Alpha Acceptance on the Integrated Stack

**Status:** Recorded 2026-09-24 for `mb-gnr9`. The rows run here pass, apart from four
findings filed as beads.
M10b, M12, and M13 were not run because the thin-mirror plan defers them.
This record is evidence for the landing decision (`mb-n2ro`), not that decision.
The failed rows were rerun on the fixes in #243; see [Rerun on #243](#rerun-on-243). The
[addendum](#addendum-2026-09-30) records what changed after the run.
M03b and M08b were rerun on View file at the stack’s tip, and both pass; see
[Rerun on #250](#rerun-on-250-view-file-landing-fixes).
The [addendum of 2026-10-01](#addendum-2026-10-01) records the verification of the tip
as it was at #257, which is not an acceptance rerun, and the
[second addendum](#second-addendum-2026-10-01) what followed the same day.

The procedure is the manual matrix in the
[alpha testing plan](../specs/active/plan-2026-09-22-v012-alpha-testing.md), adapted to
the scope of the
[thin-mirror plan](../specs/active/plan-2026-09-23-v012-thin-mirror.md).
The step-by-step checks come from the
[repository library QA runbook](../../qa-v012-repository-library.md).

## Build

The open v0.12 pull requests above #234 are siblings, so no single head contains all of
them. Draft [#241](https://github.com/jlevy/metabrowser/pull/241) starts at #240’s head
and merges, without rebasing, the tips of #236, #238, and #239 (which includes #235).
#240 already includes #237.

| Item | Value |
| --- | --- |
| Integration head (tested wheel) | `250a10c42583e4e06d4ff286c573b289ce6e2153` |
| Integration head (after the test fix) | `aa1f4d93ce0248ef1ecf4a792cab9c531abac859`; changes only `tests/test_source_ref_selector_session.py` |
| Base (#240, `codex/v012-markdown-anchors`) | `edef33c5e0a7b8512e8f84c7d0c074ad8aa6aea7` |
| Merged tips | #236 `05875cd43322000f7d633f439e76273bff39404c`, #238 `57ada67e08666b9533562e16a8e7533deb988191`, #239 `311e83987088194ce273bb9cfcef8293f2511c65` |
| `main` | `6c278f3f9e10aebcb34a207035aee7768a1bba0e` |
| Wheel | `metabrowser-0.11.1.dev400+250a10c4-py3-none-any.whl` from `make build` |
| Platform | macOS 26.5.2 (25F84), arm64 |
| Tools | Git 2.50.1, gh 2.98.0, uv 0.12.8, Python 3.14.7, Node 24.19.0 |
| Browser | The Claude desktop browser pane, Chrome 152.0.7977.130 |
| Observation time | 2026-09-24, 20:36–21:10 UTC |

### Merge conflicts

Every conflict was two additions side by side in documentation, and each resolution
keeps both sides. There were no code conflicts.

- #236: in the routes map, #240’s kpress row now sits beside #236’s new
  `/api/source/refs` row and its extended `/api/source/pin` row.
  In the QA runbook, #240’s section 5.9 stays and #236’s selector section becomes 5.10.
- #238: no conflicts.
- #239: `CHANGELOG.md` keeps both the SDK 0.7 entry and the `renderSourceView` gutter
  entry. `docs/plugins.md` keeps `ownDelegate` and `delegateOwnerAttribute` beside #239’s
  `renderSourceView(container, data, options)`. Runbook 5.3 keeps the Load more step as
  step 8, and the line-anchor steps become 9–12.

### Automated evidence

- Local, on `250a10c4`: `make lint-check` passes, and parity reports 38 routes covered,
  5 exempt, 11 kinds, and 47 functional aspects.
  The tryscript goldens pass, 269 of 269, with `tests/no-real-gh` first on `PATH`.
  `make build` passes its distribution checks, including the isolated wheel smoke test.
  The full `make test` ran in CI because the machine’s load average was 150–200.
- CI [run 36055735310](https://github.com/jlevy/metabrowser/actions/runs/36055735310) on
  `250a10c4`: lint, distribution, and admitted-git (2.43.7 and 2.50.1) pass.
  Every test job and `stack-integration` failed on one test,
  `test_recording_is_what_a_served_mirror_answers`, with 3657 passing.
  The cause exists only on the merged stack.
  #239’s `test_shell_loads_line_anchors_eagerly_before_the_sdk` renders the shell
  through `server.index`, which opens the lazily created source session and never resets
  it. #236’s recording test then records every session generation one higher.
  Each test passes when run alone.
  Commit `aa1f4d93` resets the session at the start of the recording.
- CI [run 36059678339](https://github.com/jlevy/metabrowser/actions/runs/36059678339) on
  `aa1f4d93`: all nine checks pass: lint, distribution, admitted-git 2.43.7 and 2.50.1,
  test on Python 3.12, 3.13, 3.14, and 3.14t, and `stack-integration`.

## Method

- The wheel is installed into a clean uv-managed Python 3.14 environment in the session
  scratch directory (`<scratch>`), with dependency versions from
  `uv export --frozen --no-dev` and `UV_EXCLUDE_NEWER="14 days"`. Every command runs the
  installed `metab` entry point without patches.
- `METABROWSER_CACHE_DIR` and `XDG_CACHE_HOME` point into `<scratch>`. T1 used one home.
  T2 started from a second, cold home, and M10 used a third.
- Offline rows block the network for the test process only:
  `sandbox-exec -f offline.sb`, with a profile that denies outbound IP connections
  except to localhost.
  System network settings did not change.
- `gh` is the real, signed-in gh 2.98.0 unless a row says otherwise.
  Every gh call was a read-only GET of public data.
  To count calls, some rows put a wrapper first on `PATH` that logs only its arguments
  and then runs the real gh.
  The signed-out case sets `GH_CONFIG_DIR` to an empty directory, and the real login is
  untouched. The “too old” case uses a stand-in without `auth status --json`.
- Browser rows use servers on ports 8691–8698. The browser pane was hidden for most of
  the run, which has three consequences.
  Screenshots were not available after M03. Checks read the DOM and the network through
  the page’s JavaScript.
  The freshness controller polls only while the page is visible, so rows that need it
  override `document.visibilityState` and dispatch `visibilitychange`. Key and click
  events are dispatched to the production handlers rather than typed.

## Fixtures

All fixtures are public repositories, recorded at the observation time.

| Fixture | Revisions |
| --- | --- |
| `octocat/Hello-World` | `master` `7fd1a60b01f91b314f59955a4e4d4e80d8edf11d`, `test` `b3cbd5bbd7e81436d2eee04537ea2b4c0cad4cdf`, first commit `553c2077f0edc3d5dc5d17262f6aa498e69d6f8e` |
| `octocat/Spoon-Knife` | `main` `d0dd1f61b33d64e29d8bc1372a94ef6a2fee76a9` |
| `jlevy/metabrowser` | `main` and tag `v0.11.0` `6c278f3f…`; `codex/v012-markdown-anchors` `edef33c5…`, which has `docs/雪.md` and `docs/space name.md` under `tests/fixtures/github-markdown-repo`; `claude/research-desktop-app-packaging` `d9dfbbe86ac3fb0fec87dc0ed5d2a6b00c39856e` |
| `cli/cli#14128` | Merged. Base `trunk` at `c624f0ac79b2923a98a451aa9b7eebffca9c1222`, head `5dfc6b06b53e8c3962b28d3ebf00e9b696daf985`. 3 reviews, 2 review comments, 26 check runs, 86 files with 1 rename |
| `jlevy/metabrowser#3` | Merged. Base `5dfb02e74b572fbf402326a42d8e979d182f7fb3`, head `93edfdeb8b304c175141b4b3da03ea7d7226d425`. 91 files: 5 deletions and 1 binary added |
| `jlevy/metabrowser#234` | Open. Base branch `codex/v012-pr-view` at `8e5be947c3729d7410d1857337024b3cf9a6f3c1`, head `783248c32eac901097ad10d4890fc3fb68f461ff`. 47 files: 1 deletion and 1 binary added |
| Local `file://` origins | A working checkout with `main` and `feature/x` (M04), a hostile repository (M06), and a repository holding `a\b.md` |

## Results

| Row | Result | Notes |
| --- | --- | --- |
| M01 | Pass | The HTML Preview frame did not paint; see the row |
| M02a | Pass | URL shapes, slash branch, and percent-encoded Unicode and space paths |
| M02b | Fail (P3) | Raw Unicode or a space is refused without a recovery hint: `mb-tals` |
| M03a | Pass | Relative links, reload, back and forward, second tab |
| M03b | Fail (P3); pass in the [rerun on #250](#rerun-on-250-view-file-landing-fixes) | No way to open base or head files from a diff: `mb-zb5t`. View file adds the controls |
| M04 | Pass |  |
| M05 | Pass |  |
| M06 | Pass |  |
| M07 | Pass | Wording finding `mb-5wqg` |
| M08a | Pass | Files changed matches GitHub; recorded OIDs agree with the mirror |
| M08b | Fail (P3); pass in the [rerun on #250](#rerun-on-250-view-file-landing-fixes) | Base and head reached only by URL or CLI: `mb-zb5t`. View file adds the controls; a symbolic link or submodule in a pull request was not run |
| M09 | Pass |  |
| M10 | Pass for the cases run | Private, revoked, and live rate-limit cases not run |
| M10b | Not run | Deferred (thin-mirror plan, Decisions) |
| M11 | Pass |  |
| M12 | Not run | Deferred (thin-mirror plan, Decisions) |
| M13 | Not run | Deferred (thin-mirror plan, Decisions) |
| R1 `#L` anchors and `?plain=1` | Pass |  |
| R2 Markdown Source tab gutter | Pass |  |
| R3 Keyboard anchors | Pass | Dispatched keys; focus ring and screen reader not observed |
| R4 Branch and tag selector | Pass |  |
| R5 Background refresh and newer revision | Pass | `file://` and GitHub |
| R6a Heading anchors and TOC rail | Pass |  |
| R6b TOC drawer toggle at narrow widths | Fail (P2) | Scrolls away; also on `main`: `mb-ddbe` |
| R7 Backslash filenames | Pass |  |
| R8 Served pull-request links (#238) | Pass |  |

### T0

**M01: local manual corpus.** The action served `tests/manual-fixtures` and then the
checkout root with the installed `metab`. The expected result is that existing views,
Git history and diffs, links, and themes keep working without console or network errors.

Actual: `overview.md` renders as a document, and its Source tab shows the line gutter.
`example.py` is highlighted source.
`record.json` opens as a Tree, `events.jsonl` as a log, and `status.svg` as an image.
The diff fixture shows split view in the dark theme, and in a 700 px pane its split
columns scroll horizontally, as the fixture intends.
A 4 KiB random file shows the Bytes view.
`opaque.bin`, whose content is ASCII, opens as text; the file is identical on `main`. On
the checkout root, the Git tab lists history, and a commit shows its detail with a split
diff. The console showed only performance warnings from the loaded machine, and every
request went to `127.0.0.1`.

The HTML Preview frame did not paint: the browser pane refused the sandboxed frame with
`net::ERR_BLOCKED_BY_CLIENT`. The server side was checked directly instead.
`/raw/<path>` answers 200 with
`content-security-policy: sandbox allow-scripts allow-popups allow-forms allow-downloads`
on a trusted folder, and the page loads as a top-level document.

### T1

**M02a: URL intent.** Every accepted form opened the same store, `sha256:b301cb88…` for
Hello-World:

- `github.com/octocat/Hello-World`, `www.` with `.git/`, `git@github.com:…`, and a URL
  with tracking parameters;
- `/tree/master`, and `/tree/test`, which pins `b3cbd5bb`;
- `/blob/master/README#L1`, which reports `lines: L1`, and `?plain=1#L1-L1`, which adds
  `plain: true`;
- `/commit/<full oid>` for the head and for the first commit;
- `raw.githubusercontent.com` URLs, with and without `refs/heads/`.

On `jlevy/metabrowser`, `/tree/codex/v012-markdown-anchors/tests/…/docs` pins `edef33c5`
on the slash branch.
`/blob/…/docs/%E9%9B%AA.md#L1` selects `tests/fixtures/github-markdown-repo/docs/雪.md`,
and `.../space%20name.md` on `main` selects `docs/space name.md`. A full and an
abbreviated commit ID both pin `edef33c5`.

Rejected and missing addresses exit 1 with a typed code, and most name the URL to open
instead: `unsupported_github_url` for issues and account pages, `insecure_http`,
`reserved_owner`, `invalid_pull_request`, `invalid_repository`, `credentials_in_url`,
`ref_not_found`, `path_not_found`, and `commit_not_found`. A cold cache opened
Hello-World in 3.0 s and `jlevy/metabrowser` in 5.9 s.

**M02b: raw Unicode and spaces.** The same paths pasted unencoded answer `non_ascii` or
`control_or_whitespace`. Each code says what is wrong but not how to recover, unlike the
other refusals. Filed as `mb-tals`, owned by #231.

**M03a: navigation within a revision.** The fixture README’s 11 links all resolve inside
the pin. They include Unicode, space, `100%25`, and `what%3F%23` names, and
`/CONTRIBUTING.md`, which resolves to the repository root as on GitHub; the
`javascript:` link is inert.
A link carrying `?plain=1#installation` opens the Source view.
Back and forward, reloading `/view/…` and `/commit/<oid>`, and opening a copied address
in a second tab each show the same file at `edef33c5`. The Git history starts at the
pin. No console errors appeared, and every resource came from `127.0.0.1`.

**M03b: base and head from a diff.** A commit diff’s file bar offers only “Copy path”,
so there is no way to open the file at either side from it.
Filed as `mb-zb5t`.

**M04: concurrent branches.** Two servers ran from one store, one on `main` and one on
`codex/v012-markdown-anchors`, and each was asked to refresh at the same moment.
Both refreshes succeeded, and both pins held.
`CHANGELOG.md` from each server hashes the same as `git show <pin>:CHANGELOG.md` for its
own pin.

The store is bare, with no `index` and no `worktrees`. Its refs are only
`refs/remotes/*` (126) and `refs/tags/*` (17), with `gc.auto=0`,
`maintenance.auto=false`, and `core.hookspath=/dev/null`.

A `file://` working checkout was served twice, and one server was switched to
`feature/x`. After both servers refreshed together, the checkout’s `HEAD`, refs, the
hashes of `index`, `config`, and `HEAD`, its `.git` listing, and `git status` (one
untracked file) were all unchanged.

**M05: offline restart.** The network was blocked for the process only.
On the warm cache, `--no-serve`, `--show`, and `--api` return the same commit IDs and
content, with `stale: true`. An explicit refresh returns `network_unreachable` and exits
1\. An uncached repository answers `network_unreachable` and publishes nothing.

A server started offline keeps its pin, highlights `#L1`, and labels itself “Refresh
failed · fetched 14 min ago”.
A served commit the mirror lacks reaches `selection_state: fetch_failed`, and the page
shows “Address not fetched” with a Retry button.
This state is distinct from `path_not_found` and `commit_not_found`. One-shot commands
never fetch, so offline they report a commit the mirror lacks as `commit_not_found`, as
they do online.

**M06: hostile content with a populated cache.** The home held four sources.
The mirrored hostile README, `tests/fixtures/untrusted-markdown` at `edef33c5`, rendered
with no script, form, input, iframe, SVG `use`, `set`, or `animate`, and no `style`
attribute. Its only ids are `user-content-…`, and there is no `#metabrowser` id.
The fake dialog is a plain `div`, and external images became links.
No KPress script loaded, every resource came from `127.0.0.1`, and the page sent its
Content-Security-Policy header.
`/api/capabilities` reports `active_content: false`.

An HTML file on a pin offers only Source, according to `--show`. `/raw?path=` sends a
sandbox without `allow-scripts`, and `/raw/<path>` answers 409
`unsupported_for_subject`.

Preview-origin requests were refused.
`/api/cache/sources` on a pin answers 409. A request with `Origin: null` and
`Sec-Fetch-Site: cross-site` is refused for `GET /api/tree`, `GET /api/source/status`,
and `POST /api/source/pin`. A `text/plain` POST answers 415.

In a `file://` hostile repository, `page.html` fetches `/api/cache/sources`. Opened at
`/raw`, it kept its title, and the console reported script execution blocked by the
sandbox. The README’s `<script>` and `onerror` were removed.

### T2

**M07: cold direct pull request.**
`metab https://github.com/cli/cli/pull/14128 --no-serve` ran on a cold home, with no
index, and took 13.4 s. It pinned the head `5dfc6b06`. The record holds the merged
state, 3 reviews (two `COMMENTED`, one `APPROVED`), 2 review comments, and 26 check
runs: 13 `success` and 13 `skipped`. Nothing was truncated, and the reader is
`gh:<login>`. `jlevy/metabrowser#3` and #234 opened in 10.0 s and 4.9 s.

In the browser, `/pull/14128` shows the header, the rendered description, the review
cards (including the approval), the review comments with `git/test.go:12` links to
`/view/…#L12` at the head, and the checks.

Review bodies render lazily when scrolled into view.
The hidden pane never fires the observer that triggers them, so the part route was
checked directly: `/api/plugin/github/pull-markdown?part=review/<id>` answers the
rendered, allowlisted HTML.

Finding `mb-5wqg`, owned by #233: the header reads “wants to merge into” on a merged
pull request, and the checks summary counts skipped runs as neutral.

**M08a: changed files.** For each pull request, the comparison’s file list equals
GitHub’s `pulls/<n>/files` in status, path, and previous path; only the status names
differ (`deleted` against `removed`). The totals match too:

- `cli/cli#14128`: 86 files, +304 −254, and the rename
  `internal/config/stub.go → internal/config/test.go` at 62% similarity.
- `metabrowser#3`: 91 files, +2237 −952. Five deletions show their hunks, and the added
  JPEG reads “Binary file; no textual diff.”
- `metabrowser#234` (open): 47 files, +4106 −625, with `base_from: base_branch`, a
  deletion, and a binary PNG.

The comparison’s old and new blob IDs equal `git rev-parse <merge-base>:<path>` and
`<head>:<path>` in the mirror.
`--show` at the head pin and at `/blob/<merge-base>/…` reads `README.md` as 7454 and
5681 bytes, and an unchanged Markdown file is 7330 bytes on both sides.

**M08b: base and head from Files changed.** The file bars offer only “Copy path”, so the
base side is reachable only through a URL or a pin switch.
See `mb-zb5t`.

**M09: offline reopen.** A cached pull-request read with the network blocked ran no gh
at all. `--no-serve` tried `gh auth status` and one conditional `gh api`, then reported
`network_error`, kept the record, and exited 0. A server started offline keeps the pin,
reports `network_unreachable`, and shows the cached conversation with “The last refresh
failed: gh could not reach api.github.com”.
Files changed shows 86 files and 109 hunks.
No gh process ran while that server served the pages.

**M10: typed failures.**

- A repository that does not exist answers `not_found_or_private` with a sign-in hint,
  exits 1, and publishes nothing.
  Git asked the gh credential helper only after GitHub’s challenge, and no credential
  appeared in any output.
- A pull-request number that does not exist answers `not_found_or_private` and pins the
  default branch.
- With `gh` missing from `PATH`, the pull request reports `gh_missing`, and a public
  repository still clones anonymously.
- Signed out: `not_logged_in` with “run gh auth login”, and the served page offers
  Fetch. No prompt appeared, and the empty config directory stayed empty.
- The stand-in older gh gives `gh_too_old`.

Not run:

- Authorized private access, because no operator-owned private fixture was provided.
- Revoked access.
- A live rate limit. `tests/golden/cli-github-pull-refresh.txt` covers `rate_limited`.

The not-found message says Git “has no credentials” even when gh supplied them; it is
recorded here as an observation.

**M11: interruption.** Every gh API read was delayed 8 s. SIGINT to `--no-serve` during
the refresh exited 130. SIGTERM to a server during `pull-refresh` exited 143. In both
cases the record’s SHA-256 was unchanged, and no staging entry or gh process was left
behind. After the restart, the record refreshed to `current` at the same pin.
Lock files planted in the store, `packed-refs.lock` and
`refs/remotes/origin/trunk.lock`, were removed by the next refresh, which succeeded.

### Round-2 features

**R1 `#L` anchors and `?plain=1`.** The banner reads `Selection: blob README#L1`.

- `#L10-L20` highlights lines 10–20; the gutter is a slider reading “Lines 10–20”.
- Clicking line 5 sets `#L5` without adding a history entry, and a Shift-click makes it
  `#L5-L12`.
- `#L30` highlights and scrolls to line 30.
- `#L99999` shows “Line 99,999 is past the end of this file, which has 238 lines.”

**R2 Markdown Source tab gutter.** `overview.md#L10` on a mirror opens the Source tab.
The YAML front matter and the Markdown body are separate blocks, the body offset by 7
lines, under one gutter numbered 1–14, with line 10 highlighted.

**R3 Keyboard anchors.** Down moves `#L10-L20` to `#L21`, and Shift+Down twice extends
it to `#L21-L23` ("Lines 21–23"). End goes to `#L238` and Home to `#L1`. Page Down goes
to `#L44` and scrolls.

**R4 Branch and tag selector.** `/api/source/refs` filters branches and lists tags
newest first, reports `total` and `truncated`, and answers 400 for `kind=commit`. In the
browser:

- Choosing tag `v0.11.0` from the selector keeps `README.md` on generation 2, and the
  button reads “Tag: v0.11.0”.
- A branch without the open file reloads at `/view/`.
- A filter that matches nothing reads “No branches match.”
- Escape closes the list and returns focus to the button.

**R5 Background refresh and the newer-revision offer.** With `file://`, a commit to the
origin produced “main is now at b56073026094 · Switch”, and Switch moved the page to the
new commit at generation 2.

With GitHub, the cached `codex/v012-acceptance` opened at `250a10c4` after this branch’s
push had moved it to `aa1f4d93`. The page offered “codex/v012-acceptance is now at
aa1f4d93ce02 · Switch”, and the switch succeeded.

**R6a Heading anchors and the TOC rail.** The mirrored
`docs/qa-v012-repository-library.md` has only `user-content-` heading ids.
The Contents rail shows 42 entries at 1700 px, and clicking an entry sets
`#user-content-…` and marks it active.
Reloading with the bare fragment `#phase-2-classify-and-refuse-no-acquire` scrolls to
that heading. At 1000 px the drawer opens from the toggle, and the backdrop or an entry
closes it.

**R6b The drawer toggle.** Once the document scrolls, the toggle scrolls out of view,
the same in a trusted folder.
`.preview-pane` is the scroller and, through its transform, also the containing block of
the toggle, which is `position: fixed`. The rule predates v0.12. Filed as `mb-ddbe`.

**R7 Backslash filenames.** The test repository holds `a\b.md`. The trusted folder lists
it as `a%5Cb.md`, and `[odd](a%5Cb.md)` opens it.
The mirror lists it as `a\b.md` and serves it by its wire path, while the same link
renders as text with no address, as the runbook documents.

**R8 Served pull-request links.** `/pull/999` on a server for #14128 links to
`/pull/14128`. The selector’s place in the navigation header reads “Pull request:
#14128”.

## Findings

| Bead | Priority | Owner | Summary |
| --- | --- | --- | --- |
| `mb-ddbe` | P2 | Pre-existing on `main`; surfaced by #240 | TOC drawer toggle scrolls away with the document in a narrow pane |
| `mb-tals` | P3 | #231 | Raw Unicode or space in a GitHub URL is refused without a recovery hint |
| `mb-5wqg` | P3 | #233 | “Wants to merge” on merged and closed pull requests; skipped checks counted as neutral |
| `mb-zb5t` | P3 | #233; commit diff pre-existing | No way to open a changed file at base or head from a diff |

## Limits of This Run

- The browser pane was hidden for most rows.
  Paint-only checks after M03 (focus rings, layout at each width, and the lazy
  review-body renders) were not observed.
  For those rows the evidence is DOM state, network and console reads, and route
  answers.
- The in-pane HTML Preview could not be exercised, because this browser refuses the
  sandboxed frame.
- There was no private fixture, so authorized private access and revoked access were not
  run.

## Rerun on #243

The rows that failed above were rerun on
[#243](https://github.com/jlevy/metabrowser/pull/243), which fixes `mb-ddbe`, `mb-tals`,
and `mb-5wqg` on top of #241, with a smoke pass of M01 and M05 on the new wheel.

| Item | Value |
| --- | --- |
| Head (`codex/v012-acceptance-fixes`) | `7d91c8f4a655d32070370d26408419d0970f4671` |
| Base (`codex/v012-acceptance`, #241) | `948861c42281f522941071da6011fbcf95fe9525` |
| `main` | `6c278f3f9e10aebcb34a207035aee7768a1bba0e` |
| Wheel | `metabrowser-0.11.1.dev412+7d91c8f4-py3-none-any.whl` from `make build`, whose distribution checks pass |
| Platform | macOS 26.5.2 (25F84), arm64; load average 44–89 |
| Tools | Git 2.50.1, gh 2.98.0, uv 0.12.8, Python 3.14.7, Node 24.19.0, KPress 0.3.5 |
| Browser | The Claude desktop browser pane, Chrome 152.0.7977.130 |
| Observation time | 2026-09-24, 23:11–23:39 UTC |

The method is the one above: a clean uv-managed Python 3.14 environment in `<scratch>`
with dependencies from `uv export --frozen --no-dev` and `UV_EXCLUDE_NEWER="14 days"`,
the installed `metab` entry point, one fresh application home and cache, and
`sandbox-exec -f offline.sb` for offline rows.
Servers ran on ports 8721–8729. Every gh call was a read-only GET of public data.

The browser pane was hidden again.
Screenshots worked, but each one showed the page as it was one step earlier, and the
page advanced its frames only while screenshots were taken.
Geometry and state were therefore read through the page’s JavaScript after a screenshot.
The toggle, backdrop, and TOC entries were clicked as real clicks.

| Row | Action | Expected | Actual | Result |
| --- | --- | --- | --- | --- |
| M02b raw forms | `--no-serve` on blob, `#L1`, `?plain=1#L1-L2`, tree, and raw-host URLs, with `雪.md` and `space name.md` unencoded | Each opens as its encoded spelling would | All ten open with the expected `selection`, `path`, `lines`, and `plain`; raw and encoded output are byte-identical | Pass |
| M02b refusals | U+202E, U+3164, a lone `%`, a tab, U+00A0, and a trailing space | Refused with the code point and the encoded spelling | Each exits 1 with its code, names the code point, and gives the spelling or a fix | Pass |
| M02b encoded | The spellings the refusals give | The reducer accepts them | `100%25.md` opens `100%.md`; `%E2%80%AE` and `%E3%85%A4` reach `path_not_found` | Pass; see `mb-1bpe` |
| M07 open | `jlevy/metabrowser#234` | github.com’s header | “jlevy wants to merge 10 commits into codex/v012-pr-view from codex/v012-inert-markdown”, the same words as github.com | Pass |
| M07 merged | `cli/cli#14128` | Merger and “merged” | “babakks merged 6 commits into trunk from bagtoad/probable-funicular”, the same as github.com | Pass |
| M07 closed | `cli/cli#14502`, `encode/httpx#3783` | “wants to merge” with the Closed badge | Matches, except that the base lacks its owner for a head in a fork | Pass; see `mb-v8sb` |
| M07 checks | #14128 (skipped), #3783 (cancelled) | Skipped and cancelled counted apart from neutral | “13 success · 13 skipped” and “1 failure · 4 cancelled”, with muted badges | Pass |
| TOC narrow | 1000 px light and dark in a trusted folder; 760 px dark in a mirror | The toggle is reachable at every depth | Toggle stays at (312, 16) and is hit-testable at every depth once shown, to the end | Pass |
| TOC drawer | Toggle clicked at the end of the document | The drawer covers only the pane | Drawer inside the pane; backdrop equals the pane; the tree is undimmed; backdrop and entry close it | Pass |
| TOC wide | 1700 px, light and dark, trusted and mirror, old CSS emulated | Unchanged | Rail sticky at 96, then 32; toggle hidden; rects identical to the old layout | Pass |
| Frame contents | Image, HTML Preview, Source `#L`, Git commit diff at 1000 px | Laid out inside the frame | All inside the pane; the HTML frame lays out but does not paint (below) | Pass |
| M01 smoke | The manual corpus | Each kind in its view | Markdown, source, Tree, log, image, and split diff render; no console errors | Pass |
| M05 smoke | Warm, then offline restart | Same content; honest offline state | Same content and `--show`; refresh `network_unreachable`; the server keeps its pin | Pass |
| M03b | Open a changed file at base or head from a diff | — | Not run: awaiting decision (`mb-zb5t`) | Not run |
| M08b | Open a changed file at base or head from Files changed | — | Not run: awaiting decision (`mb-zb5t`) | Not run |

**M02b.** The raw forms were run on a cold home against `jlevy/metabrowser` at `main`
and at `codex/v012-markdown-anchors` (`edef33c5`). The tree form was
`/tree/main/tests/fixtures/obsidian-vault/Notes/space note.md`, and the raw host was
tried with and without `refs/heads/`. The refusal texts were:

- `non_ascii`: “the URL contains U+202E, an invisible character; if it belongs in the
  address, write it as %E2%80%AE”, and the same for U+3164 with `%E3%85%A4`.
- `invalid_percent_encoding`: “the URL has a % not followed by two hexadecimal digits;
  write a literal % as %25”.
- `control_or_whitespace`: “the URL contains U+0009, a control character”, and for
  U+00A0 “a whitespace character; if it belongs in the address, write it as %C2%A0”. A
  trailing space gives “the URL ends with a space; remove it”.

Following the U+202E hint prints the missing path with U+FFFD in place of the override.
Following the U+3164 hint prints the filler raw, because it is a letter (Lo), not a
format character. Filed as `mb-1bpe` (P4).

**M07.** On github.com, a pull request from a fork names the base with its owner (“into
cli:trunk”, “into encode:master”). Metabrowser writes “into trunk” and “into master”,
and qualifies only the head.
Filed as `mb-v8sb` (P4). Same-repository pull requests match word for word.
`encode/httpx#3783` was chosen because its head has four `cancelled` runs and one
`failure`. None of the last 80 `cli/cli` pull requests had a cancelled run.

**TOC drawer (`mb-ddbe`).** The document was `docs/qa-v012-repository-library.md`,
served from this checkout as a trusted folder, where KPress’s scripts load, and as a
GitHub mirror of this branch, which uses the inert TOC.

- At 1000 px the pane is 700 px wide.
  In light, the toggle stayed at (312, 16), 32 × 32, at scroll depths 0, 2000, 12414,
  and the end, 24028, and `elementFromPoint` at its centre hit it each time.
  In dark it was measured at the end, with the same result.
- Opened from the end, the drawer was at (316, 64), 668 × 362, and the backdrop was
  exactly the pane (300, 0, 700 × 800). A point in the file tree hit the tree.
  A backdrop click closed the drawer.
  Clicking “Phase 4: file:// Acquire and the Pin” set the fragment, scrolled that
  heading to the pane’s top, and closed the drawer.
- In the mirror at 760 px, dark, the pane is 460 px wide.
  Before any scroll the toggle was at (312, 16) but not yet shown (opacity 0). At 3000,
  15000, and the end, 31055, it stayed at (312, 16) and was hit-testable, fading in to
  opacity 1. The drawer was 428 × 704 inside the pane.
  An entry set `#user-content-44-pin---api-with-g1--wires` and closed the drawer.
- At 1700 px the rail is sticky, at y = 96 at the top and y = 32 after 5000 px, and the
  toggle is `display: none`. The old rule was restored in the page
  (`.preview-pane { transform: translateZ(0) }`, with none on the frame).
  The rail, the prose, the `h1`, and `scrollHeight` were identical at both depths in all
  four combinations of theme and source.

Inside the new frame:

- `images/metabrowser-overview.jpg` scales to 652 × 367 inside the pane.
- `src/metabrowser/cli/main.py#L300-L305` scrolls the range into view, and the gutter
  reads “Lines 300–305”.
- `docs/development.md?plain=1#L120` opens the Source tab at line 120 with the gutter.
- The Git tab lists history.
  Commit `7d91c8f4` shows its split diff in the pane, and no element extends past the
  pane’s right edge.
- The HTML Preview frame of `explorations/diff-layout/benchmark.html` fills the pane
  below the tabs. As in the first run, this browser refused to load it
  (`net::ERR_BLOCKED_BY_CLIENT`). `/raw/…` answers 200 with its sandbox header.

**M01 smoke.** `--show` gives the expected kind and views for all seven fixtures.
In the browser:

- `overview.md` renders through KPress with Document and Source tabs;
- `example.py` is highlighted with the gutter;
- `record.json` opens as a Tree;
- `events.jsonl` opens as a log of 3 events;
- `status.svg` opens as an image;
- `syntax-layouts.diff` shows 5 files in split view.

No console errors appeared.

**M05 smoke.** `octocat/Hello-World` was warmed online and then run with the network
blocked. Offline:

- `--no-serve` exits 0 at `7fd1a60b`, and `--show README` is identical to the online
  run.
- The `/api/file` envelope for `g1-UkVBRE1F` (“Hello World!”) is byte-identical to the
  online one.
- An explicit `/api/source/refresh` ends `network_unreachable` and exits 1.
- `octocat/Spoon-Knife`, which is not cached, answers `network_unreachable`, and
  “nothing was published”.
- A server started offline keeps its pin, highlights `#L1`, and labels itself “Refresh
  failed · fetched 1 min ago”.
- A server started offline at an unfetched commit (`b99406db`, a pull-request head)
  reports `selection_state: fetch_failed` and “Address not fetched”.

One observation was outside the rows.
Navigating a served page to `/commit/<oid>` for a commit the mirror lacks shows “Could
not load this commit.”
It was not checked whether this predates #243.

### New Findings

| Bead | Priority | Summary |
| --- | --- | --- |
| `mb-v8sb` | P4 | The pull-request header omits the base’s owner when the head is in a fork |
| `mb-1bpe` | P4 | Path errors print default-ignorable characters such as U+3164 raw |

## Addendum (2026-09-30)

What changed after this run, without altering the results above:

- **The stack is linear.** It was restacked by merges into one chain, so the sibling
  layout under [Build](#build) no longer holds.
  #241 now sits on #240 and below #243, and its tree is the tested tree `948861c4` plus
  #242’s removal of an unused DOM test harness.
- **M03b and M08b.** View file is [#248](https://github.com/jlevy/metabrowser/pull/248)
  (`mb-zb5t`). Both rows are rerun on an installed wheel once it is on the stack, and
  the result is added to this record.
- **M10.** The private and revoked cases are **blocked**, in the alpha plan’s terms,
  until an operator-owned private fixture exists.
- **The two observations outside the rows** are filed and fixed in
  [#249](https://github.com/jlevy/metabrowser/pull/249): the not-found message that said
  Git had no credentials (`mb-2nu0`), and “Could not load this commit.”
  for a commit the mirror lacks (`mb-4kuc`).
- **A regression check against `main`** followed on 2026-09-30. Its measurements, and
  the startup and eager-load cost it found, are in `mb-l8c2`.

The alpha plan’s
[Landing status](../specs/active/plan-2026-09-22-v012-alpha-testing.md#landing-status)
lists what remains before the stack lands.

## Rerun on #250 (View file, landing fixes)

This is the rerun the addendum promises.
M03b and M08b, which failed above for want of a control, were run on the tip of the
linear stack, [#250](https://github.com/jlevy/metabrowser/pull/250), which holds View
file ([#248](https://github.com/jlevy/metabrowser/pull/248)) and the landing fixes
([#249](https://github.com/jlevy/metabrowser/pull/249)). The run also checks what #249
changed and repeats a short smoke on the new wheel.

| Item | Value |
| --- | --- |
| Head (`codex/v012-docs-reconcile`, #250) | `f9d88f503ac3f4ad0f006028072f92617467ddf9` |
| Base (`codex/v012-landing-fixes`, #249) | `f54b2560d0049fa587572612258d3674d13b0608` |
| `main` | `6c278f3f9e10aebcb34a207035aee7768a1bba0e` |
| Wheel | `metabrowser-0.11.1.dev468+f9d88f50-py3-none-any.whl` from `make build`, whose distribution checks pass |
| Platform | macOS 26.5.2 (25F84), arm64; load average 24–87 |
| Tools | Git 2.50.1, gh 2.98.0, uv 0.12.8, Python 3.14.7, Node 24.19.0, KPress 0.3.5 |
| Browser | The Claude desktop browser pane, Chrome 152.0.7977.130 |
| Observation time | 2026-10-01, 04:50–05:09 UTC |

The method is the one above: a clean uv-managed Python 3.14 environment in `<scratch>`
with dependencies from `uv export --frozen --no-dev`, the installed `metab` entry point,
and one fresh application home and cache.
Servers ran on ports 8771–8777. Every gh call was a read-only GET of public data.

The fixtures were public and recorded at the observation time:

- `jlevy/metabrowser` commit `8d7fe7f0bd4ea491dca4015bc0b006199c3ef1bf`, on `main`,
  whose parent is `da65dcd810d623256d03fe8725a12f36b76d24f0`. It modifies 4 files, adds
  6, deletes 6, and renames 1 (at 95% similarity).
- `cli/cli#14128` and `jlevy/metabrowser#3`, at the revisions under
  [Fixtures](#fixtures).
  GitHub’s comparison gives each one’s merge base as its recorded base: `c624f0ac…` and
  `5dfb02e7…`. `trunk` has since moved to `fc4b137c…`.
- The `file://` mirror of `tests/diff_view_file_fixture.py`, for the runbook’s section
  5.11: `second` is `6ac4c8b5eb94…` and `first` is `a5232ab93056…`.
- `octocat/Hello-World` at `7fd1a60b…`, for the checks of #249.

The browser pane was hidden, as before.
Each file was opened by a real click on its control.
The page’s state was then read through its JavaScript: the address, the commit in the
file header, the selector’s label, `/api/source/status`, and the blob ID that
`/api/file` reports for the address.
That blob ID was compared with `git rev-parse <commit>:<path>` for the commit rows, and
with GitHub’s `repos/<owner>/<repo>/contents/<path>?ref=<commit>` for the pull-request
rows. Reloads were `location.reload()`, confirmed by the navigation type `reload`,
because the reload key did nothing in the hidden pane.

| Row | Action | Expected | Actual | Result |
| --- | --- | --- | --- | --- |
| M03b controls | The diff of `8d7fe7f0`, on a server pinned to it | Each bar offers the sides its change has | 17 bars. Modified and renamed files have View at parent and View file, added files only View file, and deleted files only View at parent. View file is a link to `/view/…` “at 8d7fe7f0bd4e, the commit this page shows”; View at parent is a button, “Switch to da65dcd810d6 and open …” | Pass |
| M03b modified | `README.md`: View file, then View at parent | The file at each commit | Head `1abb32a2…` (9280 bytes) under `8d7fe7f0…`; parent `846aa5fa…` (9278 bytes) under `da65dcd8…`, after one `POST /api/source/pin`. Both equal Git’s | Pass |
| M03b added | `docs/project/README.md`: View file | The file at the head | `dfaff312…` under `8d7fe7f0…`; the path does not exist at the parent | Pass |
| M03b deleted | `docs/specs/file-search.md`: View at parent | The file at the parent | `9d0fd78e…` under `da65dcd8…`; the path does not exist at the head | Pass |
| M03b renamed | `docs/specs/metabrowser-v0.1.0.md → docs/project/specs/done/plan-2026-07-14-…`: View at parent, then View file | The old path at the parent and the new path at the head | Old path `c37ab565…` under `da65dcd8…`; new path `ad401138…` under `8d7fe7f0…` | Pass |
| M03b navigation | After each of the six opens: reload, Back, Forward, and the link’s address in a second tab | Selection and revision survive; Back returns to the diff | In all 24 actions the address, the commit in the header, the selector (“Commit: …”), and the blob ID were unchanged. Back showed the 17-file diff each time. After a switch, Back landed on the diff, reloaded once by itself onto the served commit, and swapped which control is the link | Pass |
| M03b second tab left open | A tab open on a file while the first tab switched the pin, twice | Content never silently switches to another commit | The tab kept its content under its own commit ID. Its data requests answered `409 pin_changed`, “the server now serves another revision; reload the page”. Loaded again, the address showed the served commit’s file under that commit’s ID | Pass |
| M03b runbook 5.11, steps 1 and 3–5 | The fixture mirror | As the runbook describes | 7 bars; `link` (symbolic link) and `vendor/lib` (submodule) have no control; View at parent on the rename opens `src/old_name.py` under `a5232ab93056…`, with `gone.txt` and no `added.txt` in the tree; View at parent on `gone.txt` opens “gone soon”; from the parent’s page, View file on `latin1-�.txt`, a name that is not UTF-8, opens “a Latin-1 name, edited” and returns the selector to “Branch: trunk”; `first` has only View file; `changes.patch` has no control | Pass |
| M08b controls | Files changed of `cli/cli#14128` | Each bar offers the sides its change has | 86 bars. The 84 modified files and the rename have View at base and View file; `git/test.go`, added, has only View file. View at base names `c624f0ac79b2`, the merge base, not `trunk`’s tip | Pass |
| M08b head | View file on `cmd/gen-docs/main.go`, `git/test.go`, and `internal/config/test.go` (the rename’s new path) | The files at the recorded head | `d6a317f5…`, `aa873a14…`, and `6f096e94…` under `5dfc6b06…`, each equal to GitHub’s blob at the head | Pass |
| M08b base | View at base on `cmd/gen-docs/main.go` and `internal/config/stub.go` (the rename’s old path) | The files at the merge base | `cb76f422…` and `fe5e277b…` under `c624f0ac…`, each equal to GitHub’s blob at the merge base. GitHub answers 404 for the new path at the base and for the old path at the head | Pass |
| M08b selector | View at base, Back, then View file | The selector names the pull request again at the head | On the base the selector reads “Commit: c624f0ac79b2”, and Files changed says “This page’s code is c624f0ac79b2, not the pull request’s head 5dfc6b06b53e” with “Switch to the head”. After View file it reads “Pull request: #14128” on `refs/pull/14128/head`, and the line is gone | Pass |
| M08b navigation | After each of the seven opens on the two pull requests: reload, Back, Forward, and the address in a second tab | Selection and revision survive; Back returns to Files changed | In all 28 actions the address, the commit, the selector, and the blob ID were unchanged, and Back showed Files changed with 86 or 91 bars | Pass |
| M08b deletion and binary | `jlevy/metabrowser#3`: `devtools/biome.py` (deleted) and `images/metabrowser-overview.jpg` (added, binary) | Explicit states; no side the change lacks | The deletion has only View at base, which opens `8ca98335…` under `5dfb02e7…`, GitHub’s blob at the merge base. The JPEG’s diff reads “Binary file; no textual diff.”, and its View file opens the Image view (1280 × 720) of `14431ec6…`, GitHub’s blob at the head. The selector returns to “Pull request: #3” | Pass |
| M08b symbolic link and submodule | — | No control | Not run on a pull request: neither public fixture changes one. The commit diff above shows none, and `viewFileSides` in `diff-view-file.js` decides for both surfaces | Not run |
| #249: a folder named like a URL | `metab file:notes` in a directory holding the folder `file:notes`: `--walk`, `--show README.md`, and served | The folder is served | `--walk` lists `README.md`; `--show` reports `kind: markdown`; the browser renders the document, with `active_content: true`. A folder named `git@github.com:o/r` is walked the same way | Pass |
| #249: a GitHub URL | `metab https://github.com/octocat/Hello-World`, `--no-serve` and served, in a directory holding the folder `https:/github.com/octocat/Hello-World` | GitHub opens, not the folder | Acquired store `sha256:b301cb88…` at `7fd1a60b…`, and the server says “Serving https://github.com/octocat/hello-world”. The one-slash spelling walks the folder | Pass |
| #249: a commit the mirror lacks, inside the window | `/commit/5dfc6b06…` on the Hello-World mirror, 22 s after a fetch | The typed state with Retry | “Commit not found · fetched just now”, “This commit is not in the mirror as fetched just now.”, and Retry. The page sent no refresh. `--api /api/git/commit/<oid>` answers 404 `commit_not_found` | Pass |
| #249: Retry | Retry clicked | A fetch, then what it found | “Fetching this commit…”, one `POST /api/source/refresh` (202), then “Commit not found · fetched just now” with “the fetch from the origin did not bring it: no branch or tag there reaches it.” | Pass |
| #249: outside the window | The same address 15 min after the last fetch | The page fetches by itself | The same sequence without a click. “Could not load this commit.” never appeared | Pass |
| Smoke: trusted folder | This checkout served as a folder | Markdown, source, and the Git panel render | `README.md` renders through KPress; `src/metabrowser/cli/main.py#L300-L305` is highlighted, with the gutter reading “Lines 300–305”; the Git tab lists the history, and the head commit shows its split diff with no View file control. No console errors | Pass |
| Smoke: doctor | `metab --doctor` | `11 plugin(s) OK` | `metab --doctor: 11 plugin(s) OK` | Pass |

Every row that ran passes, so no bead was filed.
A symbolic link or submodule in a pull request is the one case not run.

Three observations qualify the browser evidence:

- **Back in this pane does not use the back/forward cache.** A marker set on `window`
  was gone after Back, and the diff came back at the top, not where it was scrolled to.
  That is the path the last table of `explorations/history-landing/README.md` records
  for a browser with the cache off.
  The runbook’s step 6 of section 5.11, that Back with nothing switched keeps the page
  and its scroll position, was therefore not observable here.
  The served pages carry no `Cache-Control` header, which that step also checks.
- **One console error per Back after a switch.** On that path, as that document
  describes, the page comes back naming the old commit, its request for the tree is
  refused, and it reloads once.
  The browser logs the refusal as “Failed to load resource: the server responded with a
  status of 409 (Conflict)”, and the page warns `loadTree: HTTP 409`. The View file rows
  logged no other error.
  The page for a missing commit logs the two 404 answers of its routes the same way.
  Section 5.11’s pass line says “no console errors” without this exception.
- **A hidden page waits.** The commit view for a missing commit stays on “Loading
  preview…” while the page is hidden, the limit #249 states.
  The three rows above set `document.visibilityState` to `visible` and dispatched
  `visibilitychange`, as the first run did for the freshness rows.

## Addendum (2026-10-01)

Verification of the stack’s tip after its last functional pull requests, #251 to #258,
and of the steps the [runbook](../../qa-v012-repository-library.md) gained the same day.
No row of the manual matrix was run again, so the results above stand as recorded.

| Item | Value |
| --- | --- |
| Tip (`codex/v012-tests-git-pin`, #257) | `373b59a9fdec90ca0bba45648af02d746e6adf12` |
| `main` | `6c278f3f9e10aebcb34a207035aee7768a1bba0e`, an ancestor of the tip |
| Platform | macOS 26.5.2 (25F84), arm64 |
| Tools | Git 2.50.1, gh 2.98.0, uv 0.12.8, Python 3.14.7, Node 24.19.0 |
| Browser | Google Chrome 152.0.7977.83, headless, driven over the DevTools protocol with a throwaway profile |

### The Gate on the Tip

Bead `mb-67s1` records these, run from the tip on the same day:

- `make lint-check` and the full `make test` pass locally: 3,772 tests passed, 8 were
  skipped, and tryscript ran 264 commands.
- `make golden-update`, as one command on a clean tree, exited 0 and left
  `git status --short` empty, at a load average of 13 to 21.
- CI passes all nine checks on the tip:
  [run 36886011227](https://github.com/jlevy/metabrowser/actions/runs/36886011227).

### Startup Against v0.11.0

Twelve back-to-back pairs of v0.11.0 against a wheel built from the tip, taken with
`explorations/performance-loop/startup_pairs.py` (`mb-67s1`):

| Mode | CPU time, tip over v0.11.0 (median of 12 pairs) |
| --- | ---: |
| `--show` | 1.020 |
| `--api /api/tree` | 0.990 |
| `--version` | 0.956 |
| `--doctor` | 1.466 |

One `--show` pair of the twelve was above 1.1x, and none above 1.3x. `--doctor` does
more work by design: since #246 it validates the cache record contracts.
These agree with the instruction counts in exp-037
(`explorations/performance-loop/experiments/`).

The wall-clock ratios of the same pairs ranged from 0.46 to 2.25, which is noise: other
jobs loaded the machine during the run (one-minute load average 17 at the least, 52 at
the median, 97 at the most), and one CLI start took about 3 s. The wall-clock comparison
is still owed on a quiet machine, or the user may accept the CPU-time and instruction
evidence in its place; `mb-67s1` tracks it.

### Runbook Steps Run on the Tip

Each command the runbook gained or changed on 2026-10-01 was run as written, from a
checkout of the tip with a scratch application home.

| Step | What ran | Result |
| --- | --- | --- |
| Pins | The chain listing, `ALPHA_PR`, its checks, and both ancestry checks | The chain was 39 pull requests ending at #257; nine checks pass; both ancestry commands exit 0. GitHub’s stack 218 holds only #125 to #226 |
| 0.4 | `metab --doctor`, then with one cache schema damaged | `11 plugin(s) OK`; damaged, exit 1 with the contract and schema problems on stderr; healthy again once restored |
| 0.5 | `--doctor --plugins-dir` on a stand-in plugin at SDK 0.6, then 0.7 | Refused with the SDK message and exit 1; then `12 plugin(s) OK` |
| 1.1 | The focused selection, with `tests/test_cache_origin.py` in place of a file that no longer exists | 635 passed and 1 skipped (`the macOS filesystem rejects undecodable byte names`) in 9 min 50 s, at a load average of 36 to 190 |
| 1.2 | `make test-macos` | 19 passed, none skipped. `make test-live-github` was not run |
| 1.3 | `make golden-update` on a clean tree | Exit 0 and an empty `git status --short`, in 26 min 53 s at a load average of 23 to 52 |
| 1.4 | `devtools.check_startup_scripts` | 20 requests of 25 and 173 KB of 175 KB; exit 0 |
| 1.5 | `make test-report`, alone and with `REFS="origin/main ."` | Tables printed; 264 tryscript commands, the count `make test` ran |
| 3.2 | Folders named `file:notes` and `a::b`; an `https://` argument beside a folder of that name | Both folders read; the `https://` argument refused as `unsupported_github_url`; its one-slash spelling walked; no home created |
| 3.3 | An unreadable folder with `--walk` and served; an empty argument | Exit 2, `is not readable.`, both times; `invalid ROOT (empty)`, exit 1 |
| 3.4 | The folder in a browser, all eleven checks | As the runbook describes, with the limits and the one finding below |

**Step 3.4 in a browser.** The fixture was built and served by the runbook’s commands,
and each check was driven with real mouse and key events:

- The Contents rail shows at 1,700 pixels.
  At 1,000 the toggle sits at (312, 16) at the end of the document, the drawer opens
  inside the pane, and an entry or a click outside closes it.
- `example.py#L3-L5` highlights lines 3 to 5. A click and a shift-click give `#L8` and
  `#L8-L10` without adding history entries; Down, Shift+Down, Home, and End give `#L11`,
  `#L11-L12`, `#L1`, and `#L12`; `#L99999` gives the past-the-end notice.
- `overview.md#L3-L5` and `?plain=1` open the Source tab.
- The JSON tree folds and unfolds a row.
  Its copy button reads `Copied!` and puts the record on the clipboard as YAML; the
  header’s button copies the path.
  A copy control written without the owner mark did nothing.
- Both images load.
- **The HTML Preview frame painted** and ran the page’s script, which the browser pane
  of the earlier runs refused to load.
- Load more took `long.txt` from 2.0 MB of 2.8 MB to the whole file, 40,000 numbered
  lines, with nothing repeated at the seam.
- A commit made while the Git panel was open appeared after the Git tab was selected
  again, and its diff opened with no View file control.
- Both themes applied.
- No request left `127.0.0.1`.

**Finding.** `mb-tdmd`: after about five full page loads in one tab, the next page’s
requests waited for a connection, for 4.5 s in one run and 50.8 s in another, and the
page then logged `metabrowser plugin asset failed to load: … (timed out)`. With Chrome’s
back/forward cache disabled the same sequence did not wait.
`origin/main` has the same event-stream and `pagehide` code, so the code gives no reason
to call it a regression, but it was not run on 0.11.0. The runbook’s step 3.4 describes
it.

**Limits of this verification.**

- One browser, headless.
  Focus rings and screen-reader output were not judged, and Safari and Firefox were not
  tried.
- The print dialog was not opened.
  The print button was shown to call `window.print()` once, and the page was then
  inspected under emulated print media, where the file tree, header, tabs, and buttons
  are hidden.
- The only console error apart from the finding was the browser’s own request for
  `/favicon.ico`, which answers 404.
- Nothing here touched GitHub: Parts 3 and 4 of the runbook’s walk-through, and
  `make test-live-github`, were not run.
- The desktop app’s browser pane, hidden, pegged its renderer for minutes on a text
  window of about 315,000 very short lines.
  Stock Chrome opened the same file in about 3 s, so this is recorded as a limit of that
  pane, and the runbook’s fixture uses ordinary line lengths.

## Second Addendum (2026-10-01)

What followed the first addendum the same day, as the stack grew from #257 to #265. It
changes no result above.
No row of the manual matrix was run again.

### Start-Up Against v0.11.0, With Compiled Bytecode

The first addendum’s start-up pairs, and exp-037 before them, were taken in a shell that
sets `PYTHONDONTWRITEBYTECODE`, so neither build had compiled bytecode and each start
compiled every module it imported.
The comparison was repeated with bytecode compiled in both environments: fifteen
back-to-back pairs of v0.11.0 against a wheel built from #261’s head, `c16912f8`, at a
load average of 12 to 16 (`mb-67s1`, now closed).

| Mode | Instructions retired, median pair ratio | Pairs above 1.1x | Wall clock, median pair ratio |
| --- | ---: | ---: | ---: |
| `--show` | 1.033 | 0 of 15 | 1.068 (528 to 577 ms) |
| `--api /api/tree` | 1.040 | 0 of 15 | 1.028 (577 to 601 ms) |
| `--version` | 0.994 | 0 of 15 | 1.026 (384 to 413 ms) |
| Server spawn to its first `/api` answer | 1.039 | 0 of 15 | 0.980 (513 to 503 ms) |
| `--doctor` | 1.779 | 15 of 15 | 1.533 (385 to 629 ms) |

Start-up does 3 to 4 percent more work, and serving is unchanged.
The wall-clock ratios of single pairs still spread, from 0.94 to 1.49 for `--show`, with
7 of its 15 pairs above 1.1x, so the instruction counts are the steadier reading.
`--doctor` is about 250 ms slower by design, since it validates the cache record
contracts (#246); accepting that is the user’s decision.
#264 makes `startup_pairs.py` refuse to compare builds in different bytecode states, and
exp-037 has a dated addendum.

### The Release Rehearsal

The release checklist’s steps 1 to 5 were rehearsed on `c16912f8` against v0.11.0
(`mb-cf6y`; exp-038; [#265](https://github.com/jlevy/metabrowser/pull/265)). Nothing was
tagged, released, or merged.

| Step | Result |
| --- | --- |
| 1. Clean worktree, candidate confirmed | Pass |
| 2. `make verify` | Pass in one run: 3,877 tests passed and 8 skipped, seven of the live-GitHub tier and one that the macOS file system cannot run; 38 tryscript goldens; clean audits; distribution checks |
| 3. Previous-release performance loop | Not cleared. Four `compare_builds` runs found no row or tally difference, `--walk` output was byte-identical, and every responsiveness and correctness gate passed in all 32 headed captures. The `first_row_ms` wall-clock gate was missed by both builds on a loaded machine: v0.11.0 in 6 of 11 captures with bytecode, the candidate in 5 of 11 |
| 4. CI on the exact commit | Pass, 9 of 9 |
| 5. Changes reviewed, version proposed | 0.12.0. The changelog gaps it found are corrected in #264 |

Still owed: the headed pairs and the backend pairs on a quiet machine, on the final tip,
with bytecode in both environments.

### The Landing Gate

The gate (`mb-2g6f`) compares the stack with v0.11.0 on regular folders.
Its evidence audit and its data differential ran at #259’s head, `f62c16b1`; its browser
differential had not reported when this was written.
[Changes to existing behavior](../reviews/review-2026-10-01-v012-changes-to-existing-behavior.md)
holds what they found: the intended changes, the three differences restored in #264, and
two regressions being fixed above #265.

### Runbook Steps Run on #265’s Tree

The steps the runbook changed for #261 and #263 were run on #265’s tree (`25540fa2`,
which adds only documents) with an isolated application home and a `file://` origin, in
stock Chrome 152, headless.

| Step | What ran | Result |
| --- | --- | --- |
| Pins | The stack listing, the chain, the fork check, and `ALPHA_PR` | Stack #218 lists #125 to #265. The fork check printed `#260, #259`, because #260’s base had not yet been moved onto #265; with that base simulated the chain ends at #260 and the check prints nothing |
| 4.1 | `--no-serve` twice | `cloning … into <scratch home>/cache`, then `cloned … in 9.5 s (14.2 MiB)`; the second run prints the one `using the clone …` line; the identity lines are the same |
| 5.1, 5.2 | Serve the pin; the wire | stdout names no cache path. The status carries `name`, an `origin` under the home directory as `file://~/…`, and the `location`. `/raw`, `/api/cache/sources`, and the opaque origin answer as written |
| 5.3, steps 1 and 2 | The mirror’s headings | The navigation heading reads name, branch, commit; the branch gives way first as the column narrows, then the name. The copy control copies the full commit. The `mirror in` note is whole or absent. `git -C <location> log` lists commits |
| 5.11, steps 2 to 4 | View file on the fixture mirror | The headings read `origin trunk 6ac4c8b5eb94` and `origin a5232ab93056`, as the step now says |

**Finding.** `mb-hj9h`: on a mirror whose name is long
(`metabrowser-v012-landing-docs`), the name is drawn with an ellipsis while the note
still shows. The name’s box is 2/64 of a pixel narrower than its text when the note is
cut. A mirror named `squares` or `metabrowser` does not show it.
Step 2 of 5.3 names it.

**Not run.** 4.8 and 4.9, which clone from github.com: their text follows #261’s
description.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
