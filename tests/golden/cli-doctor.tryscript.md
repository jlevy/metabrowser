---
sandbox: true
path:
  - ../fixtures/doctor
  - ../fixtures/github-status
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
  METABROWSER_OPEN_IN: "browser"
  METABROWSER_CONFIG_DIR: "/tmp/metabrowser-doctor-golden-never-created/config"
  METABROWSER_CACHE_DIR: "/tmp/metabrowser-doctor-golden-never-created/cache"
  METABROWSER_STATE_DIR: "/tmp/metabrowser-doctor-golden-never-created/state"
  METABROWSER_EVENT_LOG: "1"
  METABROWSER_CACHE_RESERVE_MB: "0"
  SOFTSCHEMA_PURE_YAML: "1"
patterns:
  FAKE_GH: '[^\s"]+/fixtures/github-status/gh'
  FAKE_GIT: '[^\s"]+/fixtures/doctor/git'
  METAB_VERSION: '[0-9]+\.[0-9]+\.[0-9]+[0-9A-Za-z.+]*'
  EXECUTABLE: '[^\s"]+/bin/metab'
  PYTHON: '[0-9]+\.[0-9]+\.[0-9]+[0-9A-Za-z.+]* at [^\s"]+'
  INSTALL_LOCATION: '(?:from the source checkout|in the Python environment) [^\s"]+'
  SANDBOX: '[^\s"]+/tryscript-[A-Za-z0-9]+'
  FREE: '(?:[0-9]+\.[0-9] GB|[0-9]+ MB|under 1 MB)'
before: >-
  mkdir -m 700 config cache badconfig &&
  mkdir -m 755 shared &&
  printf 'not: [yaml\n' > badconfig/config.yml &&
  chmod 600 badconfig/config.yml
---
# Golden tests: the setup checks of `metab --doctor`

After the plugin verdict, where `--present` opens a target, and GitHub CLI’s sign-in,
`metab --doctor` checks the setup: this `metab`, the `git` on `PATH`, and the
configuration and cache directories, and the event log.
`--doctor --json` serves all of them, the plugins and `open_in` first, as `checks`,
which the macOS app’s Help > Check Setup… decodes into one row each;
`src/metabrowser/cli/doctor.py` documents the shape and each check.

`git` here is `tests/fixtures/doctor/git`, which names the version `FAKE_GIT_VERSION`
chooses, and `gh` is `tests/fixtures/github-status/gh`, so neither the host’s Git nor a
signed-in `gh` decides the answer.
The frontmatter names configuration, cache, and state directories that do not exist and
that metab can create, as on a Mac where `metab` has not run yet; the doctor creates
neither. The other commands name theirs in the sandbox, or under `/nonexistent`, which
this user cannot create.
`METABROWSER_OPEN_IN=browser` looks for no app, so the `metab` check has no app’s
minimum to compare; `tests/test_doctor.py` covers that comparison.
`METABROWSER_EVENT_LOG` is set on, as the Makefile’s goldens otherwise turn it off.
The patterns elide what the host decides: the `metab` version and executable, the
Python, the install location, and the free space.
A source checkout may keep its Python virtual environment on an external scratch volume.
`METABROWSER_CACHE_RESERVE_MB` is 0, so the cache check never warns of low free space;
`tests/test_doctor.py` covers that warning.

## Test: a clean setup, as text

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/cache metab --doctor 2>/dev/null
metab --doctor: open_in browser (environment); --present looks for no app
metab --doctor: 17 plugin(s) OK
plugin requirements:
  agents: requires structured
  delimited: requires table
  diff: requires structured, pdf
  event-log: requires agents
  folder: requires markdown
  fsqlite: requires sqlite, table
  github: requires markdown, diff
  markdown: requires pdf
  sqlite: requires table
  structured: requires table
  unknown-jsonl: requires agents
github: ok: GitHub CLI is signed in to github.com as octo-reader.
  gh: [FAKE_GH] (version 2.98.0; needs 2.81.0 or later)
  account: octo-reader (token from keyring)
  scopes: gist, read:org, repo, workflow
metab: ok: metab [METAB_VERSION]
  version: [METAB_VERSION]
  executable: [EXECUTABLE]
  python: [PYTHON]
  SoftSchema YAML parser: pure
  installed: [INSTALL_LOCATION]
  app: not looked for
git: ok: git version 2.56.1, which meets every floor
  executable: [FAKE_GIT]
  version: git version 2.56.1
  file ages: available
config: ok: the configuration directory is private
  directory: [SANDBOX]/config
  source: METABROWSER_CONFIG_DIR
  config.yml: none
cache: ok: the cache directory is private and writable
  directory: [SANDBOX]/cache
  source: METABROWSER_CACHE_DIR
  free space: [FREE]
event_log: ok: no event log is written yet; the first server creates its directory
  directory: /tmp/metabrowser-doctor-golden-never-created/state/events
  source: METABROWSER_STATE_DIR
  not recorded: a server whose folder is the events directory or inside it writes no log, so that browsing the log does not change it; every other server writes one
? 0
```

## Test: the JSON report, before metab has created either directory

This is the report the app’s Check Setup… reads.

```console
$ metab --doctor --json
{
  "ok": true,
  "plugin_count": 17,
  "problems": [],
  "open_in": {
    "value": "browser",
    "source": "environment",
    "present_browser": true,
    "app": null
  },
  "github": {
    "host": "github.com",
    "state": "ok",
    "message": "GitHub CLI is signed in to github.com as octo-reader.",
    "fix": null,
    "remedy": null,
    "gh_path": "[FAKE_GH]",
    "gh_version": "2.98.0",
    "gh_minimum": "2.81.0",
    "account": "octo-reader",
    "token_source": "keyring",
    "scopes": [
      "gist",
      "read:org",
      "repo",
      "workflow"
    ]
  },
  "checks": [
    {
      "id": "plugins",
      "title": "Plugins",
      "state": "ok",
      "summary": "17 plugins and the packaged cache record contracts check out",
      "details": [
        {
          "name": "plugins",
          "value": "17"
        }
      ],
      "remedy": null
    },
    {
      "id": "open_in",
      "title": "Opening from a terminal",
      "state": "ok",
      "summary": "open_in browser (environment); --present looks for no app",
      "details": [
        {
          "name": "open_in",
          "value": "browser (environment)"
        },
        {
          "name": "present_browser",
          "value": "true"
        },
        {
          "name": "app",
          "value": "not looked for"
        }
      ],
      "remedy": null
    },
    {
      "id": "metab",
      "title": "metab",
      "state": "ok",
      "summary": "metab [METAB_VERSION]",
      "details": [
        {
          "name": "version",
          "value": "[METAB_VERSION]"
        },
        {
          "name": "executable",
          "value": "[EXECUTABLE]"
        },
        {
          "name": "python",
          "value": "[PYTHON]"
        },
        {
          "name": "SoftSchema YAML parser",
          "value": "pure"
        },
        {
          "name": "installed",
          "value": "[INSTALL_LOCATION]"
        },
        {
          "name": "app",
          "value": "not looked for"
        }
      ],
      "remedy": null
    },
    {
      "id": "git",
      "title": "Git",
      "state": "ok",
      "summary": "git version 2.56.1, which meets every floor",
      "details": [
        {
          "name": "executable",
          "value": "[FAKE_GIT]"
        },
        {
          "name": "version",
          "value": "git version 2.56.1"
        },
        {
          "name": "file ages",
          "value": "available"
        }
      ],
      "remedy": null
    },
    {
      "id": "config",
      "title": "Configuration",
      "state": "ok",
      "summary": "the configuration directory is not created yet; metab creates it when it first saves a setting",
      "details": [
        {
          "name": "directory",
          "value": "/tmp/metabrowser-doctor-golden-never-created/config"
        },
        {
          "name": "source",
          "value": "METABROWSER_CONFIG_DIR"
        },
        {
          "name": "config.yml",
          "value": "none"
        }
      ],
      "remedy": null
    },
    {
      "id": "cache",
      "title": "Cache",
      "state": "ok",
      "summary": "the cache directory is not created yet; metab creates it on first use",
      "details": [
        {
          "name": "directory",
          "value": "/tmp/metabrowser-doctor-golden-never-created/cache"
        },
        {
          "name": "source",
          "value": "METABROWSER_CACHE_DIR"
        },
        {
          "name": "free space",
          "value": "[FREE]"
        }
      ],
      "remedy": null
    },
    {
      "id": "event_log",
      "title": "Event log",
      "state": "ok",
      "summary": "no event log is written yet; the first server creates its directory",
      "details": [
        {
          "name": "directory",
          "value": "/tmp/metabrowser-doctor-golden-never-created/state/events"
        },
        {
          "name": "source",
          "value": "METABROWSER_STATE_DIR"
        },
        {
          "name": "not recorded",
          "value": "a server whose folder is the events directory or inside it writes no log, so that browsing the log does not change it; every other server writes one"
        }
      ],
      "remedy": null
    }
  ]
}
? 0
```

## Test: a directory metab cannot create is a problem

```console
$ METABROWSER_CONFIG_DIR=/nonexistent/metabrowser-doctor-golden/config METABROWSER_CACHE_DIR=/nonexistent/metabrowser-doctor-golden/cache metab --doctor 2>&1 >/dev/null
metab --doctor: 2 problem(s):
  • config: the configuration directory does not exist, and metab cannot create it: / is not writable by this user
  • cache: the cache directory does not exist, and metab cannot create it: / is not writable by this user
plugin requirements:
  agents: requires structured
  delimited: requires table
  diff: requires structured, pdf
  event-log: requires agents
  folder: requires markdown
  fsqlite: requires sqlite, table
  github: requires markdown, diff
  markdown: requires pdf
  sqlite: requires table
  structured: requires table
  unknown-jsonl: requires agents
github: ok: GitHub CLI is signed in to github.com as octo-reader.
  gh: [FAKE_GH] (version 2.98.0; needs 2.81.0 or later)
  account: octo-reader (token from keyring)
  scopes: gist, read:org, repo, workflow
metab: ok: metab [METAB_VERSION]
  version: [METAB_VERSION]
  executable: [EXECUTABLE]
  python: [PYTHON]
  SoftSchema YAML parser: pure
  installed: [INSTALL_LOCATION]
  app: not looked for
git: ok: git version 2.56.1, which meets every floor
  executable: [FAKE_GIT]
  version: git version 2.56.1
  file ages: available
config: problem: the configuration directory does not exist, and metab cannot create it: / is not writable by this user
  directory: /nonexistent/metabrowser-doctor-golden/config
  source: METABROWSER_CONFIG_DIR
  config.yml: none
  fix: Create it with mode 700 yourself, or set METABROWSER_CONFIG_DIR to a private directory you own.
cache: problem: the cache directory does not exist, and metab cannot create it: / is not writable by this user
  directory: /nonexistent/metabrowser-doctor-golden/cache
  source: METABROWSER_CACHE_DIR
  free space: [FREE]
  fix: Create it with mode 700 yourself, or set METABROWSER_CACHE_DIR to a private directory you own.
event_log: ok: no event log is written yet; the first server creates its directory
  directory: /tmp/metabrowser-doctor-golden-never-created/state/events
  source: METABROWSER_STATE_DIR
  not recorded: a server whose folder is the events directory or inside it writes no log, so that browsing the log does not change it; every other server writes one
? 1
```

## Test: a Git below the floor for cloning is a warning with its remedy

A warning never changes the exit status: a folder is served without cloning anything.

```console
$ FAKE_GIT_VERSION=apple-old METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/cache metab --doctor > doctor.txt 2>/dev/null; echo "exit: $?"; grep -A4 '^git:' doctor.txt
exit: 0
git: warning: git version 2.39.5 (Apple Git-154) is below the floor for cloning, 2.43.7 or a patched release at least 2.50.1 on a newer track, so metab clones no Git source and shows no branch or tag of a checkout
  executable: [FAKE_GIT]
  version: git version 2.39.5 (Apple Git-154)
  file ages: needs Git 2.53 or newer, so a Git revision shows no By age
  fix: Update Git with the package manager that installed it, or from Git's downloads. https://git-scm.com/downloads
? 0
```

## Test: a Git below a partial clone’s release

```console
$ FAKE_GIT_VERSION=before-partial-clone METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/cache metab --doctor > doctor.txt 2>/dev/null; echo "exit: $?"; grep -A4 '^git:' doctor.txt
exit: 0
git: warning: git version 2.44.4 shows no branch or tag of a partial clone, which needs 2.45.4 or a patched release at least 2.50.1 on a newer track
  executable: [FAKE_GIT]
  version: git version 2.44.4
  file ages: needs Git 2.53 or newer, so a Git revision shows no By age
  fix: Update Git with the package manager that installed it, or from Git's downloads. https://git-scm.com/downloads
? 0
```

## Test: a Git that clones but reads no file ages is a warning with its remedy

`git last-modified`, which dates the files of a Git revision, is Git 2.53’s, so a Git
that meets every floor for cloning still shows a revision no By age.
The report says so, and says which release it needs, and the exit status stays 0.

```console
$ FAKE_GIT_VERSION=before-file-ages METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/cache metab --doctor > doctor.txt 2>/dev/null; echo "exit: $?"; grep -A4 '^git:' doctor.txt
exit: 0
git: warning: File ages on Git revisions need Git 2.53 or newer (found 2.50.1)
  executable: [FAKE_GIT]
  version: git version 2.50.1
  file ages: needs Git 2.53 or newer, so a Git revision shows no By age
  fix: Update Git with the package manager that installed it, or from Git's downloads. https://git-scm.com/downloads
? 0
```

## Test: a Git that names no version

```console
$ FAKE_GIT_VERSION=unreadable METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/cache metab --doctor > doctor.txt 2>/dev/null; echo "exit: $?"; grep -A4 '^git:' doctor.txt
exit: 0
git: warning: git at [FAKE_GIT] did not name a version metab can read
  executable: [FAKE_GIT]
  version: a build of git that names no version
  file ages: needs Git 2.53 or newer, so a Git revision shows no By age
  fix: Update Git with the package manager that installed it, or from Git's downloads. https://git-scm.com/downloads
? 0
```

## Test: a gh older than the minimum is too old by its version

The stand-in signs in as a current gh does, so only its version, 2.80.0, says it is too
old.

```console
$ FAKE_GH_STATUS=old-version METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/cache metab --doctor > doctor.txt 2>/dev/null; echo "exit: $?"; grep -A2 '^github:' doctor.txt
exit: 0
github: gh_too_old: GitHub CLI 2.80.0 cannot report the signed-in account, so Metabrowser opens no pull request it has not cached; that needs gh 2.81.0 or later. To update it: https://cli.github.com/.
  gh: [FAKE_GH] (version 2.80.0; needs 2.81.0 or later)
  fix: https://cli.github.com/
? 0
```

## Test: a configuration directory other users can read is a problem

A problem is listed with the plugin problems, the report goes to stderr, and the exit
status is 1. `--present` reads `config.yml` from the same directory, and the `open_in`
check notes that it did not read it there, so the problem is listed once, at its cause.

```console
$ METABROWSER_CONFIG_DIR=$PWD/shared METABROWSER_CACHE_DIR=$PWD/cache metab --doctor 2>&1 >/dev/null
metab --doctor: 1 problem(s):
  • config: The Metabrowser storage directory is accessible to other users (mode 0755). Run chmod 700 on it, or set the applicable override (METABROWSER_CACHE_DIR or METABROWSER_CONFIG_DIR) to a private directory you own.
plugin requirements:
  agents: requires structured
  delimited: requires table
  diff: requires structured, pdf
  event-log: requires agents
  folder: requires markdown
  fsqlite: requires sqlite, table
  github: requires markdown, diff
  markdown: requires pdf
  sqlite: requires table
  structured: requires table
  unknown-jsonl: requires agents
github: ok: GitHub CLI is signed in to github.com as octo-reader.
  gh: [FAKE_GH] (version 2.98.0; needs 2.81.0 or later)
  account: octo-reader (token from keyring)
  scopes: gist, read:org, repo, workflow
metab: ok: metab [METAB_VERSION]
  version: [METAB_VERSION]
  executable: [EXECUTABLE]
  python: [PYTHON]
  SoftSchema YAML parser: pure
  installed: [INSTALL_LOCATION]
  app: not looked for
git: ok: git version 2.56.1, which meets every floor
  executable: [FAKE_GIT]
  version: git version 2.56.1
  file ages: available
config: problem: The Metabrowser storage directory is accessible to other users (mode 0755). Run chmod 700 on it, or set the applicable override (METABROWSER_CACHE_DIR or METABROWSER_CONFIG_DIR) to a private directory you own.
  directory: [SANDBOX]/shared
  source: METABROWSER_CONFIG_DIR
cache: ok: the cache directory is private and writable
  directory: [SANDBOX]/cache
  source: METABROWSER_CACHE_DIR
  free space: [FREE]
event_log: ok: no event log is written yet; the first server creates its directory
  directory: /tmp/metabrowser-doctor-golden-never-created/state/events
  source: METABROWSER_STATE_DIR
  not recorded: a server whose folder is the events directory or inside it writes no log, so that browsing the log does not change it; every other server writes one
? 1
```

## Test: a config.yml this release cannot read is a problem

```console
$ METABROWSER_CONFIG_DIR=$PWD/badconfig METABROWSER_CACHE_DIR=$PWD/cache metab --doctor 2>doctor.txt >/dev/null; echo "exit: $?"; grep -A5 '^config:' doctor.txt
exit: 1
config: problem: config.yml cannot be read: config.yml is not portable YAML
  directory: [SANDBOX]/badconfig
  source: METABROWSER_CONFIG_DIR
  config.yml: unreadable
  fix: Move [SANDBOX]/badconfig/config.yml aside; metab writes a fresh one.
cache: ok: the cache directory is private and writable
? 0
```

## Test: a cache override that is not an absolute path is a problem

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=relative metab --doctor --json 2>/dev/null
{
  "ok": false,
  "plugin_count": 17,
  "problems": [
    "cache: METABROWSER_CACHE_DIR must be a nonempty absolute path without '..' components."
  ],
  "open_in": {
    "value": "browser",
    "source": "environment",
    "present_browser": true,
    "app": null
  },
  "github": {
    "host": "github.com",
    "state": "ok",
    "message": "GitHub CLI is signed in to github.com as octo-reader.",
    "fix": null,
    "remedy": null,
    "gh_path": "[FAKE_GH]",
    "gh_version": "2.98.0",
    "gh_minimum": "2.81.0",
    "account": "octo-reader",
    "token_source": "keyring",
    "scopes": [
      "gist",
      "read:org",
      "repo",
      "workflow"
    ]
  },
  "checks": [
    {
      "id": "plugins",
      "title": "Plugins",
      "state": "ok",
      "summary": "17 plugins and the packaged cache record contracts check out",
      "details": [
        {
          "name": "plugins",
          "value": "17"
        }
      ],
      "remedy": null
    },
    {
      "id": "open_in",
      "title": "Opening from a terminal",
      "state": "ok",
      "summary": "open_in browser (environment); --present looks for no app",
      "details": [
        {
          "name": "open_in",
          "value": "browser (environment)"
        },
        {
          "name": "present_browser",
          "value": "true"
        },
        {
          "name": "app",
          "value": "not looked for"
        }
      ],
      "remedy": null
    },
    {
      "id": "metab",
      "title": "metab",
      "state": "ok",
      "summary": "metab [METAB_VERSION]",
      "details": [
        {
          "name": "version",
          "value": "[METAB_VERSION]"
        },
        {
          "name": "executable",
          "value": "[EXECUTABLE]"
        },
        {
          "name": "python",
          "value": "[PYTHON]"
        },
        {
          "name": "SoftSchema YAML parser",
          "value": "pure"
        },
        {
          "name": "installed",
          "value": "[INSTALL_LOCATION]"
        },
        {
          "name": "app",
          "value": "not looked for"
        }
      ],
      "remedy": null
    },
    {
      "id": "git",
      "title": "Git",
      "state": "ok",
      "summary": "git version 2.56.1, which meets every floor",
      "details": [
        {
          "name": "executable",
          "value": "[FAKE_GIT]"
        },
        {
          "name": "version",
          "value": "git version 2.56.1"
        },
        {
          "name": "file ages",
          "value": "available"
        }
      ],
      "remedy": null
    },
    {
      "id": "config",
      "title": "Configuration",
      "state": "ok",
      "summary": "the configuration directory is private",
      "details": [
        {
          "name": "directory",
          "value": "[SANDBOX]/config"
        },
        {
          "name": "source",
          "value": "METABROWSER_CONFIG_DIR"
        },
        {
          "name": "config.yml",
          "value": "none"
        }
      ],
      "remedy": null
    },
    {
      "id": "cache",
      "title": "Cache",
      "state": "problem",
      "summary": "METABROWSER_CACHE_DIR must be a nonempty absolute path without '..' components.",
      "details": [
        {
          "name": "source",
          "value": "METABROWSER_CACHE_DIR"
        }
      ],
      "remedy": null
    },
    {
      "id": "event_log",
      "title": "Event log",
      "state": "ok",
      "summary": "no event log is written yet; the first server creates its directory",
      "details": [
        {
          "name": "directory",
          "value": "/tmp/metabrowser-doctor-golden-never-created/state/events"
        },
        {
          "name": "source",
          "value": "METABROWSER_STATE_DIR"
        },
        {
          "name": "not recorded",
          "value": "a server whose folder is the events directory or inside it writes no log, so that browsing the log does not change it; every other server writes one"
        }
      ],
      "remedy": null
    }
  ]
}
? 1
```

## Test: an environment that turns the event log off is a warning

The owner’s aim is that latency is always captured, so a log that is off is said, with
the setting that turned it off and the step that undoes it.
It is a warning, not a problem: a folder is served without a log.

```console
$ METABROWSER_EVENT_LOG=0 METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/cache metab --doctor > doctor.txt 2>/dev/null; echo "exit: $?"; grep -A3 '^event_log:' doctor.txt
exit: 0
event_log: warning: METABROWSER_EVENT_LOG turns the event log off, so no latency or failure is recorded
  directory: /tmp/metabrowser-doctor-golden-never-created/state/events
  source: METABROWSER_STATE_DIR
  fix: Unset METABROWSER_EVENT_LOG, or set it to 1.
? 0
```

## Test: a state directory that cannot be created is a warning

```console
$ METABROWSER_STATE_DIR=/nonexistent/metabrowser-doctor-golden/state METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/cache metab --doctor > doctor.txt 2>/dev/null; echo "exit: $?"; grep -A4 '^event_log:' doctor.txt
exit: 0
event_log: warning: the event log's directory does not exist, and metab cannot create it: / is not writable by this user
  directory: /nonexistent/metabrowser-doctor-golden/state/events
  source: METABROWSER_STATE_DIR
  not recorded: a server whose folder is the events directory or inside it writes no log, so that browsing the log does not change it; every other server writes one
  fix: Create the state directory with mode 700 yourself, or set METABROWSER_STATE_DIR to a private directory you own.
? 0
```

## Test: the events directory a server has written counts its segments

```console
$ mkdir -m 700 state state/events && touch state/events/events-20260101T000000Z-p1-000.jsonl && METABROWSER_STATE_DIR=$PWD/state METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/cache metab --doctor > doctor.txt 2>/dev/null; echo "exit: $?"; grep -A4 '^event_log:' doctor.txt
exit: 0
event_log: ok: a server writes an event log here
  directory: [SANDBOX]/state/events
  source: METABROWSER_STATE_DIR
  not recorded: a server whose folder is the events directory or inside it writes no log, so that browsing the log does not change it; every other server writes one
  segments: 1
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
