---
sandbox: true
path:
  - ../fixtures/github-status
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
patterns:
  FAKE_GH: '[^\s"]+/fixtures/github-status/gh'
before: >-
  mkdir statusroot &&
  printf '{}\n' > empty.json &&
  printf '{"fresh": true}\n' > fresh.json &&
  printf '{"fresh": "yes"}\n' > bad.json
---
# Golden tests: the GitHub status check

One check reports what GitHub work needs from GitHub CLI: where `gh` is, its version,
the account it is signed in to, that account’s token scopes, and one state with the step
that fixes it. `metab --doctor` prints it after the plugin verdict, and
`POST /api/plugin/github/status` serves the same report.
The state table is in the GitHub plugin’s `gh_status.py`.

`gh` here is `tests/fixtures/github-status/gh`, which answers `gh --version` and
`gh auth status --json hosts` as `FAKE_GH_STATUS` names and fails anything else, so no
command reaches a `gh` anyone has signed in.
Its account, `octo-reader`, is a fake.

## Test: the route reports a signed-in account with every scope

```console
$ metab statusroot --api /api/plugin/github/status --data empty.json
api: /api/plugin/github/status
status: 200
{
  "host": "github.com",
  "state": "ok",
  "message": "GitHub CLI is signed in to github.com as octo-reader.",
  "fix": null,
  "gh_path": "[FAKE_GH]",
  "gh_version": "2.98.0",
  "account": "octo-reader",
  "token_source": "keyring",
  "scopes": [
    "gist",
    "read:org",
    "repo",
    "workflow"
  ]
}
? 0
```

## Test: `fresh` asks gh again rather than reuse a recent answer

A server keeps an answer for a few seconds; after the reader signs in, `{"fresh": true}`
is how a Retry sees the change at once.

```console
$ metab statusroot --api /api/plugin/github/status --data fresh.json
api: /api/plugin/github/status
status: 200
{
  "host": "github.com",
  "state": "ok",
  "message": "GitHub CLI is signed in to github.com as octo-reader.",
  "fix": null,
  "gh_path": "[FAKE_GH]",
  "gh_version": "2.98.0",
  "account": "octo-reader",
  "token_source": "keyring",
  "scopes": [
    "gist",
    "read:org",
    "repo",
    "workflow"
  ]
}
? 0
```

## Test: a token without the repo scope reads public repositories only

```console
$ FAKE_GH_STATUS=no-repo-scope metab statusroot --api /api/plugin/github/status --data empty.json
api: /api/plugin/github/status
status: 200
{
  "host": "github.com",
  "state": "missing_scope",
  "message": "GitHub CLI is signed in to github.com as octo-reader, but its token lacks the repo scope, so it reads public repositories only. To read private ones: gh auth refresh --hostname github.com --scopes repo.",
  "fix": "gh auth refresh --hostname github.com --scopes repo",
  "gh_path": "[FAKE_GH]",
  "gh_version": "2.98.0",
  "account": "octo-reader",
  "token_source": "keyring",
  "scopes": [
    "gist",
    "read:org"
  ]
}
? 0
```

## Test: a token from the environment reports no scopes, and that is not a problem

gh does not list the scopes of a token it was handed in `GH_TOKEN`, so `scopes` is null
rather than empty.

```console
$ FAKE_GH_STATUS=env-token metab statusroot --api /api/plugin/github/status --data empty.json
api: /api/plugin/github/status
status: 200
{
  "host": "github.com",
  "state": "ok",
  "message": "GitHub CLI is signed in to github.com as octo-reader.",
  "fix": null,
  "gh_path": "[FAKE_GH]",
  "gh_version": "2.98.0",
  "account": "octo-reader",
  "token_source": "GH_TOKEN",
  "scopes": null
}
? 0
```

## Test: not signed in

```console
$ FAKE_GH_STATUS=signed-out metab statusroot --api /api/plugin/github/status --data empty.json
api: /api/plugin/github/status
status: 200
{
  "host": "github.com",
  "state": "not_logged_in",
  "message": "GitHub CLI is not signed in to github.com. Run gh auth login --hostname github.com, then retry.",
  "fix": "gh auth login --hostname github.com",
  "gh_path": "[FAKE_GH]",
  "gh_version": "2.98.0",
  "account": null,
  "token_source": null,
  "scopes": null
}
? 0
```

## Test: a token GitHub refuses is not signed in either

```console
$ FAKE_GH_STATUS=token-refused metab statusroot --api /api/plugin/github/status --data empty.json
api: /api/plugin/github/status
status: 200
{
  "host": "github.com",
  "state": "not_logged_in",
  "message": "GitHub refused gh's token for octo-reader. To sign in again: gh auth login --hostname github.com.",
  "fix": "gh auth login --hostname github.com",
  "gh_path": "[FAKE_GH]",
  "gh_version": "2.98.0",
  "account": "octo-reader",
  "token_source": "keyring",
  "scopes": null
}
? 0
```

## Test: a network failure is its own state, with no fix to run

```console
$ FAKE_GH_STATUS=offline metab statusroot --api /api/plugin/github/status --data empty.json
api: /api/plugin/github/status
status: 200
{
  "host": "github.com",
  "state": "network_error",
  "message": "gh is signed in as octo-reader but could not check its token: gh could not reach api.github.com.",
  "fix": null,
  "gh_path": "[FAKE_GH]",
  "gh_version": "2.98.0",
  "account": "octo-reader",
  "token_source": "keyring",
  "scopes": null
}
? 0
```

## Test: a gh too old to report its account as JSON

```console
$ FAKE_GH_STATUS=too-old metab statusroot --api /api/plugin/github/status --data empty.json
api: /api/plugin/github/status
status: 200
{
  "host": "github.com",
  "state": "gh_too_old",
  "message": "This GitHub CLI cannot report the active account. Update gh from https://cli.github.com/, then run gh auth status --hostname github.com.",
  "fix": "https://cli.github.com/",
  "gh_path": "[FAKE_GH]",
  "gh_version": "2.20.2",
  "account": null,
  "token_source": null,
  "scopes": null
}
? 0
```

## Test: a gh that fails without an answer

```console
$ FAKE_GH_STATUS=broken metab statusroot --api /api/plugin/github/status --data empty.json
api: /api/plugin/github/status
status: 200
{
  "host": "github.com",
  "state": "gh_failed",
  "message": "gh auth status did not report an account; run gh auth status --hostname github.com to see why.",
  "fix": "gh auth status --hostname github.com",
  "gh_path": "[FAKE_GH]",
  "gh_version": null,
  "account": null,
  "token_source": null,
  "scopes": null
}
? 0
```

## Test: a body that names anything but `fresh` is refused

```console
$ metab statusroot --api /api/plugin/github/status --data bad.json
api: /api/plugin/github/status
status: 400
{
  "error": "a status request names only fresh, true or false",
  "code": "invalid_request"
}
Error: /api/plugin/github/status returned HTTP 400
? 1
```

## Test: a GET runs no gh

The check runs `gh`, so the route takes only a POST.

```console
$ metab statusroot --api /api/plugin/github/status
api: /api/plugin/github/status
status: 405
Method Not Allowed
Error: /api/plugin/github/status returned HTTP 405
? 1
```

## Test: --doctor prints the same report after the plugin verdict

A GitHub state never changes the exit status: `--doctor` checks plugins, and a machine
with no `gh`, or one not signed in, has nothing wrong with its plugins.

```console
$ FAKE_GH_STATUS=signed-out metab --doctor 2>/dev/null
metab --doctor: 11 plugin(s) OK
github: not_logged_in: GitHub CLI is not signed in to github.com. Run gh auth login --hostname github.com, then retry.
  gh: [FAKE_GH] (version 2.98.0)
  fix: gh auth login --hostname github.com
? 0
```

```console
$ FAKE_GH_STATUS=too-old metab --doctor 2>/dev/null
metab --doctor: 11 plugin(s) OK
github: gh_too_old: This GitHub CLI cannot report the active account. Update gh from https://cli.github.com/, then run gh auth status --hostname github.com.
  gh: [FAKE_GH] (version 2.20.2)
  fix: https://cli.github.com/
? 0
```

```console
$ FAKE_GH_STATUS=offline metab --doctor --json 2>/dev/null
{
  "ok": true,
  "plugin_count": 11,
  "problems": [],
  "github": {
    "host": "github.com",
    "state": "network_error",
    "message": "gh is signed in as octo-reader but could not check its token: gh could not reach api.github.com.",
    "fix": null,
    "gh_path": "[FAKE_GH]",
    "gh_version": "2.98.0",
    "account": "octo-reader",
    "token_source": "keyring",
    "scopes": null
  }
}
? 0
```

## Test: --doctor with no gh on PATH

```console
$ PATH=/nonexistent "$(command -v metab)" --doctor 2>/dev/null
metab --doctor: 11 plugin(s) OK
github: gh_missing: Metabrowser could not find GitHub CLI (gh). Install it from https://cli.github.com/, then run gh auth login --hostname github.com.
  gh: not found on PATH
  fix: https://cli.github.com/
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
