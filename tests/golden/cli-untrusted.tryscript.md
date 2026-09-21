---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
  METAB_UNTRUSTED: ""
  METAB_ACTIVE_CONTENT: ""
  METAB_ALLOW_EDITS: ""
before: >-
  mkdir -p trustroot &&
  printf '# Sample\n\nHello.\n' > trustroot/README.md &&
  printf '<!doctype html>\n<title>Page</title>\n<p>Hello</p>\n' > trustroot/page.html &&
  touch -t 202311142213.20 trustroot/README.md trustroot/page.html trustroot
---
# Golden tests: the `--untrusted` content-trust profile

Every other transcript in this directory runs the default profile, where active content
is on. This one pins the conservative profile and the two individual flags, so a change
that silently stops one of them from reaching the capability block or the view list
shows up as a diff here rather than as a quiet loss of containment.

The three capability environment variables are cleared in the front matter.
The profile under test is the one the flag asks for, and pinning the environment keeps
the transcript from recording whatever the surrounding shell happened to export.

The default answers to both commands are in `cli-api-shell.tryscript.md` and
`cli-show.tryscript.md`; read them beside these.

The watcher values are host facts and startup transients, elided here for the reason
`cli-api-shell.tryscript.md` states.

## Test: the capability block under `--untrusted`

```console
$ metab trustroot --untrusted --api /api/capabilities
api: /api/capabilities
status: 200
{
  "backends": [
    {
      "prefix": ".",
      "mode": "[..]",
      "reason": "[..]",
      "state": "[..]"
    }
  ],
  "index": {
    "complete": true,
    "indexed_files": 2,
    "max_files": 500000,
    "truncated": false,
    "provider": "python",
    "contract": "inventory-provider-v1"
  },
  "events": {
    "stream": "live",
    "reason": "[..]"
  },
  "capabilities": {
    "active_content": false,
    "mutations": false
  }
}
? 0
```

## Test: HTML loses its Preview view under `--untrusted`

Preview is the surface that executes a browsed document, so the conservative profile
withdraws it and leaves Source as the only view, and therefore the default.

```console
$ metab trustroot --untrusted --show page.html
show: page.html
route: /view/page.html
kind: html
views: source (default)
model: text envelope; size=49 content_bytes=49 content_truncated=False
? 0
```

## Test: `--no-active-content` withdraws Preview on its own

The profile is not the only way to reach the conservative view list.
`--no-active-content` drops `allow-scripts` from the `/raw` sandbox, and a Preview whose
frame cannot run scripts would misrepresent the document, so the flag withdraws the view
the same way `--untrusted` does.
Pinning it separately keeps the two paths from drifting apart, which a test that only
ever passes the profile would not catch.

```console
$ metab trustroot --no-active-content --show page.html
show: page.html
route: /view/page.html
kind: html
views: source (default)
model: text envelope; size=49 content_bytes=49 content_truncated=False
? 0
```

## Test: `--untrusted --allow-edits` lifts mutations and nothing else

This is the one combination that overrides the profile, so it is the one that shows the
rule is a real precedence and not a blanket refusal.
`--allow-edits` publishes `mutations: true` from under `--untrusted`, while
`active_content` stays false because nothing asked for it.

```console
$ metab trustroot --untrusted --allow-edits --api /api/capabilities
api: /api/capabilities
status: 200
{
  "backends": [
    {
      "prefix": ".",
      "mode": "[..]",
      "reason": "[..]",
      "state": "[..]"
    }
  ],
  "index": {
    "complete": true,
    "indexed_files": 2,
    "max_files": 500000,
    "truncated": false,
    "provider": "python",
    "contract": "inventory-provider-v1"
  },
  "events": {
    "stream": "live",
    "reason": "[..]"
  },
  "capabilities": {
    "active_content": false,
    "mutations": true
  }
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
