---
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
patterns:
  ROOT_ARG: '\[ROOT\]'
  VERSION: '\d+[^\s]*'
---
# Golden tests: top-level CLI surface

Console goldens for the flat `metab` command per
`tbd guidelines golden-testing-guidelines`. Regenerate after an intended change with
`make golden-update` and review the diff.

## Test: --help shows the full mode-grouped option surface

```console
$ metab --help

 Usage: metab [OPTIONS] [ROOT_ARG]

 Browse local files from your web browser, with extensible plugin-based
 rendering of Markdown, code, JSON, YAML, logs, and other files.

 Serving is the default: `metab .` serves the current directory and opens
 it in your browser. Select another operation with a mode flag (--walk,
 --diff, --check-api, --remote, --plugins, --plugin, --doctor).

╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│   [root]      PATH  Root directory to serve, check, or walk; a file may be   │
│                     served directly. With no ROOT and no mode, prints help.  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --version          Show the installed version and exit.                      │
│ --help             Show this message and exit.                               │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Modes (default: serve ROOT) ────────────────────────────────────────────────╮
│ --walk                   Walk ROOT with the inventory walker and dump the    │
│                          result (no server).                                 │
│ --diff             SPEC  Show a change set: BASE..TARGET, one revision       │
│                          (against its first parent), or a .patch/.diff file  │
│                          under ROOT.                                         │
│ --check-api              Run the navigation API scenario without a browser   │
│                          or listening port.                                  │
│ --remote           HOST  SSH into HOST, start metab there, and tunnel it to  │
│                          localhost. Pass the remote directory with --path.   │
│ --plugins                List every discovered plugin.                       │
│ --plugin           NAME  Print the full resolved manifest for one plugin.    │
│ --doctor                 Validate every discovered plugin; exit non-zero on  │
│                          any problem.                                        │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Diff (--diff SPEC) ─────────────────────────────────────────────────────────╮
│ --diff-patch        PATH  Print one changed file's hunks from the comparison │
│                           (--diff only).                                     │
│ --diff-check              Run the apply oracle: rebuild the target tree and  │
│                           compare hashes (--diff only).                      │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Shared by multiple modes (each option names its modes) ─────────────────────╮
│ --path               TEXT   Serve: relative path from ROOT to select on      │
│                             launch. Walk: subtree for a JSON/YAML            │
│                             all-at-once tree envelope. Remote: remote        │
│                             directory to serve (required).                   │
│ --no-open                   Don't auto-open the browser (serve and remote    │
│                             modes).                                          │
│ --plugins-dir        PATH   Extra plugin directory; each subdirectory        │
│                             containing manifest.toml is loaded. May be       │
│                             passed multiple times. Combines additively with  │
│                             the METABROWSER_PLUGINS_DIRS env var (env-var    │
│                             dirs first, then CLI; deduped). Applies when     │
│                             serving, checking APIs, and to the plugin modes. │
│ --log-level          LEVEL  Log verbosity: DEBUG, INFO, WARNING, ERROR,      │
│                             CRITICAL. DEBUG traces the inventory walker      │
│                             (rewalk targets + resolved paths). Overrides     │
│                             METABROWSER_LOG_LEVEL. Applies when serving,     │
│                             walking, or checking APIs.                       │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Serve ──────────────────────────────────────────────────────────────────────╮
│ --port        INTEGER RANGE [1<=x<=65535]  Server port. [default: 8411]      │
│ --host        TEXT                         Host to bind to. A concrete value │
│                                            is automatically permitted by the │
│                                            Host-header allowlist; wildcard   │
│                                            binds (0.0.0.0, ::) use loopback  │
│                                            for the local URL, and additional │
│                                            trusted names can be allowed with │
│                                            METABROWSER_ALLOWED_HOSTS (see    │
│                                            SECURITY.md).                     │
│                                            [default: 127.0.0.1]              │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Walk (--walk) ──────────────────────────────────────────────────────────────╮
│ --format                        FORMAT                Output format: text    │
│                                                       (human report) | json  │
│                                                       | yaml. json/yaml dump │
│                                                       the exact data the nav │
│                                                       panel consumes.        │
│                                                       [default: text]        │
│ --stream       --all-at-once                          Streaming emits one    │
│                                                       walker record per line │
│                                                       (json→JSONL, yaml→doc  │
│                                                       stream), in walk order │
│                                                       (the SSE upsert        │
│                                                       surface). All-at-once  │
│                                                       emits the full         │
│                                                       /api/tree envelope.    │
│                                                       Ignored for --format   │
│                                                       text.                  │
│                                                       [default: all-at-once] │
│ --detail                        LEVEL                 Text-report detail:    │
│                                                       summary | dirs | all   │
│                                                       (only with --format    │
│                                                       text).                 │
│                                                       [default: all]         │
│ --max-depth                     INTEGER RANGE [x>=0]  Max walk depth.        │
│                                                       [default: 20]          │
│ --max-files                     INTEGER RANGE [x>=1]  Max files before       │
│                                                       truncation.            │
│                                                       [default: 500000]      │
│ --type                          TOKEN                 Keep only files of     │
│                                                       this type: an          │
│                                                       extension (.md,        │
│                                                       .min.js) or a whole    │
│                                                       filename (README).     │
│                                                       Repeatable, or         │
│                                                       comma-separated.       │
│ --age                           WINDOW                Keep only files        │
│                                                       modified within a      │
│                                                       window: live, 1h, 24h, │
│                                                       7d, 30d.               │
│ --min-size                      SIZE                  Keep only files at     │
│                                                       least this large.      │
│                                                       Plain bytes or a k/m/g │
│                                                       suffix (10m).          │
│ --ignored      --no-ignored                           Include gitignored     │
│                                                       entries in the         │
│                                                       filtered result.       │
│                                                       [default: ignored]     │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ API check (--check-api) ────────────────────────────────────────────────────╮
│ --index-timeout        SECONDS [x>=0.1]  Maximum time to wait for the        │
│                                          inventory to finish.                │
│                                          [default: 60.0]                     │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Remote (--remote) ──────────────────────────────────────────────────────────╮
│ --base-port          INTEGER RANGE               Starting port for local +   │
│                      [1<=x<=65535]               remote port search (walks   │
│                                                  upward).                    │
│                                                  [default: 8411]             │
│ --ssh-options        TEXT                        Extra SSH flags (e.g. '-i   │
│                                                  ~/.ssh/mykey').             │
│ --gcp                                            Use gcloud compute ssh      │
│                                                  instead of plain ssh.       │
│ --zone               TEXT                        GCP zone (only with --gcp). │
│                                                  [default: us-central1-b]    │
│ --project            TEXT                        GCP project (only with      │
│                                                  --gcp).                     │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Plugins (--plugins / --plugin / --doctor) ──────────────────────────────────╮
│ --json          Emit structured JSON (plugin modes).                         │
╰──────────────────────────────────────────────────────────────────────────────╯

 Examples:
 metab .
 metab ./path/to/directory --no-open
 metab . --walk --format json
 metab . --check-api
 metab --remote example-host --path /srv/shared-files
 metab --plugins
? 0
```

## Test: bare invocation shows help

```console
$ metab

 Usage: metab [OPTIONS] [ROOT_ARG]

 Browse local files from your web browser, with extensible plugin-based
 rendering of Markdown, code, JSON, YAML, logs, and other files.

 Serving is the default: `metab .` serves the current directory and opens
 it in your browser. Select another operation with a mode flag (--walk,
 --diff, --check-api, --remote, --plugins, --plugin, --doctor).

╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│   [root]      PATH  Root directory to serve, check, or walk; a file may be   │
│                     served directly. With no ROOT and no mode, prints help.  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --version          Show the installed version and exit.                      │
│ --help             Show this message and exit.                               │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Modes (default: serve ROOT) ────────────────────────────────────────────────╮
│ --walk                   Walk ROOT with the inventory walker and dump the    │
│                          result (no server).                                 │
│ --diff             SPEC  Show a change set: BASE..TARGET, one revision       │
│                          (against its first parent), or a .patch/.diff file  │
│                          under ROOT.                                         │
│ --check-api              Run the navigation API scenario without a browser   │
│                          or listening port.                                  │
│ --remote           HOST  SSH into HOST, start metab there, and tunnel it to  │
│                          localhost. Pass the remote directory with --path.   │
│ --plugins                List every discovered plugin.                       │
│ --plugin           NAME  Print the full resolved manifest for one plugin.    │
│ --doctor                 Validate every discovered plugin; exit non-zero on  │
│                          any problem.                                        │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Diff (--diff SPEC) ─────────────────────────────────────────────────────────╮
│ --diff-patch        PATH  Print one changed file's hunks from the comparison │
│                           (--diff only).                                     │
│ --diff-check              Run the apply oracle: rebuild the target tree and  │
│                           compare hashes (--diff only).                      │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Shared by multiple modes (each option names its modes) ─────────────────────╮
│ --path               TEXT   Serve: relative path from ROOT to select on      │
│                             launch. Walk: subtree for a JSON/YAML            │
│                             all-at-once tree envelope. Remote: remote        │
│                             directory to serve (required).                   │
│ --no-open                   Don't auto-open the browser (serve and remote    │
│                             modes).                                          │
│ --plugins-dir        PATH   Extra plugin directory; each subdirectory        │
│                             containing manifest.toml is loaded. May be       │
│                             passed multiple times. Combines additively with  │
│                             the METABROWSER_PLUGINS_DIRS env var (env-var    │
│                             dirs first, then CLI; deduped). Applies when     │
│                             serving, checking APIs, and to the plugin modes. │
│ --log-level          LEVEL  Log verbosity: DEBUG, INFO, WARNING, ERROR,      │
│                             CRITICAL. DEBUG traces the inventory walker      │
│                             (rewalk targets + resolved paths). Overrides     │
│                             METABROWSER_LOG_LEVEL. Applies when serving,     │
│                             walking, or checking APIs.                       │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Serve ──────────────────────────────────────────────────────────────────────╮
│ --port        INTEGER RANGE [1<=x<=65535]  Server port. [default: 8411]      │
│ --host        TEXT                         Host to bind to. A concrete value │
│                                            is automatically permitted by the │
│                                            Host-header allowlist; wildcard   │
│                                            binds (0.0.0.0, ::) use loopback  │
│                                            for the local URL, and additional │
│                                            trusted names can be allowed with │
│                                            METABROWSER_ALLOWED_HOSTS (see    │
│                                            SECURITY.md).                     │
│                                            [default: 127.0.0.1]              │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Walk (--walk) ──────────────────────────────────────────────────────────────╮
│ --format                        FORMAT                Output format: text    │
│                                                       (human report) | json  │
│                                                       | yaml. json/yaml dump │
│                                                       the exact data the nav │
│                                                       panel consumes.        │
│                                                       [default: text]        │
│ --stream       --all-at-once                          Streaming emits one    │
│                                                       walker record per line │
│                                                       (json→JSONL, yaml→doc  │
│                                                       stream), in walk order │
│                                                       (the SSE upsert        │
│                                                       surface). All-at-once  │
│                                                       emits the full         │
│                                                       /api/tree envelope.    │
│                                                       Ignored for --format   │
│                                                       text.                  │
│                                                       [default: all-at-once] │
│ --detail                        LEVEL                 Text-report detail:    │
│                                                       summary | dirs | all   │
│                                                       (only with --format    │
│                                                       text).                 │
│                                                       [default: all]         │
│ --max-depth                     INTEGER RANGE [x>=0]  Max walk depth.        │
│                                                       [default: 20]          │
│ --max-files                     INTEGER RANGE [x>=1]  Max files before       │
│                                                       truncation.            │
│                                                       [default: 500000]      │
│ --type                          TOKEN                 Keep only files of     │
│                                                       this type: an          │
│                                                       extension (.md,        │
│                                                       .min.js) or a whole    │
│                                                       filename (README).     │
│                                                       Repeatable, or         │
│                                                       comma-separated.       │
│ --age                           WINDOW                Keep only files        │
│                                                       modified within a      │
│                                                       window: live, 1h, 24h, │
│                                                       7d, 30d.               │
│ --min-size                      SIZE                  Keep only files at     │
│                                                       least this large.      │
│                                                       Plain bytes or a k/m/g │
│                                                       suffix (10m).          │
│ --ignored      --no-ignored                           Include gitignored     │
│                                                       entries in the         │
│                                                       filtered result.       │
│                                                       [default: ignored]     │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ API check (--check-api) ────────────────────────────────────────────────────╮
│ --index-timeout        SECONDS [x>=0.1]  Maximum time to wait for the        │
│                                          inventory to finish.                │
│                                          [default: 60.0]                     │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Remote (--remote) ──────────────────────────────────────────────────────────╮
│ --base-port          INTEGER RANGE               Starting port for local +   │
│                      [1<=x<=65535]               remote port search (walks   │
│                                                  upward).                    │
│                                                  [default: 8411]             │
│ --ssh-options        TEXT                        Extra SSH flags (e.g. '-i   │
│                                                  ~/.ssh/mykey').             │
│ --gcp                                            Use gcloud compute ssh      │
│                                                  instead of plain ssh.       │
│ --zone               TEXT                        GCP zone (only with --gcp). │
│                                                  [default: us-central1-b]    │
│ --project            TEXT                        GCP project (only with      │
│                                                  --gcp).                     │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Plugins (--plugins / --plugin / --doctor) ──────────────────────────────────╮
│ --json          Emit structured JSON (plugin modes).                         │
╰──────────────────────────────────────────────────────────────────────────────╯

 Examples:
 metab .
 metab ./path/to/directory --no-open
 metab . --walk --format json
 metab . --check-api
 metab --remote example-host --path /srv/shared-files
 metab --plugins
? 0
```

## Test: --version

```console
$ metab --version
metab [VERSION]
? 0
```
