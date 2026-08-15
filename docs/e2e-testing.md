# End-to-End Testing

Metabrowser uses layered tests so server routes, browser contracts, plugins, and built
artifacts can fail independently and report a useful cause.

## Test Layers

### Python Unit and Route Tests

Pytest covers safe path resolution, inventory state, kind classification, manifest
validation, data-hook routing, log parsing, and HTTP response envelopes.
Lightweight request doubles exercise handlers directly when a network client would add
no value.

### Application Lifespan Tests

The lifespan suite starts the real Starlette application wiring, waits for the initial
inventory, and verifies tree, recent, capabilities, events, and watcher behavior.
These tests prove that startup and teardown tasks cooperate; individual route tests do
not.

### JavaScript Contract Tests

Node `vm` shims load the real SDK and every built-in `index.js` with small browser
stubs. They verify:

- every declared view has a matching registration;
- plugins do not read unloaded built-in namespaces at module-load time;
- KPress assets load once and failure paths remain visible;
- renderers can mount with their documented context shape.

These are contract tests, not visual browser tests.
Keep the shims small instead of growing an incomplete DOM implementation.

### Distribution Tests

`make build` inspects the wheel for required static assets and rejects repository-only
files. It then creates an isolated uv environment from the wheel and imports the package
and CLI. This catches missing package data and source-checkout assumptions.

## Running Tests

```shell
# Complete Python suite.
uv --config-file uv.toml run --frozen pytest

# One module or test.
uv --config-file uv.toml run --frozen pytest tests/test_plugin_loader.py
uv --config-file uv.toml run --frozen pytest tests/test_plugin_loader.py::test_classifier_priority_wins

# Full release gate.
make verify
```

Node-backed tests skip when Node is unavailable locally.
CI provides Node and treats those contracts as required.

## Adding Coverage

Choose the narrowest layer that proves the behavior:

- pure transforms and classifiers: unit test;
- response shape, ETag, path validation, or middleware: route test;
- background tasks and live changes: lifespan test;
- SDK registration or renderer lifecycle: Node contract test;
- package-data or import-boundary behavior: distribution test.

For regressions, make the test fail for the original defect before applying the fix.
Assert behavior and public contracts instead of copying implementation structure into
the test.

## Plugin Test Matrix

A plugin should cover:

1. manifest parsing and classifier matches, including near misses;
2. registry diagnostics through `metab --doctor`;
3. default-view mount and lazy-view mount;
4. data-hook success, validation errors, and unsafe paths;
5. disposal of requests, streams, listeners, timers, and charts;
6. wheel contents in a clean installation;
7. graceful fallback when the plugin is not installed.

Keep consumer plugin fixtures in the consumer repository.
The Metabrowser suite should use generic sample plugins so it cannot pass only because
an unrelated workspace package happens to be installed.

## Manual Browser Check

Before a release, serve the public-safe manual corpus and check the real browser:

```shell
uv --config-file uv.toml run --frozen metab ./tests/manual-fixtures --no-open
```

The corpus contains Markdown with frontmatter, structured JSON, JSONL events, source
code, an SVG image, and an opaque file large enough to exercise the binary view.
Keep these fixtures generic and free of copied production data.

Open the printed URL and verify:

- first paint appears before a large tree finishes indexing;
- Markdown, structured data, source, JSONL, image, and binary views render;
- the binary Bytes view loads a second chunk on **Load more**, appends without
  re-rendering the bytes already shown, and wraps without horizontal overflow at narrow
  and wide panes in both themes;
- a binary file above the preview ceiling reports the cutoff instead of loading;
- changing and deleting files updates tree and recent views;
- a direct hash path opens independently of the tree crawl;
- light and dark themes, narrow panes, keyboard focus, and print output remain usable;
- the console and Network panel contain no unexpected errors or missing assets.

Do not make the manual check the only coverage for a deterministic contract.

### Headless Screenshots

There is no automated visual-regression layer.
When a change is presentational and a reviewer needs to see it, drive a real browser
manually.

Chrome’s `--headless --screenshot --virtual-time-budget` mode does not work against the
shell: the page holds the `/api/events` stream open, so virtual time never drains and
Chrome hangs without writing a file.
Two approaches work instead.

Drive the live application over the DevTools protocol.
Start Chrome with `--headless=new --remote-debugging-port=<port>` and a scratch
`--user-data-dir`, read the page target from `http://127.0.0.1:<port>/json/list`, then
send `Emulation.setDeviceMetricsOverride`, `Page.enable`, `Page.navigate`, and
`Page.captureScreenshot` over the target’s WebSocket.
Node 24 provides a `WebSocket` global, so the driver needs no dependency.

For a question that is only about document CSS, skip the shell.
Request `/api/kpress/render` for the file and view, then write a standalone page that
inlines the returned `html` alongside the stylesheet entries in the returned asset
manifest and `/static/styles.css`. Such a page holds no event stream, so the ordinary
`--virtual-time-budget` screenshot works, and it can be rendered at several widths and
disclosure states in one pass.
Keep these harnesses in a scratch directory; they are debugging aids, not fixtures.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
