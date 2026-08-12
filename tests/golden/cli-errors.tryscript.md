---
sandbox: true
path:
  - ../../.venv/bin
patterns:
  ROOT_ARG: '\[ROOT\]'
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
---
# Golden tests: usage errors

The full usage-error matrix for the flat CLI: mode conflicts, options outside their
mode, missing or extra roots, removed subcommand spellings, and value validation.
Usage errors report on stderr and exit 2, so commands merge streams with `2>&1`. Value
validation runs at parse time, before mode applicability (see the flat-CLI spec’s
Validation section), which the last two tests pin.

## Test: conflicting mode flags

```console
$ metab . --walk --plugins 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ mode flags are mutually exclusive; got --walk and --plugins                  │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

## Test: serve option explicitly passed in walk mode

```console
$ metab . --walk --port 9000 --no-open 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ --no-open, --port not valid with --walk                                      │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

## Test: walk option explicitly passed in serve mode

```console
$ metab . --json 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ --json not valid with serve mode (the default)                               │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

## Test: serve requires ROOT

```console
$ metab --no-open 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ ROOT is required for serve mode (the default); e.g. `metab .`                │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

## Test: walk requires ROOT

```console
$ metab --walk 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ ROOT is required for --walk; e.g. `metab . --walk`                           │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

## Test: API check requires ROOT

```console
$ metab --check-api 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ ROOT is required for --check-api; e.g. `metab . --check-api`                 │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

## Test: plugins mode rejects ROOT

```console
$ metab . --plugins 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ ROOT is not used with --plugins                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

## Test: remote mode rejects ROOT and hints at --path

```console
$ metab . --remote vm --path /runs 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ ROOT is not used with --remote; pass the remote directory with --path        │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

## Test: remote mode requires --path

```console
$ metab --remote vm 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ --remote requires --path with the remote directory to serve                  │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

## Test: removed subcommand spelling is rejected

```console
$ metab serve . 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ Got unexpected extra argument(s) (.)                                         │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

## Test: invalid --format value

```console
$ metab . --walk --format xml 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ Invalid value for '--format': must be one of text, json, yaml                │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

## Test: invalid --port value

```console
$ metab . --port 0 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ Invalid value for '--port': 0 is not in the range 1<=x<=65535.               │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

## Test: invalid value on a mode-inapplicable option reports the value

```console
$ metab --plugins --port 0 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ Invalid value for '--port': 0 is not in the range 1<=x<=65535.               │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

## Test: nonexistent serve root fails cleanly

```console
$ metab ./missing --no-open 2>&1
Error: [CWD]/missing is not a directory
? 1
```
