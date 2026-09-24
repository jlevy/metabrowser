---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
patterns:
  ROOT_ARG: '\[ROOT\]'
  # A checkout appends how far past the tag it is and whether it is dirty,
  # which changes on every commit; the elision covers both forms.
  VERSION: '\d+[^\s]*( \([^)]*\))?'
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
 it in your browser. Select another operation with a mode flag.

 Data modes read the same server the browser reads, without a browser or a
 listening port: --api issues one route, --show reports the four layers
 behind one selection, --walk dumps the inventory, --diff shows a change
 set. A file:// or https:// Git source, or a GitHub web URL, is served, shown,
 or checked at the commit it selects under the untrusted profile; --no-serve
 only acquires it into the cache. Diagnostics: --check-api, --plugins,
 --plugin, --doctor.
 Remote serving: --remote.

╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│   [root]      TEXT  Root directory to serve, check, or walk; a file may be   │
│                     served directly. https, ssh, and file:// clone URLs and  │
│                     GitHub web URLs are Git sources, not local paths. An     │
│                     https:// or file:// source is acquired into the cache    │
│                     and opened at the commit its URL selects, or its default │
│                     branch's, always untrusted; --no-serve only acquires it; │
│                     ssh stays closed. With no ROOT and no mode, prints help. │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --version          Show the installed version and exit.                      │
│ --help             Show this message and exit.                               │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Modes (default: serve ROOT) ────────────────────────────────────────────────╮
│ --walk                    Walk ROOT with the inventory walker and dump the   │
│                           result (no server).                                │
│ --diff             SPEC   Show a change set: BASE..TARGET, one revision      │
│                           (against its first parent), or a .patch/.diff file │
│                           under ROOT.                                        │
│ --api              ROUTE  Issue one /api/ route through the real request     │
│                           stack and print the normalized envelope (no        │
│                           browser, no listening port).                       │
│ --show             PATH   Report the four layers for one selection: route,   │
│                           kind, views, and a model summary.                  │
│ --check-api               Run the navigation API scenario without a browser  │
│                           or listening port.                                 │
│ --no-serve                Acquire a file:// or https:// Git source into the  │
│                           cache without starting a server.                   │
│ --remote           HOST   SSH into HOST, start metab there, and tunnel it to │
│                           localhost. Pass the remote directory with --path.  │
│ --plugins                 List every discovered plugin.                      │
│ --plugin           NAME   Print the full resolved manifest for one plugin.   │
│ --doctor                  Validate browser plugins and installed artifact    │
│                           capabilities.                                      │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Diff (--diff SPEC) ─────────────────────────────────────────────────────────╮
│ --diff-patch        PATH  Print one changed file's hunks from the comparison │
│                           (--diff only).                                     │
│ --diff-check              Run the apply oracle: rebuild the target tree and  │
│                           compare hashes (--diff only).                      │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ API (--api ROUTE) ──────────────────────────────────────────────────────────╮
│ --data        FILE  Send FILE as the request body, making the request a POST │
│                     (--api only).                                            │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Shared by multiple modes (each option names its modes) ─────────────────────╮
│ --path                     TEXT              Serve: relative path from ROOT  │
│                                              to select on launch. Walk:      │
│                                              subtree for a JSON/YAML         │
│                                              all-at-once tree envelope.      │
│                                              Remote: remote directory to     │
│                                              serve (required).               │
│ --no-open                                    Don't auto-open the browser     │
│                                              (serve and remote modes).       │
│ --plugins-dir              PATH              Extra plugin directory; each    │
│                                              subdirectory containing         │
│                                              manifest.toml is loaded. May be │
│                                              passed multiple times. Combines │
│                                              additively with the             │
│                                              METABROWSER_PLUGINS_DIRS env    │
│                                              var (env-var dirs first, then   │
│                                              CLI; deduped). Applies when     │
│                                              serving, checking APIs, issuing │
│                                              --api or --show, and to the     │
│                                              plugin modes.                   │
│ --log-level                LEVEL             Log verbosity: DEBUG, INFO,     │
│                                              WARNING, ERROR, CRITICAL. DEBUG │
│                                              traces the inventory walker     │
│                                              (rewalk targets + resolved      │
│                                              paths). Overrides               │
│                                              METABROWSER_LOG_LEVEL. Applies  │
│                                              when serving, walking, issuing  │
│                                              --api or --show, checking APIs, │
│                                              or acquiring with --no-serve.   │
│ --untrusted                                  Conservative content-trust      │
│                                              profile: disable active content │
│                                              on /raw (drop allow-scripts)    │
│                                              and keep mutations off.         │
│                                              Individual flags override it.   │
│                                              Env: METAB_UNTRUSTED=1. Applies │
│                                              when serving and to --api,      │
│                                              --show, and --check-api.        │
│ --no-active-content                          Disable script execution on     │
│                                              content surfaces: /raw omits    │
│                                              allow-scripts from its sandbox. │
│                                              Env: METAB_ACTIVE_CONTENT=0.    │
│                                              Applies when serving and to     │
│                                              --api, --show, and --check-api. │
│ --allow-edits                                Publish the mutations           │
│                                              capability as on. No write      │
│                                              route consumes it yet. Env:     │
│                                              METAB_ALLOW_EDITS=1. Overrides  │
│                                              --untrusted for mutations.      │
│                                              Applies when serving and to     │
│                                              --api, --show, and --check-api. │
│ --format                   FORMAT            Output format: text (human      │
│                                              report) | json | yaml. Walk and │
│                                              diff: json/yaml dump the exact  │
│                                              data the browser consumes.      │
│                                              Show: json reports the four     │
│                                              layers as an object. Api: json  │
│                                              (default) or yaml renders the   │
│                                              envelope.                       │
│                                              [default: text]                 │
│ --index-timeout            SECONDS [x>=0.1]  Maximum time to wait for the    │
│                                              inventory to finish. Applies to │
│                                              --api, --show, and --check-api. │
│                                              [default: 60.0]                 │
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
 metab . --api '/api/tree?depth=2'
 metab . --show README.md
 metab . --check-api
 metab file:///path/to/repo.git
 metab file:///path/to/repo.git --no-serve
 metab --remote example-host --path /srv/shared-files
 metab --plugins
 Guide: https://github.com/jlevy/metabrowser/blob/main/docs/command-line.md
? 0
```

## Test: bare invocation prints the same help and exits 0

The full help is pinned once, above.
This test asserts only the relationship, so a help change is a single diff: any line
where the two outputs differ is printed and fails the transcript.

```console
$ metab > bare.txt; echo "exit: $?"; metab --help | diff bare.txt - && echo "identical to metab --help"
exit: 0
identical to metab --help
? 0
```

## Test: --version

```console
$ metab --version
metab [VERSION]
? 0
```
