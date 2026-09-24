# QA: v0.12 Repository Library and HTML Trust

**Status:** Active foundation procedure for the unreleased v0.12 Repository Library
stack. HTML trust is included through released `main`. Acquired `file://` Git is
inspectable through data modes and served in the browser as an immutable pin under the
forced untrusted profile.
The served mirror refreshes from its `file://` origin in the background, and the pin can
switch to another branch, tag, or commit of the same mirror; https and ssh stay closed.

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
Serving a `file://` pin applies that trust profile, and Phase 5 proves it against a
populated cache over HTTP and in a browser.

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
  filesystem path is never rewritten into a clone URL. Only Phase 4.8 and the live half
  of 4.10 use the network.
- **Nothing binds a port** on `--no-serve`, `--show`, `--api`, or `--check-api`.
  “Serving” in the output is a failure on those modes.
- **A served pin is always untrusted.** `metab file://…` or `metab https://…` with no
  mode flag acquires or reuses the store and serves the commit its URL selects; ssh
  refuses. Serving a **local filesystem** root (v0.10) is a different product and is in
  scope for the regression steps below.
- **Only a server, or an explicit refresh request, fetches.** A served mirror refreshes
  from its origin in the background; `--show`, `--api`, and `--check-api` never fetch
  unless the command is `--api /api/source/refresh`.
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

**Fail:** Missing `--no-serve`, or help that claims ssh acquire or serve.

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
  tests/test_cli_api_mode.py \
  tests/test_serve_pin.py \
  tests/test_cache_update.py \
  tests/test_source_refresh.py \
  tests/test_cli_git_refresh_golden.py \
  tests/test_refresh_signals.py \
  tests/test_source_freshness_session.py \
  tests/test_source_kind_session.py
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
Nothing in that golden prints `Serving`. `tests/test_serve_pin.py` runs serve mode
in-process with only uvicorn and the port search patched, then drives the real
application lifespan and routes over HTTP: the banner golden `serve-pin-banner.txt`, the
forced profile, a fresh pin per start and a clean close at shutdown, tree, file, raw and
its sandbox headers, history, commit detail and comparison, and a populated-cache
isolation sweep over every registered GET route.
`tests/test_cache_update.py` refreshes real stores from real origins: new commits, a
force-push that keeps the old commit readable, a deleted branch pruned by name and
readable by ID, a fetch lock another process holds, stale lock files, a fetch cancelled
mid-transfer, a removed origin, and on a case-insensitive filesystem a ref the fetch
folded into its case twin, which is put back and reported as `ref_case_collision`.
`tests/test_refresh_signals.py` runs the real command and interrupts a refresh
mid-fetch: Ctrl-C or a terminal hangup leaves no Git running and the fetch lock free,
and a killed server’s Git keeps the lock until it exits; it needs an admitted Git and
skips below the floor.
`tests/test_source_refresh.py` drives the served routes over HTTP, including the
newer-revision offer and switch, joined refreshes, refresh on open, shutdown
cancellation, and the cross-origin, form, and GET refusals.
`cli-git-refresh.txt` and `cli-ui-source-freshness.tryscript.md` pin the refresh and
switch transcripts and the browser’s freshness session.

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

### 2.3 ssh is not served; `--walk` and `--allow-edits` refuse a pin

```shell
uv --config-file uv.toml run --frozen metab \
  'ssh://git@example.com/owner/repo.git' --no-open; echo "exit:$?"
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --walk; echo "exit:$?"
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --no-open --allow-edits; echo "exit:$?"
```

**Pass:** Non-zero exit.
ssh serve: `ssh Git sources are not served yet` and “ssh stays closed.”
Walk: `--walk runs the filesystem inventory walker` and names
`--api '/api/tree?depth=N'`. `--allow-edits`:
`--allow-edits is not available on an acquired Git source`. Nothing listens.
`${METABROWSER_HOME}` is still absent.

**Fail:** A server banner, a bound port, a walk dump, or a created home.

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
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --check-api; echo "exit:$?"
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --no-open; echo "exit:$?"
test ! -e "${METABROWSER_HOME}"
```

**Pass:** The same one-line `unsupported Git version` error as `--no-serve`, with no
Python traceback and no staging or home path.
Serve prints no banner and binds nothing.

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

### 4.6 `--check-api` on the pin

```shell
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --check-api; echo "exit:$?"
```

**Pass:** Exit 0. `api check:` names `${FILE_URL}`.
`live filter: 409; unsupported_for_subject`, because a pin has no mtimes, then
`index: done`, `final nav` and `filtered nav` rows, and `result: pass`. Nothing listens.

**Fail:** `result: fail`; a 200 live filter with invented recency; `Serving`.

### 4.7 GitHub URLs without the network

`tests/test_cli_github_url_golden.py` opens every accepted GitHub URL shape end to end
with a local origin standing in for `https://github.com/octo/demo`, and pins the result
in `tests/golden/cli-github-url-open.txt`. Read the transcript rather than rerunning it:
every spelling of the repository prints one slug and store; `/tree/release/v1/docs` pins
the `release/v1` branch; `/blob/…?plain=1#L3-L4` reports `lines` and `plain`; a branch
named `523f` wins over the commit whose ID starts with those digits; and a missing ref,
commit, or path is `ref_not_found`, `commit_not_found`, or `path_not_found`.
Pull-request URLs are 4.10.

```shell
uv --config-file uv.toml run --frozen pytest tests/test_cli_github_url_golden.py \
  tests/test_github_credentials.py tests/test_acquire_stall_and_hangup.py -rs
```

**Pass:** All pass; the credential test shows `gh` answering only for
`https://github.com` and the user’s own helper cleared; the stall test fails a stalled
origin as `timed_out`; the hangup and SIGTERM tests exit 129 and 143 with no Git helper
left running, an ignored hangup stays ignored, and the installed-CLI hangup test skips
below the Git floor.

**Fail:** Any failure; a golden regenerated without an intended change.

### 4.8 GitHub URLs over HTTPS (network, opt-in)

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
The smoke test calls the real `gh` only for the read-only size check; its clones run
with a fake `gh` that answers nothing.

Then serve the same repository at a file, from a terminal you keep open:

```shell
uv --config-file uv.toml run --frozen metab \
  'https://github.com/octocat/Hello-World/blob/master/README#L1' --no-open --port 8475
curl -s http://127.0.0.1:8475/api/source/status; echo
curl -s -X POST -H 'Content-Type: application/json' -d '{}' \
  http://127.0.0.1:8475/api/source/refresh; echo
```

**Pass:** The banner prints
`Serving https://github.com/octocat/hello-world at http://127.0.0.1:8475/view/g1-UkVBRE1F#L1`,
then `Revision: <commit> (master)` and `Selection: blob README#L1`. Status names
`"ref_name": "master"`; the refresh answers `202`, and status soon reports
`"last_outcome"` with `"operation": "refresh"` and `"outcome": "succeeded"`. Opening the
printed address shows the README.

**Fail:** A token prompt; a message containing Git’s own error text or a local path; a
second clone on the cache hit; a refresh outcome other than `succeeded` on a working
network.

### 4.9 A terminal hangup cancels a first clone

Start a first clone of a large public repository in a terminal you can close, then close
the terminal while it reports `fetching every object`.

**Pass:** No `git` or `git-remote-https` process for that URL remains
(`ps -A -o pid,args | grep remote-https`), and the scratch home’s `cache/staging` is
empty after the next `metab` command.
`kill <pid>` (SIGTERM) behaves the same and exits 143; under `nohup`, closing the
terminal does not stop the clone.
`tests/test_acquire_stall_and_hangup.py` asserts all three without a terminal.

**Fail:** An orphaned Git process still fetching; a staging entry left behind.

### 4.10 Pull-request data

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
`schema_mismatch`, `unreadable`, and `not_cached`. `/api/source/status` on `/pull/7`
names `refs/pull/7/head` and `pull_request: 7`; `pull-refresh` answers `202` with
`refreshing: true` (`pending` for 14), `409 no_pull_request` for a repository URL, and
`405` for a GET. In `tests/test_github_pulls.py`, a served `/pull/7` pins its head, a
refresh through `pull-refresh` runs as one coordinator job that a second request joins,
a newer head behind `refs/pull/7/head` is offered as `latest` and taken through
`/api/source/pin`, and a held fetch lock ends in `refreshing_elsewhere`.

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

## Phase 5: Serve the Pin (T1 Browser Subset, No Network)

Skip this phase when Phase 2.4 refused below-floor Git, and record the skip.
It covers the rows of the
[alpha manual matrix](project/specs/active/plan-2026-09-22-v012-alpha-testing.md) that a
`file://` pin can run without GitHub: M03 (links, reload, and history within one
revision), M05 (reopen with the origin gone), and M06 (hostile content with a populated
cache), plus refresh and pin switching (5.6), and the part of M04 one server can show:
switching branches within one repository.
Stop every server you start with Ctrl-C.

### 5.1 Start the server

```shell
uv --config-file uv.toml run --frozen metab "${FILE_URL}" --no-open --port 8471
```

**Pass:** `Serving ${FILE_URL} at http://127.0.0.1:8471/view/`, then
`Revision: <full commit> (<branch>)` with the `revision:` from 4.1 and this checkout’s
current branch, then `Plugins: …`. No cache path in the output.
The process keeps serving.
If the port was taken, use the one the banner names below.

**Fail:** A refusal; a different revision; a `METABROWSER_HOME` path in the output.

Starting instead with `--path docs/` or `--path ./README.md` prints a URL ending in the
directory’s `/view/g1-…/` or the file’s `/view/g1-…`; `--path nope.txt` exits 1 with
`--path target is not in the pinned revision`.

### 5.2 The wire, from a second terminal

```shell
BASE=http://127.0.0.1:8471
README_WIRE=g1-UkVBRE1FLm1k   # README.md, from the codec in 4.4
curl -s "$BASE/api/source/status"; echo
curl -s -D - -o /dev/null "$BASE/raw?path=$README_WIRE"
curl -s -i "$BASE/raw/README.md"; echo
curl -s -i "$BASE/api/cache/sources"; echo
curl -s -o /dev/null -w '%{http_code}\n' -H 'Origin: null' "$BASE/api/source/status"
curl -s "$BASE/api/capabilities"; echo
```

**Pass:**

- `/api/source/status` has `"subject": "git_revision"`, `"pin"` equal to the `Revision:`
  commit, `"ref": "refs/remotes/origin/<branch>"`, and `"ref_name": "<branch>"`.
- `/raw?path=…` answers 200 with
  `content-security-policy: sandbox allow-popups allow-forms allow-downloads` (no
  `allow-scripts`) and `x-content-type-options: nosniff`.
- `/raw/README.md` answers 409 with `"capability": "raw_document_path"` and the same
  sandbox header: the path form is refused on a pin rather than misreported as 404.
- `/api/cache/sources` answers 409 with `"capability": "cache_inspection"`.
- The opaque-origin request answers 403.
- `/api/capabilities` reports `"active_content": false` and `"mutations": false`.

**Fail:** Another source’s slug or a home path in any body; `allow-scripts` on `/raw`; a
200 from `/api/cache/…` or from the opaque origin.

### 5.3 Browse the pin (M03)

Open `http://127.0.0.1:8471/view/` in a browser, with its developer tools open.

1. The navigation heading shows the branch, then a muted 12-character commit.
   Narrow the navigation column: the branch name truncates with an ellipsis and the
   commit stays visible.
   Hovering the heading shows the full commit, the file count, and the size, and the
   count and size equal `/api/rollup?depth=0` (a symlink counts as a file on a pin).
   The file header prefix is the full commit.
2. The tree lists this repository’s top-level entries with sizes; folders expand.
   The filter bar has no recency filter and no “Show ignored” control, and neither has
   the root folder’s Overview.
3. `README.md` renders as a document, and its image (`images/metabrowser-overview.jpg`)
   loads. A relative link to another document opens it inside the pin, at a `/view/g1-…`
   address.
4. A Markdown file’s Source tab, `package.json` (Tree), an image, and a binary file each
   open in their usual view.
5. An HTML file offers only its Source tab.
6. The Git tab lists history starting at the pinned commit.
   Selecting a commit shows its detail and a split or unified diff.
   Reloading that `/commit/…` address reopens the same commit.
7. Reload a `/view/g1-…` address, use back and forward, and open a copied link in a
   second tab: the same file and revision open each time.

**Pass:** Every step as described; no console errors; no request leaves `127.0.0.1`.

**Fail:** A blank heading, a different commit anywhere, a Preview tab on HTML, a broken
image, or a request to another host.

### 5.4 Reopen with the origin gone (M05)

Serve a throwaway copy, stop it, move the copy away, and serve the same URL again.

```shell
QA_ORIGIN="$(mktemp -d "${TMPDIR:-/tmp}/mb-qa-origin.XXXXXX")/origin.git"
git clone -q --bare "${REPO}" "${QA_ORIGIN}"
uv --config-file uv.toml run --frozen metab "file://${QA_ORIGIN}" --no-open --port 8472
# Ctrl-C, then:
mv "${QA_ORIGIN}" "${QA_ORIGIN}.moved"
uv --config-file uv.toml run --frozen metab "file://${QA_ORIGIN}" --no-open --port 8472
```

**Pass:** The second run prints the same `Revision:` line and serves the same tree,
history, and files; nothing reads the moved origin.
Stopping prints `Stopping Metabrowser.` and exits 130.

**Fail:** A refusal because the origin is missing; a different revision.

### 5.5 Hostile content beside a populated cache (M06)

```shell
HOSTILE="$(mktemp -d "${TMPDIR:-/tmp}/mb-qa-hostile.XXXXXX")"
git -C "${HOSTILE}" init -q -b topic
printf '<!doctype html><script>fetch("/api/cache/sources").then(r=>r.text()).then(t=>document.title=t)</script><p>hostile</p>\n' > "${HOSTILE}/page.html"
printf '# Hostile\n\n<script>document.title="pwned"</script>\n\n<img src=x onerror="document.title=1">\n' > "${HOSTILE}/README.md"
git -C "${HOSTILE}" add . && git -C "${HOSTILE}" -c user.name=QA -c user.email=qa@example.invalid commit -qm hostile
uv --config-file uv.toml run --frozen metab "file://${HOSTILE}" --no-open --port 8473
```

The home already holds this repository’s source from Phase 4, so the cache is populated.

**Pass:** `page.html` offers only Source.
`README.md` renders with its script and handler removed; the tab title never changes.
Opening `http://127.0.0.1:8473/raw?path=g1-cGFnZS5odG1s` directly shows the page text,
its script does not run (the console reports it blocked by the sandbox), and the title
stays unchanged.

**Fail:** Any script runs; a Preview tab; the cache listing reaches the page.

### 5.6 Refresh and switch the pin (no network)

Serve a throwaway origin you can push to, then change it while the page is open.

```shell
QA_WORK="$(mktemp -d "${TMPDIR:-/tmp}/mb-qa-work.XXXXXX")"
git clone -q "${REPO}" "${QA_WORK}/work"
git clone -q --bare "${QA_WORK}/work" "${QA_WORK}/origin.git"
uv --config-file uv.toml run --frozen metab "file://${QA_WORK}/origin.git" --no-open --port 8474
```

Open `http://127.0.0.1:8474/view/` and keep it open.

1. The foot of the navigation pane reads `Fetched just now`. Hovering it explains the
   fetch; clicking it shows `Refreshing…` and then `Fetched just now` again.

2. From a second terminal, commit and push to the origin:

   ```shell
   git -C "${QA_WORK}/work" commit -q --allow-empty -m "QA newer commit"
   git -C "${QA_WORK}/work" push -q "${QA_WORK}/origin.git" HEAD
   ```

   Click the fetched label.
   Within a few seconds the row offers `<branch> is now at <short commit>` with
   **Switch**; the page itself has not changed.

3. Before switching, open the same address in a second tab.
   Click **Switch** in the first.
   The page reloads, the heading shows the new short commit, and the Git tab lists
   `QA newer commit` first.
   In the second tab, open another file: the request is refused as `pin_changed` and the
   row offers **Reload** at once, instead of showing the new commit’s file under the old
   heading.

4. From the second terminal, check the routes and their guard:

   ```shell
   BASE=http://127.0.0.1:8474
   curl -s -D - -o /dev/null "$BASE/api/source/status" | grep -i etag
   curl -s -o /dev/null -w '%{http_code}\n' "$BASE/api/source/refresh"
   curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'Origin: https://attacker.example' \
     -H 'Content-Type: application/json' -d '{}' "$BASE/api/source/refresh"
   curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'Content-Type: text/plain' \
     -d '{}' "$BASE/api/source/refresh"
   curl -s -X POST -H 'Content-Type: application/json' -d '{"ref": ":/QA"}' \
     "$BASE/api/source/pin"; echo
   curl -s -X POST -H 'Content-Type: application/json' -d '{"oid": "HEAD~1"}' \
     "$BASE/api/source/pin"; echo
   ```

   **Pass:** an `etag` header; `405` for the GET, `403` for the foreign origin, `415`
   for the form content type; both pin requests answer `invalid_selection` and nothing
   changes in the page.

5. Force-push the branch back one commit, then refresh from the page:

   ```shell
   git -C "${QA_WORK}/work" push -q --force "${QA_WORK}/origin.git" HEAD~1:"$(git -C "${QA_WORK}/work" branch --show-current)"
   ```

   The row offers the branch’s commit again, now the older one, because the branch moved
   back; the page you are reading still serves the commit you switched to.
   `curl -s -X POST -H 'Content-Type: application/json' -d '{"ref": "<that branch>"}' "$BASE/api/source/pin"`
   serves the force-pushed tip, and pinning the commit it replaced by ID still works.

6. Move the origin away (`mv "${QA_WORK}/origin.git" "${QA_WORK}/origin.moved"`) and
   click the fetched label.
   The row reads `Refresh failed · fetched …` as a warning; the tree, files, and history
   keep serving.

7. Restart the server after more than a minute with the origin back in place.
   The banner’s `Revision:` is the default branch as last fetched, and the row shows the
   startup refresh without the page waiting for it.

**Pass:** every step as described; the page never changes without **Switch** or a
reload; no console errors; no request leaves `127.0.0.1`.

**Fail:** the page moves to a newer commit on its own; a refresh blocks a page load; a
cross-origin or form POST is accepted; a failed refresh breaks the page; a force-pushed
commit becomes unreadable.

### 5.7 The pull-request page (stand-in, no network)

Build the stand-in of `tests/github_pull_fixture.py` (a `file://` origin standing in for
`https://github.com/octo/demo`, a fake `gh` replaying scrubbed real responses, and a
home holding pull requests 7 to 10), then serve pull request 7 from it:

```shell
QA_PR="$(mktemp -d "${TMPDIR:-/tmp}/mb-qa-pr.XXXXXX")"
uv --config-file uv.toml run --frozen python tests/github_pull_fixture.py "${QA_PR}"
uv --config-file uv.toml run --frozen python tests/github_pull_fixture.py "${QA_PR}" \
  --serve 7 8475
```

The banner prints
`Serving https://github.com/octo/demo at http://127.0.0.1:8475/pull/7`. Open that
address.

1. The page shows **Count to two in the app #7** with an **Open** badge,
   `forker wants to merge into topic from forker:count-to-two`, the opened and updated
   times, **View on GitHub**, **Browse code**, and the `enhancement` label.
   The status line reads `Fetched … by gh:octo-reader`; the records were fetched on
   2026-09-17, so it first adds `may be out of date` and offers **Refresh**, and the
   freshness row at the foot of the navigation pane refreshes on its own and links
   **Pull request #7**.
2. The description shows as plain text at first, then after a moment as Markdown
   (**two** in bold). The conversation lists, in time order, maintainer’s **reviewed**
   review, the comment `Thanks. CI is green; one question inline.`, and the **approved**
   review `Looks right.`
3. **Review comments (2)** shows `src/app.txt` with an **outdated** badge and its diff
   hunk, then forker’s reply on `src/app.txt:2`. **Checks** reads
   `2 success · 1 pending`, with `tests (3.13)`, `docs` (in progress), and the Read the
   Docs status, each linking out in a new tab, and `No conflicts with the base branch`.
4. Click **Files changed**. The address becomes `/pull/7/files` and the diff shows two
   files, `docs/new.md` and `src/app.txt`, and not `README.md`, which changed only on
   `topic`. Reload: the page opens on Files changed.
   Back: the conversation.
5. Click `src/app.txt:2`. The file opens at `/view/g1-c3Jj/g1-YXBwLnR4dA#L2` from the
   served head, `one` and `two`. Back returns to the pull-request page.
6. Click **Refresh** while the record is stale.
   The status line reads `Refreshing…` and then `Fetched just now by gh:octo-reader`;
   the conversation does not flicker or jump.
7. Open `/pull/8`. The page says `This server serves pull request #7.` When the pin is
   not the head the record names, as when the pull request could not be opened at
   startup and serving fell back to the default branch, the status line says
   `This page's code is …, not the pull request's head …` with **Switch to the head**,
   which reloads the page on `refs/pull/7/head`. The stand-in opens the pull request at
   startup, so this case is played by
   `tests/golden/cli-ui-github-pull-page.tryscript.md` rather than by hand.
8. Stop the server and serve pull request 9 (`--serve 9 8475`): **spam** is **Closed**,
   from `spam (deleted fork)` into `topic`, with no conversation, and Files changed
   compares from the recorded `base.sha`.
9. A hostile comment. Stop the server, add `HOSTILE_COMMENT` from
   `tests/github_pull_fixture.py` to pull request 7’s comments in
   `"${QA_PR}/fake-gh-scenario.json"` (rebuild that entry with the fixture’s `ok()`, so
   its entity tag changes), and serve 7 again with the browser’s network panel open.
   Once the freshness row’s refresh brings it, scroll to the comment.
   It shows as plain paragraphs, links, and text only: **build badge** is a link to the
   image, `x` a link, and `video`, `copy`, `fake dialog`, and `styled` plain text; no
   dialog covers the page; and the network panel shows no request to any origin but
   `127.0.0.1`, no `/kpress-static/` script, and no iframe.

**Pass:** every step as described; no console errors; no request leaves `127.0.0.1`
except the check and status links you click, which open in a new tab.

**Fail:** a text of the pull request rendered as HTML other than through the Markdown
renderer; an image, stylesheet, or other resource from a comment loading, or an `id`
from one in the page; a link that opens in the same tab or keeps an opener; a
`javascript:` link; a diff that moves to a newer head on its own; a blank page on a
reload or back.

With the network, a signed-in `gh`, and a Git the floor admits (read-only), open a real
public pull request, for example `pallets/markupsafe#507`, and repeat steps 1 to 6:

```shell
uv --config-file uv.toml run --frozen metab https://github.com/pallets/markupsafe/pull/507
```

**Pass:** the page matches the pull request on github.com: title, **Merged** badge,
description, conversation, review comments, checks, and the Files changed file list.
Nothing is written to GitHub.

### 5.8 A hostile README on a mirror (no network)

Serve a `file://` origin whose README carries every payload of the hostile corpus,
`tests/fixtures/untrusted-markdown`, with the browser’s network panel open:

```shell
QA_README="$(mktemp -d "${TMPDIR:-/tmp}/mb-qa-readme.XXXXXX")"
cp -R tests/fixtures/untrusted-markdown "${QA_README}/work"
git -C "${QA_README}/work" init -q -b main
git -C "${QA_README}/work" add -A
git -C "${QA_README}/work" -c user.name=QA -c user.email=qa@example.invalid commit -q -m qa
git clone -q --bare "${QA_README}/work" "${QA_README}/origin.git"
uv --config-file uv.toml run --frozen metab "file://${QA_README}/origin.git" --no-open --port 8479
```

1. Open `http://127.0.0.1:8479/view/`. The folder Overview’s README shows **Hostile
   readme** as plain paragraphs, links, and text: **build badge** and **tracker** are
   links to their images, `video`, `copy`, `fake dialog`, and `styled` are plain text,
   and the repository image `docs/diagram.png` shows.
2. The network panel shows no request to any origin but `127.0.0.1`, no
   `/kpress-static/` script (its stylesheets and fonts load), and no iframe; no dialog
   covers the page.
3. The page’s response carries `Content-Security-Policy` with
   `script-src 'self' 'nonce-…'`. In the console,
   `document.body.append(Object.assign(document.createElement("img"), {src: "https://example.com/x.png"}))`
   is refused by `img-src`, and no other policy violation is reported.
4. Open `README.md` itself, then **Guide**: the relative link opens `docs/guide.md` at
   the pin.
5. In the console, the repository’s own files are not code:
   `document.head.append(Object.assign(document.createElement("script"), {src: "/raw?path=g1-ZG9jcw%2Fg1-Z3VpZGUubWQ"}))`
   (any browsed file) is refused by `script-src`, and `/raw` answers such a request 403.
   Wiki links and embeds in a mirrored document show as plain text.
6. Serve the same folder as a trusted local folder (`metab "${QA_README}/work"`): the
   README renders with KPress’s full styling, and the response carries no policy.

**Pass:** every step as described.

**Fail:** any request to another origin, a KPress script loaded for the mirror’s README,
an iframe, a dialog over the page, a policy violation from the application itself, or a
trusted folder that renders plainly.

### 5.9 Heading anchors and the table of contents on a mirror (no network)

A mirrored document gets github.com’s heading anchors and the page’s own table of
contents, since no KPress script runs under the untrusted profile.
Mirror a guide long enough to earn one, with a repeated heading and a raw heading
carrying an `id` of its own, and a file whose POSIX name holds a backslash:

```shell
QA_TOC="$(mktemp -d "${TMPDIR:-/tmp}/mb-qa-toc.XXXXXX")"
mkdir "${QA_TOC}/work"
{
  printf '# Guide\n\n[install](#install) [again](#usage-1) [odd](a%%5Cb.md)\n\n'
  for title in Install Usage Configuration Troubleshooting; do
    printf '## %s\n\n' "$title"
    for _ in $(seq 100); do printf 'Words about %s. ' "$title"; done
    printf '\n\n### Usage\n\nA nested section.\n\n'
  done
  printf '<h2 id="metabrowser">Raw heading</h2>\n'
} > "${QA_TOC}/work/GUIDE.md"
printf '# Odd name\n' > "${QA_TOC}/work/a\\b.md"
git -C "${QA_TOC}/work" init -q -b main
git -C "${QA_TOC}/work" add -A
git -C "${QA_TOC}/work" -c user.name=QA -c user.email=qa@example.invalid commit -q -m qa
git clone -q --bare "${QA_TOC}/work" "${QA_TOC}/origin.git"
uv --config-file uv.toml run --frozen metab "file://${QA_TOC}/origin.git" --no-open --port 8480
```

1. Open `GUIDE.md` at a width that shows the side rail.
   A **Contents** list sits beside the document: **Install**, **Usage**,
   **Configuration**, and **Troubleshooting**, each with a nested **Usage**, and no
   plain list of the same entries sits at the top of the document.
2. Scroll: the entry for the section at the top quarter of the pane is highlighted.
   Click **Troubleshooting**: the document scrolls to it and the address ends
   `#user-content-troubleshooting`.
3. In the console, `document.querySelectorAll("h1[id], h2[id], h3[id]")` lists only
   `user-content-` ids, the repeated heading as `user-content-usage-1`, and
   `document.getElementById("metabrowser")` is `null`.
4. Click **install** and **again** in the first paragraph: each scrolls to its heading.
   Replace the address’s fragment with `#install` and reload: the page scrolls to
   **Install**, as github.com does.
5. Narrow the window until the rail folds away and scroll down: the toggle appears; it
   opens the drawer, and an entry or the backdrop closes it.
6. Serve the working folder as a trusted folder (`metab "${QA_TOC}/work"`): **odd**
   opens `a\b.md` (this needs PR #237’s `%5C` inventory names).
   In the mirror, and in the folder served with `--untrusted`, **odd** is text with no
   address: the inert allowlist drops an escaped backslash.

**Pass:** every step as described.

**Fail:** a flat list of entries in the document, an `id` the document wrote, an entry
or link that does not scroll, or a KPress script loaded for the mirror.

## Phase 6: HTML Trust on the Integration Tip

The selected integration tip must include the merged HTML trust implementation:

```shell
git merge-base --is-ancestor fd65812ba911e7fa0f6b5967d9240556c8c01c54 HEAD
```

Keep running from that tip so these checks exercise the actual combined build.

### 6.1 Automated HTML tests

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

### 6.2 Manual filesystem HTML (not acquired Git)

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

### 6.3 Optional: local filesystem serve for `/raw` headers

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

## Phase 7: What This Runbook Cannot Test

These are documented product gaps or environment limits.
Do **not** file beads for them unless the run shows **wrong** behavior (for example, ssh
was acquired or served, or a served pin ran a script).

| Item | Why it is out of scope here |
| --- | --- |
| ssh acquire and serve | Closed; refuse is the test |
| A branch and tag selector in the browser | Not built; pin by name through `POST /api/source/pin` (5.6) |
| The browser’s view of a pending URL selection | A page opened while the selection waited goes to it when the fetch finds it; the freshness row says when it is not on the origin or could not be fetched, and offers a Retry for the second |
| Line highlighting for `#L10-L20` | `mb-rlf3`; the anchor stays in the address |
| Pull-request page | Later steps; pull-request data is read through `--api` and served beside the pin (4.10) |
| Hosted-review / GitHub PR slice | Separate beads; not on these tips |
| Archive containers | `mb-380k` |
| Real browser HTML preview | Needs a browser; Phase 6.3 is optional and header-level. A pin never offers preview |
| Below-floor acquire success | Forbidden; ubuntu 2.43.0 must refuse |
| Overlay / `watch_backends` host differences | Investigate separately; record any unresolved failure |
| Landing / merging the v0.12 stack | `mb-n2ro`; this runbook does not merge |

## Hunt List (File a Bead Only for a Real Defect)

While executing, treat these as bugs if they happen:

- Wrong refuse string (transport or mode mismatch)
- HTTP 500 or a traceback instead of `CLIError`
- Missing `--api` `subject` on a pin (`git_revision` expected)
- `Serving` or a bound port on `--no-serve` / `--show` / `--api` / `--check-api`
- A served pin whose heading is blank, whose `/api/cache/…` answers 200, whose `/raw`
  lacks the sandbox or carries `allow-scripts`, or whose pages request another host
- A refresh that moves the page without **Switch**, blocks a request, or leaves a ref
  half-updated; a commit a reader pinned that becomes unreadable after a refresh
- Application home created on a refuse (ssh, a refused GitHub URL, walk,
  `--allow-edits`, below-floor Git)
- A GitHub token offered to a host other than github.com, or a token or query string
  echoed in an error
- An orphaned Git process after Ctrl-C, a terminal hangup, or `SIGTERM`
- Filesystem `--show` failing on this repository’s real paths
- Pin `--show` / `--api` failing on those same paths when Git meets the floor
- Cache inspect exposing origin objects through `/api/tree` on a cache route

Honest parents: `mb-k7zy` (epic), `mb-z335` (Git-tree source / pin), `mb-3bna` (source
session), `mb-h51g` (acquisition), `mb-cun0` (HTML `/raw` sandbox), `mb-doao` (serving a
pin), `mb-99ub` (forced untrusted profile), `mb-g5je` (served `/raw` references).
Do not start `mb-380k` or `mb-oueh` (unless the defect is exactly that bead), or reopen
the completed HTML publication bead `mb-d658`. Do not close unfinished product beads
from a QA run.

Record pass/fail in the pull request or the QA bead.
Do not rewrite this procedure into a changelog of one host’s run.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
