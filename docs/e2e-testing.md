# End-to-End Testing

MetaBrowser uses layered tests so server routes, browser contracts, plugins, and built
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
uv run pytest

# One module or test.
uv run pytest tests/test_plugin_loader.py
uv run pytest tests/test_plugin_loader.py::test_classifier_priority_wins

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
2. registry diagnostics through `metab plugins doctor`;
3. default-view mount and lazy-view mount;
4. data-hook success, validation errors, and unsafe paths;
5. disposal of requests, streams, listeners, timers, and charts;
6. wheel contents in a clean installation;
7. graceful fallback when the plugin is not installed.

Keep consumer plugin fixtures in the consumer repository.
The MetaBrowser suite should use generic sample plugins so it cannot pass only because
an unrelated workspace package happens to be installed.

## Manual Browser Check

Before a release, run a small local fixture and check the real browser:

```shell
uv run metab serve ./tests/fixtures --no-open
```

Open the printed URL and verify:

- first paint appears before a large tree finishes indexing;
- Markdown, structured data, source, JSONL, image, and binary views render;
- changing and deleting files updates tree and recent views;
- a direct hash path opens independently of the tree crawl;
- light and dark themes, narrow panes, keyboard focus, and print output remain usable;
- the console and Network panel contain no unexpected errors or missing assets.

Do not make the manual check the only coverage for a deterministic contract.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
