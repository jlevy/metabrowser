---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
patterns:
  PYDANTIC_URL: 'https://errors\.pydantic\.dev/\d+\.\d+/v/value_error'
before: >-
  mkdir -p viewroot mdroot pair/alpha pair/beta stack/prnotes reserved/reskey override/steal &&
  printf 'mine\n' > viewroot/b.myk &&
  printf '# Notes\n' > mdroot/a.md &&
  printf '[plugin]\nname = "alpha"\nsdk_version = "0.7"\n[[kind]]\nid = "myk"\nmatch = { ext = ".myk" }\n[[view]]\nkind = "myk"\nid = "main"\nlabel = "Main"\nkey = "m"\ndefault = true\n' > pair/alpha/manifest.toml &&
  printf '[plugin]\nname = "beta"\nsdk_version = "0.7"\n[[view]]\nkind = "myk"\nid = "more"\nlabel = "More"\nkey = "M"\n' > pair/beta/manifest.toml &&
  printf '[plugin]\nname = "prnotes"\nsdk_version = "0.7"\n[[view]]\nkind = "pull-request"\nid = "notes"\nlabel = "Notes"\nkey = "N"\n' > stack/prnotes/manifest.toml &&
  printf '[plugin]\nname = "reskey"\nsdk_version = "0.7"\n[[view]]\nkind = "markdown"\nid = "outline"\nlabel = "Outline"\nkey = "T"\n' > reserved/reskey/manifest.toml &&
  printf '[plugin]\nname = "steal"\nsdk_version = "0.7"\n[[view]]\nkind = "markdown"\nid = "rendered"\nlabel = "Document"\nkey = "s"\ndefault = true\n' > override/steal/manifest.toml &&
  for dir in pair/alpha pair/beta stack/prnotes reserved/reskey override/steal; do printf '// No renderer: these plugins exist for their manifests.\n' > "$dir/index.js"; done
---
# Golden tests: view keys across plugin manifests

A view’s one-letter `key` is checked at two levels.
The manifest loader refuses a key that no view of any kind may hold.
`keymap.check_view_keys` checks a kind’s merged view list, which spans manifests: the
first view in tab order keeps a shared key, a key the shell reserves for that kind is
dropped, and the view is still served.
`--show` prints what the server serves, and `--doctor` reports each dropped key and
exits 1.

The `before:` block writes five operator plugins, loaded with `--plugins-dir`:

- `alpha` declares the `myk` kind and its Main view, keyed `m`.
- `beta` adds a More view to `myk`, keyed `M`. Keys are compared without case, so it
  collides with Main.
- `prnotes` adds a Notes view to `pull-request`, keyed `N`, which the shell reserves
  there for the next pull request in a stack.
- `reskey` adds an Outline view to `markdown`, keyed `T`, which the shell reserves
  everywhere for Quick Search.
- `steal` overrides Markdown’s Document view and keys it `s`, which the built-in Source
  view declares.

## Test: two plugins that share a key on one kind: the first view keeps it

```console
$ metab viewroot --plugins-dir pair --show b.myk
show: b.myk
route: /view/b.myk
kind: myk
views: main (default, key M), more
model: text envelope; size=5 content_bytes=5 content_truncated=False
? 0
```

## Test: --doctor names the view that lost the key and the plugin that holds it

tryscript matches stdout and stderr as one text, so each stream is recorded on its own.
The problem is on stderr.

```console
$ metab --doctor --plugins-dir pair >/dev/null
metab --doctor: 1 problem(s):
  • plugin 'beta': view 'more' of kind 'myk' declares key 'm', but view 'main' (plugin 'alpha') already holds it; the view is served without a key
? 1
```

## Test: --doctor writes nothing to stdout when it finds a problem

```console
$ metab --doctor --plugins-dir pair 2>/dev/null
? 1
```

## Test: --doctor --json reports the same problem

```console
$ metab --doctor --json --plugins-dir pair 2>/dev/null
{
  "ok": false,
  "plugin_count": 13,
  "problems": [
    "plugin 'beta': view 'more' of kind 'myk' declares key 'm', but view 'main' (plugin 'alpha') already holds it; the view is served without a key"
  ]
}
? 1
```

## Test: a pull-request view keyed N loads, and is served without the key

`N` and `P` are reserved only for `pull-request`, so the loader accepts the manifest,
since another kind could use the letter, and the merged list drops it.

```console
$ metab --doctor --plugins-dir stack >/dev/null
metab --doctor: 1 problem(s):
  • plugin 'prnotes': view 'notes' of kind 'pull-request' declares key 'n', which is reserved for the shell's next pull request in the stack; the view is served without a key
? 1
```

## Test: a key the shell reserves everywhere is refused at load

The plugin is not loaded, so `plugin_count` is the eleven built-in plugins alone.

```console
$ metab --doctor --json --plugins-dir reserved 2>/dev/null
{
  "ok": false,
  "plugin_count": 11,
  "problems": [
    "[CWD]/reserved/reskey/manifest.toml: 1 validation error for PluginManifest\nview.0.key\n  Value error, key 'T' is reserved for the shell's Quick Search [type=value_error, input_value='T', input_type=str]\n    For further information visit [PYDANTIC_URL]"
  ]
}
? 1
```

## Test: an override that takes a built-in view’s key holds it

`steal` replaces Document in place, so Document stays first in tab order and keeps `s`.
Source is served without its key.

```console
$ metab mdroot --plugins-dir override --show a.md
show: a.md
route: /view/a.md
kind: markdown
views: rendered (default, key S), source
model: text envelope; size=8 content_bytes=8 content_truncated=False
? 0
```

## Test: --doctor blames the override, not the built-in view it replaced

The problem names the built-in `markdown` plugin, whose Source lost the key, and
`steal`, whose Document holds it.

```console
$ metab --doctor --plugins-dir override >/dev/null
metab --doctor: 1 problem(s):
  • plugin 'markdown': view 'source' of kind 'markdown' declares key 's', but view 'rendered' (plugin 'steal') already holds it; the view is served without a key
? 1
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
