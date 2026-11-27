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
  METABROWSER_OPEN_IN: "browser"
patterns:
  SANDBOX: '[^\s"]+/tryscript-[A-Za-z0-9]+'
  FAKE_GH: '[^\s"]+/fixtures/github-status/gh'
before: >-
  mkdir -p ok/uses-md gaps/needs-absent gaps/loop-a gaps/loop-b gaps/on-loop override/markdown &&
  printf '[plugin]\nname = "uses-md"\nsdk_version = "0.8"\nrequires = ["markdown"]\n' > ok/uses-md/manifest.toml &&
  printf '[plugin]\nname = "needs-absent"\nsdk_version = "0.8"\nrequires = ["absent"]\n' > gaps/needs-absent/manifest.toml &&
  printf '[plugin]\nname = "loop-a"\nsdk_version = "0.8"\nrequires = ["loop-b"]\n' > gaps/loop-a/manifest.toml &&
  printf '[plugin]\nname = "loop-b"\nsdk_version = "0.8"\nrequires = ["markdown", "loop-a"]\n' > gaps/loop-b/manifest.toml &&
  printf '[plugin]\nname = "on-loop"\nsdk_version = "0.8"\nrequires = ["loop-a"]\n' > gaps/on-loop/manifest.toml &&
  printf '[plugin]\nname = "markdown"\nsdk_version = "0.8"\nrequires = ["absent"]\n' > override/markdown/manifest.toml &&
  for dir in ok/uses-md gaps/needs-absent gaps/loop-a gaps/loop-b gaps/on-loop override/markdown; do printf '// No code: this plugin exists for its manifest.\n' > "$dir/index.js"; done
---
# Golden tests: declared plugin dependencies

A manifest’s `requires` names the plugins whose exports its browser code loads with
`mb.plugins.load(name)`. Discovery refuses a plugin whose requirements cannot be met,
and `--plugins`, `--plugin`, and `--doctor` report the graph of those it kept.
[Plugin Authoring](../../docs/plugins.md#declared-dependencies) states the rule, and
`tests/test_plugin_requirements.py` covers a manifest that requires itself, which its
own validation refuses.

The `before:` block writes operator plugins, loaded with `--plugins-dir`:

- `ok/uses-md` requires the built-in `markdown`, so it loads.
- `gaps/needs-absent` requires a plugin nobody provides.
- `gaps/loop-a` and `gaps/loop-b` require each other, and `loop-b` also requires
  `markdown`; `gaps/on-loop` requires `loop-a`, so it is refused with the cycle.
- `override/markdown` replaces the built-in `markdown` by name and requires a plugin
  nobody provides.

## Test: a plugin whose provider is loaded is kept, and its requirement listed

```console
$ metab --plugins-dir ok --plugin uses-md
name:            uses-md
display_name:    (none)
version:         0.0.0
sdk_version:     0.8
source:          local:[SANDBOX]/ok/uses-md
static_root:     [SANDBOX]/ok/uses-md
requires:        markdown
python_requires: (none)

kinds:

views:

data hooks:
  (none)

assets in static_root:
  - index.js
  - manifest.toml
? 0
```

## Test: --doctor reports the dependency graph

```console
$ metab --plugins-dir ok --doctor 2>/dev/null
metab --doctor: open_in browser (environment); --present looks for no app
metab --doctor: 19 plugin(s) OK
plugin requirements:
  agents: requires structured
  delimited: requires table
  diff: requires structured, pdf
  event-log: requires agents
  folder: requires markdown
  fsqlite: requires sqlite, table
  github: requires markdown, diff
  markdown: requires pdf
  softschema: requires structured, table
  sqlite: requires table
  structured: requires table
  unknown-jsonl: requires agents
  uses-md: requires markdown
github: ok: GitHub CLI is signed in to github.com as octo-reader.
  gh: [FAKE_GH] (version 2.98.0; needs 2.81.0 or later)
  account: octo-reader (token from keyring)
  scopes: gist, read:org, repo, workflow
...
? 0
```

## Test: a missing provider, a cycle, and what depends on them are refused

Each refusal names its cause: a provider that was not discovered, the shortest cycle
back to the plugin, or a provider that was itself refused.
The other plugins still load, so `--plugins` lists them and exits 1.

```console
$ metab --plugins-dir gaps --plugins 2>&1 >/dev/null

Discovery errors:
  • plugin 'loop-a' is refused: its requirements form a cycle, loop-a -> loop-b -> loop-a
  • plugin 'loop-b' is refused: its requirements form a cycle, loop-b -> loop-a -> loop-b
  • plugin 'needs-absent' is refused: it requires 'absent', which was not discovered
  • plugin 'on-loop' is refused: it requires 'loop-a', which was refused
? 1
```

## Test: --doctor lists each refusal as a problem

```console
$ metab --plugins-dir gaps --doctor 2>&1 >/dev/null
metab --doctor: 4 problem(s):
  • plugin 'loop-a' is refused: its requirements form a cycle, loop-a -> loop-b -> loop-a
  • plugin 'loop-b' is refused: its requirements form a cycle, loop-b -> loop-a -> loop-b
  • plugin 'needs-absent' is refused: it requires 'absent', which was not discovered
  • plugin 'on-loop' is refused: it requires 'loop-a', which was refused
plugin requirements:
  agents: requires structured
  delimited: requires table
  diff: requires structured, pdf
  event-log: requires agents
  folder: requires markdown
  fsqlite: requires sqlite, table
  github: requires markdown, diff
  markdown: requires pdf
  softschema: requires structured, table
  sqlite: requires table
  structured: requires table
  unknown-jsonl: requires agents
github: ok: GitHub CLI is signed in to github.com as octo-reader.
...
? 1
```

## Test: a refused override keeps the built-in it would replace

A replacement whose requirements cannot be met is refused like one whose manifest is
invalid: the built-in `markdown` stays, so `folder` and `github`, which require it, load
too.

```console
$ metab --plugins-dir override --doctor 2>&1 >/dev/null
metab --doctor: 1 problem(s):
  • plugin 'markdown' is refused: it requires 'absent', which was not discovered; the plugin it overrides (builtin) is kept
plugin requirements:
  agents: requires structured
  delimited: requires table
  diff: requires structured, pdf
  event-log: requires agents
  folder: requires markdown
  fsqlite: requires sqlite, table
  github: requires markdown, diff
  markdown: requires pdf
  softschema: requires structured, table
  sqlite: requires table
  structured: requires table
  unknown-jsonl: requires agents
github: ok: GitHub CLI is signed in to github.com as octo-reader.
...
? 1
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
