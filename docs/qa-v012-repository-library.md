# QA: v0.12 Repository Library and HTML Trust

**Status:** Active foundation procedure for the unreleased v0.12 Repository Library
stack. HTML trust is included through released `main`. Acquired Git is inspectable
through data modes; HTTP serving is not implemented at this stage.

The [v0.12 alpha test plan](project/specs/active/plan-2026-09-22-v012-alpha-testing.md)
defines the later repository-URL and direct-PR milestones, manual browser matrix, and
automated acceptance work.
Use this runbook for the foundation that is executable now.

This runbook tests the Git foundation and inherited HTML behavior: automated coverage
first, then numbered manual checks against **this** repository, with an explicit
pass/fail for each step and a list of what this procedure cannot prove.

`metab --help` is the flag reference for the build you are running.
The [command-line guide](command-line.md) is the other half: what each mode is for.
Where the two disagree, believe `--help`. Test layering lives in
[end-to-end testing](e2e-testing.md).
Acquisition, GitPath wires, and the one-subject rule live in
[repository sources and provider mirrors](project/architecture/arch-repository-sources-and-provider-mirrors.md).
The HTML-trust invariant lives in
[full-page HTML rendering and an explicit trust model](project/specs/active/plan-2026-08-06-html-rendering-and-trust-model.md)
and [SECURITY.md](../SECURITY.md).

Keep additional work on the existing stack until the stack is stabilized and approved
for landing. This procedure tests the current foundation; it does not implement URL
serving (`mb-ew38`) or archive containers (`mb-380k`).

## Pins

Verify the live SHAs before a run.
They move.

The Repository Library review line is one formal GitHub stack,
[#218](https://github.com/jlevy/metabrowser/stack/218). Do not check out the superseded
crumb slices (#208, #210, #211–#215).

| Lane | PR | Branch | Tip | What it adds |
| --- | --- | --- | --- | --- |
| Repository Library / Git pin | [#216](https://github.com/jlevy/metabrowser/pull/216) (consolidates #211–#215) | `cursor/v011-git-revision-pin-bd04` | the command below | GitPath / `file://` pin for `--show` and non-cache `--api`; review and acceptance work remains |
| HTML trust | [#209](https://github.com/jlevy/metabrowser/pull/209), merged to `main` | Included in the integration tip | verify ancestry below | `/raw` sandbox, `/api` same-origin proof, `--untrusted`, HTML preview kind, plus subsequent mainline hardening |

Every tip in this runbook is read from the live branch rather than written down, because
a SHA copied into prose is a baseline nothing maintains and it is stale by the next
push:

```shell
gh pr view 216 --repo jlevy/metabrowser --json headRefOid,headRefName,url
gh pr view 209 --repo jlevy/metabrowser --json state,mergeCommit,url
git merge-base --is-ancestor fd65812ba911e7fa0f6b5967d9240556c8c01c54 HEAD
```

Run both the Repository Library and HTML regression steps on the same selected
integration tip. HTML trust has landed and is inherited through `main`; no separate
checkout of the merged HTML branch is needed.
Serving acquired content still requires the URL-opening implementation to apply that
trust profile and prove it against a populated cache.

Layers of stack #218, bottom to top — the PRs that still exist as review units, not the
crumb slices they folded in:

`#125 → #134 → #136 → #139 → #140 → #217 → #216 → #225`

New testing, stabilization, and feature PRs extend this chain.
Landing is tracked by `mb-n2ro`.

## Constraints That Are Part of the Product

- **Isolate `METABROWSER_HOME`.** Every acquire or refuse step in this runbook uses a
  scratch home. A refuse that creates `~/.metabrowser` is a failure.
  Discard any home an earlier v0.12 development build wrote: its records are not
  migrated, and every `file://` mode refuses it with one message that says to move the
  cache directory aside or set `METABROWSER_HOME` to a different directory.
- **Git acquisition floor.** Acquisition requires Git **2.43.7** or a patched release on
  a newer track (see `ACQUISITION_PATCHED_TRACKS` in `src/metabrowser/git/process.py`
  and `tests/fixtures/repository-cache/git-version-gates.json`). Ubuntu’s
  `git version 2.43.0` is below the floor: it must refuse acquire and **must not create
  the application home**. Do not weaken the floor to make a local run pass.
- **ssh stays closed.** It is not acquired and not opened.
- **`file://` and `https://` are the origins acquired**, including GitHub web URLs,
  which the GitHub reducer rewrites to `https://github.com/<owner>/<repo>`. A bare
  filesystem path is never rewritten into a clone URL. Only Phase 4.7 and the live half
  of 4.9 use the network.
- **Nothing binds a port** on `--no-serve`, `--show`, or `--api`. “Serving” in the
  output is a failure on those modes.
- **Do not serve acquired Git.** `metab file://…` without `--no-serve` / `--show` /
  `--api` must refuse.
  Serving a **local filesystem** root (v0.10) is a different product and is in scope for
  the regression steps below.
- **Investigate every test failure.** Watch-backend and overlay-dependent failures
  require a recorded cause and comparable CI evidence.
  Do not regenerate goldens to conceal a host difference or count a failed local
  `make verify` as passed.

## Related Documentation

- [Using the command line](command-line.md)
- [End-to-end testing](e2e-testing.md)
- [Development](development.md)
- [Repository library and open from a Git URL](project/specs/active/plan-2026-08-11-open-repo-from-git-url.md)
- [CLI-first delivery map](project/specs/active/plan-2026-08-28-cli-first-delivery-map.md)
- [Views, models, and routes](project/architecture/arch-views-models-routes.md)

## Phase 0: Setup

### 0.1 Checkout and install

```shell
# Use the current top PR, including later stabilization/testing layers.
: "${ALPHA_PR:?Set ALPHA_PR to the current integration PR number}"
QA_HEAD="$(gh pr view "$ALPHA_PR" --repo jlevy/metabrowser --json headRefOid --jq .headRefOid)"
QA_CHECKOUT_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/mb-qa-checkout.XXXXXX")"
git fetch origin "$QA_HEAD"
git worktree add --detach "$QA_CHECKOUT_ROOT/checkout" "$QA_HEAD"
cd "$QA_CHECKOUT_ROOT/checkout"
git rev-parse HEAD
make install
```

**Pass:** `HEAD` matches `QA_HEAD`. `make install` uses the locked uv Python environment
and npm toolchain (`uv --config-file uv.toml sync --locked` and `npm ci` via Make).
Do not activate `.venv` or invoke raw `python` / `pip`.

**Fail:** A different tip with no note; a second environment manager; a contaminated
`uv.lock`.

### 0.2 Isolate the application home

```shell
git version
REPO="$(pwd)"
FILE_URL="file://${REPO}"
QA_HOME="${TMPDIR:-/tmp}/mb-qa-home.$$"
# Do not mkdir. A refuse must leave this path absent.
export METABROWSER_HOME="${QA_HOME}"
export REPO FILE_URL
printf 'git=%s\nrepo=%s\nfile_url=%s\nhome=%s\n' "$(git version)" "${REPO}" "${FILE_URL}" "${METABROWSER_HOME}"
test ! -e "${METABROWSER_HOME}"
```

`FILE_URL` must be `file://` plus an absolute POSIX path (three slashes after the scheme
when the path is `/…`).

**Pass:** `METABROWSER_HOME` is a path that does not exist yet.
`git version` is recorded.
The floor is **not** changed when the installed Git is `2.43.0`.

**Fail:** Using `~/.metabrowser`. Creating the home with `mkdir` or `mktemp -d` before
the refuse steps (that hid a write-on-refuse hole).
Rewriting a below-floor Git to “make acquire work.”

### 0.3 Confirm the live CLI surface

```shell
uv --config-file uv.toml run --frozen metab --help
```

**Pass:** Help lists `--no-serve`, `--show`, `--api`, `--walk`, and `--check-api`.
`--no-serve` is described as acquiring a `file://` or `https://` Git source, or a GitHub
web URL, without starting a server.

**Fail:** Missing `--no-serve`, or help that claims ssh acquire or serve-acquired-Git.

## Phase 1: Automated Tests (Repository Library Tip)

These tests monkeypatch `require_acquisition_git` where a real acquire is required, so
they can pass on ubuntu Git 2.43.0. That is deliberate.
The manual acquire steps in Phase 4 still refuse on that Git.

```shell
uv --config-file uv.toml run --frozen pytest \
  tests/test_cli_git_pin_golden.py \
  tests/test_cli_acquire.py \
  tests/test_cli_cache_acquire_golden.py \
  tests/test_cli_cache_recovery_golden.py \
  tests/test_cli_no_serve_surface.py \
  tests/test_cli_github_url_golden.py \
  tests/test_github_url_reducer.py \
  tests/test_github_credentials.py \
  tests/test_github_provider.py \
  tests/test_cache_resolve.py \
  tests/test_cache_remote.py \
  tests/test_acquire_stall_and_hangup.py \
  tests/test_cache_acquire.py \
  tests/test_cache_urls.py \
  tests/test_cache_layout.py \
  tests/test_cache_routes.py \
  tests/test_git_process.py \
  tests/test_git_tree_source.py \
  tests/test_source_session.py \
  tests/test_cli_show_mode.py \
  tests/test_cli_api_mode.py
```

**Pass:** Every selected test passed or was skipped for a documented reason (missing
`git` binary; installed Git already meets the floor so the below-floor live test skips;
non-POSIX). `tests/test_cli_git_pin_golden.py` pins `cli-git-pin.txt` against a
multi-entry `file://` origin with nested directories, Markdown, JSON, JSONL, an image, a
binary, an oversized blob, a symlink, an executable, a gitlink, and names containing a
newline, a tab, and a byte that is not UTF-8. It records `--show` kinds and routes,
index counts, `/api/tree` nesting with its lazy sentinel past `depth`, name order in
`/api/tree` against blob order in `/api/catalog`, file content on `g1-` wires, and the
404, 409, and 413 refusals.
Nothing in that golden prints `Serving`.

**Fail:** A failed assertion, a 500-shaped CLI envelope, or a golden update performed
without an intended product change.

This selection does not cover watcher/overlay behavior.
The complete `make verify` gate still applies.
Diagnose any failure before attributing it to the environment and record unresolved
failures as failures.

Regenerate the in-process pin golden only after an intended change:

```shell
GOLDEN_UPDATE=1 uv --config-file uv.toml run --frozen pytest tests/test_cli_git_pin_golden.py
```

## Phase 2: Classify and Refuse (No Acquire)

These steps must run even when Git is below the floor.
After each refuse, the scratch home must still be absent.

```shell
test ! -e "${METABROWSER_HOME}"
```

### 2.1 ssh is not acquired

```shell
uv --config-file uv.toml run --frozen metab \
  'ssh://git@example.com/owner/repo.git' --no-serve; echo "exit:$?"
uv --config-file uv.toml run --frozen metab \
  'ssh://git@example.com/owner/repo.git' --api /api/cache/layout; echo "exit:$?"
```

**Pass:** Non-zero exit.
stderr contains `ssh Git sources are not acquired yet`. No `acquired:`. No `Serving`.
`test ! -e "${METABROWSER_HOME}"` still holds.

**Fail:** Acquire proceeds; home is created; a 500; a wrong transport in the message
(for example “not served” on `--no-serve`).

### 2.2 ssh is not opened as a pin

```shell
uv --config-file uv.toml run --frozen metab \
  'ssh://git@example.com/owner/repo.git' --show README.md; echo "exit:$?"
uv --config-file uv.toml run --frozen metab \
  'ssh://git@example.com/owner/repo.git' --api /api/tree; echo "exit:$?"
```

**Pass:** Non-zero exit.
`--show` says `ssh Git sources are not opened yet`. `--api /api/tree` says
`ssh Git sources are not served yet`. `${METABROWSER_HOME}` is still absent.

**Fail:** Home created; pin attached; message claims the source was acquired.

### 2.2a GitHub URL shapes that are refused

```shell
for url in \
  'https://github.com/octo/demo/issues/5' \
  'http://github.com/octo/demo' \
  'https://github.com/settings/profile' \
  'https://ghp_example@github.com/octo/demo' \
  'https://github.com/octo/demo/pull/0'; do
  uv --config-file uv.toml run --frozen metab "$url" --no-serve; echo "exit:$?"
done
test ! -e "${METABROWSER_HOME}"
```

**Pass:** Each exits 1 with `invalid ROOT (<reason>): <message>`:
`unsupported_github_url` offering `https://github.com/octo/demo`, `insecure_http`,
`reserved_owner`, `credentials_in_url`, and `invalid_pull_request`. No message repeats
`ghp_example`. The home is still absent.
`tests/golden/cli-github-urls.tryscript.md` pins the full set.

**Fail:** A refused URL reaches Git or the network; a token echoed; the home created.

### 2.3 Serve, walk, and check-api refuse Git sources

```shell
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --no-open; echo "exit:$?"
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --walk; echo "exit:$?"
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --check-api; echo "exit:$?"
```

**Pass:** Non-zero exit.
Serve: `file Git sources are not served yet` and the text names `--no-serve` plus “ssh
stays closed.” Walk and `--check-api`: `file Git sources are not opened yet`. Nothing
listens. `${METABROWSER_HOME}` is still absent.

**Fail:** A server banner, a bound port, a walk dump, a check-api pass, or a created
home.

### 2.4 Below-floor Git refuses acquire without creating the home

```shell
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --no-serve; echo "exit:$?"
test ! -e "${METABROWSER_HOME}"
```

On Git **2.43.7+** (or a patched newer track) this command is Phase 4, not a refuse.
On Git **2.43.0** (ubuntu default):

**Pass:** Non-zero exit.
stderr contains `unsupported Git version` and names the detected line plus the required
floor (`2.43.7` / patched tracks).
No `acquired:`. The `METABROWSER_HOME` path is still absent.
This is a **known environment limit**, not a product bug, and not a reason to lower the
floor.

Repeat once with an empty directory already at `METABROWSER_HOME` (the `mktemp -d`
case). The refuse must leave that directory empty: no `cache/`, no `config.yml`.

The pin modes acquire through the same mapper, so repeat the refusal through them:

```shell
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --show README.md; echo "exit:$?"
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --api '/api/tree?depth=1'; echo "exit:$?"
test ! -e "${METABROWSER_HOME}"
```

**Pass:** The same one-line `unsupported Git version` error as `--no-serve`, with no
Python traceback and no staging or home path.

**Fail:** Home created on refuse; an empty existing directory written into an `f01`
skeleton; a 500; acquire succeeds on 2.43.0; the error omits the version fact; a pin
mode prints a traceback or a different message than `--no-serve`.

## Phase 3: Filesystem v0.10 Still Works

These commands use a **local path**, not `file://`. They do not acquire.
They may be served only if you are exercising the existing local server; this runbook
uses data modes so nothing binds a port.

```shell
uv --config-file uv.toml run --frozen metab . --show README.md
uv --config-file uv.toml run --frozen metab . --show AGENTS.md
uv --config-file uv.toml run --frozen metab . --show docs/development.md
uv --config-file uv.toml run --frozen metab . --show src/metabrowser/cli/main.py
uv --config-file uv.toml run --frozen metab . --api /api/cache/layout
```

**Pass:**

- Each `--show` prints `show:`, `route: /view/…`, a `kind`, `views`, and `model:` with
  no `Serving`.
- `README.md` and `AGENTS.md` are markdown (rendered + source).
- `docs/development.md` is markdown.
- `src/metabrowser/cli/main.py` is source.
- `/api/cache/layout` is HTTP 200. If the scratch home was never created, the envelope
  reports the home as `absent` and does **not** create `CACHEDIR.TAG`.
- Exit 0 on 2xx `--api`; the body is a JSON envelope, not a traceback.

**Fail:** HTTP 500; “is not a selection the browser can open”; a GitPath `g1-` wire on a
filesystem `--show` (filesystem identity is the inventory path, not the Git wire); cache
layout creating the home; `Serving` in the output.

Optional filesystem walk (large tree; not required for the pin lane):

```shell
uv --config-file uv.toml run --frozen metab . --walk --max-depth 1
```

## Phase 4: `file://` Acquire and the Pin

Skip the acquire/pin commands when Phase 2.4 already refused below-floor Git.
Record that skip.
Still run Phase 2. Do not install a different Git to “complete” Phase 4
on a floor-refusing host unless the operator’s job is to QA acquire itself on a patched
Git.

When the installed Git meets the floor:

### 4.1 Acquire without serving

```shell
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --no-serve
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --no-serve
```

**Pass:** Exit 0. Lines `acquired:`, `slug:`, `store: sha256:`, and `revision:`. No
`Serving`. No cache path, pack path, or `repository.git` in the text.
The second invocation prints the **same** identity (reuse).
Staging is empty after publish.

**Fail:** Port bind; different store on the second call without a reason; home paths in
stdout.

### 4.2 Cache `--api` after acquire

```shell
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --api /api/cache/layout
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --api /api/cache/sources
uv --config-file uv.toml run --frozen metab . --api /api/cache/sources
```

**Pass:** Each is HTTP 200. Layout `home` is `present` and `state` is `current`. Sources
list the acquired slug as `published`. The local-root `--api` sees the same slug: cache
routes resolve `METABROWSER_HOME`, not the served directory.
No cache filesystem path in the envelope.

**Fail:** `/api/tree` data from the origin appearing on a cache-inspect route; a 500;
the local-root inspect missing the slug.

### 4.3 `--show` on this repository’s real paths

```shell
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --show README.md
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --show AGENTS.md
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --show docs/development.md
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --show src/metabrowser/cli/main.py
```

`--show` accepts a display path or an already-encoded `GitPath` wire.

**Pass:** Exit 0. `show:` matches the argument.
`route:` is `/view/` plus `g1-` tokens (unpadded base64url per segment).
Kind/views match the blob: markdown docs, source for `main.py`. `model:` is a text
envelope. No `Serving`. No `METABROWSER_HOME` path in stdout.

**Fail:** HTTP 500; filesystem `/view/README.md` without a `g1-` wire; “not a GitPath”;
missing subject; serve leak.

### 4.4 Pin `--api` with `g1-` wires

Compute the wires from the same codec the routes use:

```shell
uv --config-file uv.toml run --frozen python -c '
from metabrowser.git.tree_source import GitPath
for path in (
    "README.md",
    "AGENTS.md",
    "docs/development.md",
    "src/metabrowser/cli/main.py",
):
    print(GitPath.from_display(path).to_wire(), path)
'
```

Then issue the routes (replace `WIRE` with each printed token):

```shell
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --api "/api/file?path=WIRE"
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --api "/api/tree?depth=1"
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --api /api/index/progress
```

The README blob wire in the in-process golden (a file named `README`, not `README.md`)
is `g1-UkVBRE1F`. That is a fixture spelling, not this repository’s `README.md`.

**Pass:** HTTP 200. File envelopes have `"subject": "git_revision"`, `"path"` equal to
the wire, a replacement-safe `"display"`, and content bytes for these text files.
Tree has `"subject": "git_revision"` and `"kind": "tree"`. Progress has
`"provider": "git"`, `"status": "done"`, `"complete": true`. No `Serving`.

**Fail:** 500; `"subject": "filesystem"` on a pin; a display path accepted as `path=`
without a `g1-` prefix succeeding as if it were a wire (the query `path` is a wire);
missing `--api` subject; raw cache paths in the body.

### 4.5 Pins always run under the untrusted profile

Acquired content is third-party, so no flag or environment variable lifts the profile on
a pin.

```shell
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --api /api/capabilities
METAB_ACTIVE_CONTENT=1 METAB_ALLOW_EDITS=1 \
  uv --config-file uv.toml run --frozen metab "${FILE_URL}" --api /api/capabilities
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --show README.md --allow-edits; echo "exit:$?"
```

**Pass:** Both capability envelopes report `"active_content": false` and
`"mutations": false`. The `--allow-edits` call exits non-zero with
`--allow-edits is not available on an acquired Git source`.

**Fail:** `"active_content": true` on a pin; `--allow-edits` accepted or silently
ignored.

### 4.6 GitHub URLs without the network

`tests/test_cli_github_url_golden.py` opens every accepted GitHub URL shape end to end
with a local origin standing in for `https://github.com/octo/demo`, and pins the result
in `tests/golden/cli-github-url-open.txt`. Read the transcript rather than rerunning it:
every spelling of the repository prints one slug and store; `/tree/release/v1/docs` pins
the `release/v1` branch; `/blob/…?plain=1#L3-L4` reports `lines` and `plain`; a branch
named `523f` wins over the commit whose ID starts with those digits; and a missing ref,
commit, or path is `ref_not_found`, `commit_not_found`, or `path_not_found`.
Pull-request URLs are 4.9.

```shell
uv --config-file uv.toml run --frozen pytest tests/test_cli_github_url_golden.py \
  tests/test_github_credentials.py tests/test_acquire_stall_and_hangup.py -rs
```

**Pass:** All pass; the credential test shows `gh` answering only for
`https://github.com` and the user’s own helper cleared; the stall test fails a stalled
origin as `timed_out`; the hangup tests exit 129 with no Git helper left running (the
last one skips below the Git floor).

**Fail:** Any failure; a golden regenerated without an intended change.

### 4.7 GitHub URLs over HTTPS (network, opt-in)

Skip on a floor-refusing Git and record the skip.
Read-only: nothing here writes to GitHub.

```shell
METABROWSER_LIVE_GITHUB=1 uv --config-file uv.toml run --frozen pytest -rs \
  tests/test_github_live_smoke.py
uv --config-file uv.toml run --frozen metab \
  'https://github.com/octocat/Hello-World/blob/master/README#L1' --no-serve
uv --config-file uv.toml run --frozen metab \
  https://github.com/octocat/Hello-World --api /api/git/repo
```

**Pass:** The smoke test passes.
The first command prints `acquired: https://github.com/octocat/hello-world`, then
`selection: blob`, a `pin:` on `branch master`, `path: README`, and `lines: L1`. The
second answers from the cache with the same revision and no clone.
On a terminal, the first clone reports its phases and elapsed time on stderr.
A signed-in `gh` is used only for github.com, and a public repository needs none.

**Fail:** A token prompt; a message containing Git’s own error text or a local path; a
second clone on the cache hit.

### 4.8 A terminal hangup cancels a first clone

Start a first clone of a large public repository in a terminal you can close, then close
the terminal while it reports `fetching every object`.

**Pass:** No `git` or `git-remote-https` process for that URL remains
(`ps -A -o pid,args | grep remote-https`), and the scratch home’s `cache/staging` is
empty after the next `metab` command.
`tests/test_acquire_stall_and_hangup.py` asserts the same without a terminal.

**Fail:** An orphaned Git process still fetching; a staging entry left behind.

### 4.9 Pull-request data

Without the network, read the two transcripts rather than rerunning them:
`tests/golden/cli-github-pull.tryscript.md` reads four cached pull requests (open from a
fork, merged, closed with its fork deleted, and a draft) with no `gh` at all, and
`tests/golden/cli-github-pull-refresh.txt` fetches, refreshes, and refuses them through
a fake `gh`, listing every `gh` call after each command.

```shell
uv --config-file uv.toml run --frozen pytest tests/test_github_pulls.py \
  tests/test_cli_github_pull_golden.py
npx --no-install tryscript run tests/golden/cli-github-pull.tryscript.md
```

**Pass:** All pass. In the refresh transcript, the first open of `/pull/7` runs
`gh auth status`, six `gh api` reads, and `gh auth status` again; `--no-serve` sends
`If-None-Match` on all six; a cached read runs no `gh`; and each failure exits 0 with
its typed state on the `pull_request` line (`not_found_or_private`, `not_logged_in`,
`gh_too_old`, `rate_limited`, `network_error`, `account_changed`, `head_mismatch`,
`gh_missing`), pinned at the cached head when there is a record and at the default
branch when there is none.
In `cli-github-url-open.txt`, `/pull/7` pins the default branch and
`/pull/7/commits/89e0fad` that commit when `gh` fails, as before pull-request data.
In `cli-github-pull.tryscript.md`, pull requests 12, 13, and 14 answer `absent` with
`schema_mismatch`, `unreadable`, and `not_cached`.

With the network, a signed-in `gh` 2.81.0 or newer, and a Git the floor admits
(read-only; nothing is written to GitHub):

```shell
METABROWSER_LIVE_GITHUB=1 uv --config-file uv.toml run --frozen pytest -rs \
  tests/test_github_pull_live_smoke.py
uv --config-file uv.toml run --frozen metab \
  https://github.com/pallets/markupsafe/pull/507 --api /api/plugin/github/pull
```

**Pass:** The smoke test’s Files changed matches GitHub’s file list for merged fork pull
request 507 and for an open pull request.
The command prints `pin: <head> (pull request 507 head)` and
`pull_request: 507 (merged; fetched … by gh:<login>)` on stderr, then a `current` record
whose `comparison.base_from` is `base_sha`. Run again, it answers from the cache.

**Fail:** A `gh` call on a cached read; a token, scope, or `gh` output in a message; a
record whose Files changed differs from GitHub’s; a failure without its typed state; a
traceback.

## Phase 5: HTML Trust on the Integration Tip

The selected integration tip must include the merged HTML trust implementation:

```shell
git merge-base --is-ancestor fd65812ba911e7fa0f6b5967d9240556c8c01c54 HEAD
```

Keep running from that tip so these checks exercise the actual combined build.

### 5.1 Automated HTML tests

```shell
uv --config-file uv.toml run --frozen pytest \
  tests/test_html_kind.py \
  tests/test_html_detect.py \
  tests/test_html_preview_js.py \
  tests/test_content_trust.py \
  tests/test_raw_passthrough.py \
  tests/test_raw_path_route.py \
  tests/test_capabilities.py
```

**Pass:** All selected tests pass.
`test_content_trust.py` pins sandbox headers on `/raw` and same-origin proof on `/api`.
`test_html_kind.py` pins preview-vs-source defaults and `--untrusted` /
`active_content=False` dropping preview.

**Fail:** Preview registered without the html plugin; `/raw` without the opaque-origin
sandbox; `/api` accepting a cross-site write.

### 5.2 Manual filesystem HTML (not acquired Git)

The HTML `--show` golden uses a throwaway `showroot`. Recreate that shape; do not serve
a `file://` pin.

```shell
HTML_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/mb-qa-html.XXXXXX")"
printf '<!doctype html>\n<title>Page</title>\n<p>Hello</p>\n' > "${HTML_ROOT}/page.html"
printf '<div class="card">hello</div>\n' > "${HTML_ROOT}/card.html"
uv --config-file uv.toml run --frozen metab "${HTML_ROOT}" --show page.html
uv --config-file uv.toml run --frozen metab "${HTML_ROOT}" --show card.html
uv --config-file uv.toml run --frozen metab "${HTML_ROOT}" --untrusted --show page.html
```

**Pass:** `page.html` is `kind: html`, views `preview (default), source`. `card.html` is
`kind: html`, views `preview, source (default)`. `--untrusted` drops preview (source
only). No `Serving` on `--show`.

**Fail:** Both files default to preview; `--untrusted` still offers preview; html files
still classified as catch-all `text`.

`--untrusted` is also `METAB_UNTRUSTED=1`. `--no-active-content` /
`METAB_ACTIVE_CONTENT=0` is the individual script switch.
See the [command-line guide](command-line.md).

### 5.3 Optional: local filesystem serve for `/raw` headers

Serving **this fixture directory** is v0.10 local browse, not acquired Git.
Skip if the environment has no way to issue HTTP. Do not point the server at a cache
store.

```shell
# On the selected integration tip. Stop the process when done.
uv --config-file uv.toml run --frozen metab "${HTML_ROOT}" --no-open
# Then GET /raw/page.html and require the opaque-origin sandbox headers
# pinned by tests/test_content_trust.py. Do not use a browser that the
# runbook cannot drive as a substitute for those assertions.
```

**Pass:** `/raw` carries the sandbox CSP from that test module.
`/api` rejects cross-origin writes.
The process is stopped.

**Fail:** `text/html` on the application origin with no sandbox; `/api` invoked from the
preview origin.

A hosted UI / real-browser click-through of the preview iframe is **out of scope** for
an agent host without a browser.
Record it as untested, not as a pass.

## Phase 6: What This Runbook Cannot Test

These are documented product gaps or environment limits.
Do **not** file beads for them unless the run shows **wrong** behavior (for example, ssh
was acquired, or `file://` was served).

| Item | Why it is out of scope here |
| --- | --- |
| ssh acquire | Closed; refuse is the test |
| Refresh, pin switching, and a missing ref fetched in the background | Arrive with the refresh coordinator; these modes read the mirror as it is |
| Pull-request page, and refreshing pull-request data in the background | Later steps; pull-request data is read through `--api` (4.9) |
| Serving acquired Git | `mb-ew38`; refuse is the test |
| Hosted-review / GitHub PR slice | Separate beads; not on these tips |
| Archive containers | `mb-380k` |
| Real browser HTML preview | Needs a browser; Phase 5.3 is optional and header-level |
| Below-floor acquire success | Forbidden; ubuntu 2.43.0 must refuse |
| Overlay / `watch_backends` host differences | Investigate separately; record any unresolved failure |
| Landing / merging the v0.12 stack | `mb-n2ro`; this runbook does not merge |

## Hunt List (File a Bead Only for a Real Defect)

While executing, treat these as bugs if they happen:

- Wrong refuse string (transport or mode mismatch)
- HTTP 500 or a traceback instead of `CLIError`
- Missing `--api` `subject` on a pin (`git_revision` expected)
- `Serving` or a bound port on `--no-serve` / `--show` / `--api`
- Application home created on a refuse (ssh, a refused GitHub URL, serve, walk,
  check-api, below-floor Git)
- A GitHub token offered to a host other than github.com, or a token or query string
  echoed in an error
- An orphaned Git process after Ctrl-C or a terminal hangup
- Filesystem `--show` failing on this repository’s real paths
- Pin `--show` / `--api` failing on those same paths when Git meets the floor
- Cache inspect exposing origin objects through `/api/tree` on a cache route

Honest parents: `mb-k7zy` (epic), `mb-z335` (Git-tree source / pin), `mb-3bna` (source
session), `mb-h51g` (acquisition), `mb-cun0` (HTML `/raw` sandbox).
Do not start `mb-ew38`, `mb-380k`, `mb-oueh` (unless the defect is exactly that bead),
or reopen the completed HTML publication bead `mb-d658`. Do not close unfinished product
beads from a QA run.

Record pass/fail in the pull request or the QA bead.
Do not rewrite this procedure into a changelog of one host’s run.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
