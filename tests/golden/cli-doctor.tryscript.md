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
  METABROWSER_CONFIG_DIR: "/nonexistent/metabrowser-doctor-golden/config"
  METABROWSER_CACHE_DIR: "/nonexistent/metabrowser-doctor-golden/cache"
patterns:
  FAKE_GH: '[^\s"]+/fixtures/github-status/gh'
  FAKE_GIT: '[^\s"]+/fixtures/doctor/git'
  METAB_VERSION: '[0-9]+\.[0-9]+\.[0-9]+[0-9A-Za-z.+]*'
  EXECUTABLE: '[^\s"]+/bin/metab'
  PYTHON: '[0-9]+\.[0-9]+\.[0-9]+[0-9A-Za-z.+]* at [^\s"]+'
  ENVIRONMENT: '[^\s"]+'
  SANDBOX: '[^\s"]+/tryscript-[A-Za-z0-9]+'
  FREE: '[0-9]+\.[0-9] GB'
before: >-
  mkdir -m 700 config cache badconfig &&
  mkdir -m 755 shared &&
  printf 'not: [yaml\n' > badconfig/config.yml &&
  chmod 600 badconfig/config.yml
---
# Golden tests: the setup checks of `metab --doctor`

After the plugin verdict, where `--present` opens a target, and GitHub CLI’s sign-in,
`metab --doctor` checks the setup: this `metab`, the `git` on `PATH`, and the
configuration and cache directories.
`--doctor --json` serves them as `checks`, which the macOS app’s Help > Check Setup…
decodes; `src/metabrowser/cli/doctor.py` documents the shape and each check.

`git` here is `tests/fixtures/doctor/git`, which names the version `FAKE_GIT_VERSION`
chooses, and `gh` is `tests/fixtures/github-status/gh`, so neither the host’s Git nor a
signed-in `gh` decides the answer.
The frontmatter names configuration and cache directories that do not exist, as on a Mac
where `metab` has not run yet, and the other commands name theirs in the sandbox.
`METABROWSER_OPEN_IN=browser` looks for no app, so the `metab` check has no app’s
minimum to compare; `tests/test_doctor.py` covers that comparison.
The patterns elide what the host decides: the `metab` version and executable, the
Python, the environment it runs in, and the free space.

## Test: a clean setup, as text

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/cache metab --doctor 2>/dev/null
metab --doctor: open_in browser (environment); --present looks for no app
metab --doctor: 11 plugin(s) OK
github: ok: GitHub CLI is signed in to github.com as octo-reader.
  gh: [FAKE_GH] (version 2.98.0; needs 2.81.0 or later)
  account: octo-reader (token from keyring)
  scopes: gist, read:org, repo, workflow
metab: ok: metab [METAB_VERSION]
  version: [METAB_VERSION]
  executable: [EXECUTABLE]
  python: [PYTHON]
  installed: in the Python environment [ENVIRONMENT]
  app: not looked for
git: ok: git version 2.50.1, which meets every floor
  executable: [FAKE_GIT]
  version: git version 2.50.1
config: ok: the configuration directory is private
  directory: [SANDBOX]/config
  source: METABROWSER_CONFIG_DIR
  config.yml: none
cache: ok: the cache directory is private and writable
  directory: [SANDBOX]/cache
  source: METABROWSER_CACHE_DIR
  free space: [FREE]
? 0
```

## Test: the JSON report, before metab has created either directory

This is the report the app’s Check Setup… reads.

```console
$ metab --doctor --json
{
  "ok": true,
  "plugin_count": 11,
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
          "name": "installed",
          "value": "in the Python environment [ENVIRONMENT]"
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
      "summary": "git version 2.50.1, which meets every floor",
      "details": [
        {
          "name": "executable",
          "value": "[FAKE_GIT]"
        },
        {
          "name": "version",
          "value": "git version 2.50.1"
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
          "value": "/nonexistent/metabrowser-doctor-golden/config"
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
          "value": "/nonexistent/metabrowser-doctor-golden/cache"
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
    }
  ]
}
? 0
```

## Test: a Git below the floor for cloning is a warning with its remedy

A warning never changes the exit status: a folder is served without cloning anything.

```console
$ FAKE_GIT_VERSION=apple-old METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/cache metab --doctor > doctor.txt 2>/dev/null; echo "exit: $?"; grep -A3 '^git:' doctor.txt
exit: 0
git: warning: git version 2.39.5 (Apple Git-154) is below the floor for cloning, 2.43.7 or a patched release at least 2.50.1 on a newer track, so metab clones no Git source and shows no branch or tag of a checkout
  executable: [FAKE_GIT]
  version: git version 2.39.5 (Apple Git-154)
  fix: Update Git with the package manager that installed it, or from Git's downloads. https://git-scm.com/downloads
? 0
```

## Test: a Git below a partial clone’s release

```console
$ FAKE_GIT_VERSION=before-partial-clone METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/cache metab --doctor > doctor.txt 2>/dev/null; echo "exit: $?"; grep -A3 '^git:' doctor.txt
exit: 0
git: warning: git version 2.44.4 shows no branch or tag of a partial clone, which needs 2.45.4 or a patched release at least 2.50.1 on a newer track
  executable: [FAKE_GIT]
  version: git version 2.44.4
  fix: Update Git with the package manager that installed it, or from Git's downloads. https://git-scm.com/downloads
? 0
```

## Test: a Git that names no version

```console
$ FAKE_GIT_VERSION=unreadable METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/cache metab --doctor > doctor.txt 2>/dev/null; echo "exit: $?"; grep -A3 '^git:' doctor.txt
exit: 0
git: warning: git at [FAKE_GIT] did not name a version metab can read
  executable: [FAKE_GIT]
  version: a build of git that names no version
  fix: Update Git with the package manager that installed it, or from Git's downloads. https://git-scm.com/downloads
? 0
```

## Test: a gh older than the minimum is too old by its version

The stand-in signs in as a current gh does, so only its version, 2.80.0, says it is too
old.

```console
$ FAKE_GH_STATUS=old-version METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/cache metab --doctor > doctor.txt 2>/dev/null; echo "exit: $?"; grep -A2 '^github:' doctor.txt
exit: 0
github: gh_too_old: GitHub CLI 2.80.0 cannot report the signed-in account; Metabrowser needs gh 2.81.0 or later. To update it: https://cli.github.com/.
  gh: [FAKE_GH] (version 2.80.0; needs 2.81.0 or later)
  fix: https://cli.github.com/
? 0
```

## Test: a configuration directory other users can read is a problem

A problem is listed with the plugin problems, the report goes to stderr, and the exit
status is 1. `--present` reads `config.yml` from the same directory, so `open_in`
reports it too.

```console
$ METABROWSER_CONFIG_DIR=$PWD/shared METABROWSER_CACHE_DIR=$PWD/cache metab --doctor 2>&1 >/dev/null
metab --doctor: 2 problem(s):
  • open_in: The Metabrowser storage directory is accessible to other users (mode 0755). Run chmod 700 on it, or set the applicable override (METABROWSER_CACHE_DIR or METABROWSER_CONFIG_DIR) to a private directory you own. --present reads present_browser from config.yml there before it starts a server for a browser.
  • config: The Metabrowser storage directory is accessible to other users (mode 0755). Run chmod 700 on it, or set the applicable override (METABROWSER_CACHE_DIR or METABROWSER_CONFIG_DIR) to a private directory you own.
github: ok: GitHub CLI is signed in to github.com as octo-reader.
  gh: [FAKE_GH] (version 2.98.0; needs 2.81.0 or later)
  account: octo-reader (token from keyring)
  scopes: gist, read:org, repo, workflow
metab: ok: metab [METAB_VERSION]
  version: [METAB_VERSION]
  executable: [EXECUTABLE]
  python: [PYTHON]
  installed: in the Python environment [ENVIRONMENT]
  app: not looked for
git: ok: git version 2.50.1, which meets every floor
  executable: [FAKE_GIT]
  version: git version 2.50.1
config: problem: The Metabrowser storage directory is accessible to other users (mode 0755). Run chmod 700 on it, or set the applicable override (METABROWSER_CACHE_DIR or METABROWSER_CONFIG_DIR) to a private directory you own.
  directory: [SANDBOX]/shared
  source: METABROWSER_CONFIG_DIR
cache: ok: the cache directory is private and writable
  directory: [SANDBOX]/cache
  source: METABROWSER_CACHE_DIR
  free space: [FREE]
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
  "plugin_count": 11,
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
          "name": "installed",
          "value": "in the Python environment [ENVIRONMENT]"
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
      "summary": "git version 2.50.1, which meets every floor",
      "details": [
        {
          "name": "executable",
          "value": "[FAKE_GIT]"
        },
        {
          "name": "version",
          "value": "git version 2.50.1"
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
    }
  ]
}
? 1
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
