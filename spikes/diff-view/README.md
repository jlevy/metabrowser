# Diff View Spikes

Hands-on validation of the approaches in
[the Git diff view plan](../../docs/project/specs/active/plan-2026-07-18-git-diff-view.md)
and the
[stacks and build-options research](../../docs/project/research/research-2026-07-18-diff-ui-stacks-and-browser-build-options.md).
Findings and measurements are in [REPORT.md](REPORT.md).

Spike code is reference material, not shipped code.
Its npm dependencies are quarantined in per-spike `package.json` files with
`ignore-scripts` and exact pins, and are not part of the release toolchain or root
lockfile. Nothing under `spikes/` enters the wheel or sdist.

## Contents

- `backend/`: hardened Git subprocess adapter (`spike_git_adapter.py`), synthetic dirty
  repository builder, and deterministic renderer fixture generator
- `renderers/custom/`: dependency-free ESM unified-diff renderer with load-more gating
  and IntersectionObserver progressive mounting
- `renderers/server_html/`: server-rendered HTML projection (Python renders the table
  markup; the page only inserts it)
- `renderers/pierre/`: `@pierre/diffs` 1.2.12 vanilla `FileDiff`, bundled to one ESM
  artifact with pinned esbuild (patch-input and contents-input scenarios)
- `renderers/gdv/`: `@git-diff-view/core` 0.1.6 as the diff model with a small custom
  DOM layer (the package has no vanilla renderer)
- `harness/`: Playwright driver benchmarking every renderer page headlessly

## Running

```shell
# Fixtures (writes fixtures/out/, gitignored)
python3 backend/gen_synthetic_fixtures.py
python3 renderers/server_html/render_filepatch_html.py

# Backend adapter against a synthetic dirty repository
python3 backend/make_fixture_repo.py --dir /tmp/spike-repo
python3 backend/spike_git_adapter.py --repo /tmp/spike-repo --out /tmp/spike-out --contrast

# Library bundles (quarantined installs; scripts disabled)
(cd renderers/pierre && npm ci && node build.mjs)
(cd renderers/gdv && npm ci && node build.mjs)

# Browser benchmarks (uses the preinstalled Playwright Chromium)
(cd harness && npm ci && node run_bench.mjs)
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
