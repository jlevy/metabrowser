# QA Run: v0.12 Alpha Acceptance on the Integrated Stack

**Status:** Recorded 2026-09-24 for `mb-gnr9`. The rows run here pass, apart from four
findings filed as beads.
M10b, M12, and M13 were not run because the thin-mirror plan defers them.
This record is evidence for the landing decision (`mb-n2ro`), not that decision.
The failed rows were rerun on the fixes in #243; see [Rerun on #243](#rerun-on-243).

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
- `METABROWSER_HOME` and `XDG_CACHE_HOME` point into `<scratch>`. T1 used one home.
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
| M03b | Fail (P3) | No way to open base or head files from a diff: `mb-zb5t` |
| M04 | Pass |  |
| M05 | Pass |  |
| M06 | Pass |  |
| M07 | Pass | Wording finding `mb-5wqg` |
| M08a | Pass | Files changed matches GitHub; recorded OIDs agree with the mirror |
| M08b | Fail (P3) | Base and head reached only by URL or CLI: `mb-zb5t` |
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

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
