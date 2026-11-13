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
  touch -t 202311142213.20 trustroot/README.md trustroot/page.html trustroot &&
  mkdir -p evilrepo &&
  printf '# Sample\n' > evilrepo/README.md &&
  printf 'METAB_ALLOW_EDITS=1\nMETAB_UNTRUSTED=1\nMETABROWSER_PLUGINS_DIRS=%s/evil-plugins\n'
  "$PWD" > evilrepo/.env &&
  printf 'METABROWSER_DEBUG=1\nBROWSER=%s/evil\nPATH=%s/evil\nGIT_TRACE=%s/trace.txt\n'
  "$PWD" "$PWD" "$PWD" >> evilrepo/.env &&
  printf 'METABROWSER_\033[31mRED\033[0m=1\n' >> evilrepo/.env &&
  printf "'METABROWSER_A\nFORGED: a line of its own'=1\n" >> evilrepo/.env &&
  printf 'METABROWSER_REQUEST_LOG=verbose\n' >> evilrepo/.env
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
A single view has no tab, so Source is served without its key `S`.

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

## Test: a browsed repository’s `.env` contributes only the allowlist

The dotenv chain walks up from the working directory, so `cd cloned-repo && metab .`
reaches that repository’s own `.env`, and the loader cannot tell it from a file the
operator wrote. So a dotenv file may set only the names in `ALLOWED_KEYS` in
`metabrowser/dotenv.py`. This `.env` sets one of them, shown landing at the end of this
section, and nothing else in it may land.

The warning names that allowlist in full, so adding a name to it changes this
transcript. The refused names are the repository’s own, and two of them are written to
act on the terminal: one holds escape sequences that would colour the line, and one,
quoted, holds a line break that would print a line of the file’s choosing.
The warning shows both as visible escapes on its one line.
Each capability variable below is cleared first, because a dotenv value never replaces
one the environment already holds, and the front matter holds them empty.
Had the file reached the environment, `METAB_ALLOW_EDITS` would read `mutations: true`
and `METAB_UNTRUSTED` would read `active_content: false`.

```console
$ cd evilrepo && env -u METAB_ALLOW_EDITS -u METAB_UNTRUSTED metab . --api /api/capabilities
[..]/evilrepo/.env: ignored METABROWSER_\x1b[31mRED\x1b[0m, METABROWSER_A\nFORGED: a line of its own, METABROWSER_DEBUG, METABROWSER_PLUGINS_DIRS, METAB_ALLOW_EDITS, METAB_UNTRUSTED — a dotenv file may only set METABROWSER_LOG_LEVEL, METABROWSER_REQUEST_LOG. Export the others in the environment instead; see SECURITY.md.
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
    "indexed_files": 1,
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
    "active_content": true,
    "mutations": false
  }
}
? 0
```

The same file sets `GIT_TRACE`, which makes Git write a trace to the path it names.
Asking whether the folder is a repository runs Git, so the trace would exist by now if
the name had reached it.
`PATH` and `BROWSER` are refused too, and silently, because only this package’s own
names are worth a warning: every repository has variables of its own.
A dotenv value never replaces a name the shell already exports, so `PATH` could not be
displaced through this loader in any case.

```console
$ cd evilrepo && metab . --api /api/git/repo
[..]/evilrepo/.env: ignored METABROWSER_\x1b[31mRED\x1b[0m, METABROWSER_A\nFORGED: a line of its own, METABROWSER_DEBUG, METABROWSER_PLUGINS_DIRS, METAB_ALLOW_EDITS, METAB_UNTRUSTED — a dotenv file may only set METABROWSER_LOG_LEVEL, METABROWSER_REQUEST_LOG. Export the others in the environment instead; see SECURITY.md.
api: /api/git/repo
status: 200
{
  "is_repo": false,
  "root": null,
  "head": null,
  "reason": "not_a_repo"
}
? 0
```

```console
$ test ! -e trace.txt
? 0
```

A loader that refused every name would pass everything above, so this is the admission:
the file sets `METABROWSER_REQUEST_LOG=verbose`, and each request then logs a line.
That line is at `INFO`, which the front matter’s `METABROWSER_LOG_LEVEL` hides from the
commands above, so this one clears the level, and clears the name for the reason the
capability variables were cleared.

```console
$ cd evilrepo && env -u METABROWSER_LOG_LEVEL -u METABROWSER_REQUEST_LOG metab . --api /api/git/repo
[..]/evilrepo/.env: ignored METABROWSER_\x1b[31mRED\x1b[0m, METABROWSER_A\nFORGED: a line of its own, METABROWSER_DEBUG, METABROWSER_PLUGINS_DIRS, METAB_ALLOW_EDITS, METAB_UNTRUSTED — a dotenv file may only set METABROWSER_LOG_LEVEL, METABROWSER_REQUEST_LOG. Export the others in the environment instead; see SECURITY.md.
[..] metabrowser.server | metabrowser request t=[..] -> [..] ([..] ms) method=GET path=/api/git/repo status=200 bytes=63 start_ms=[..] phases=git:[..]
api: /api/git/repo
status: 200
{
  "is_repo": false,
  "root": null,
  "head": null,
  "reason": "not_a_repo"
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
