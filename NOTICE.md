# Metabrowser Notices

Metabrowser’s own license is AGPL-3.0-or-later, declared in `LICENSE`. This file records
the third-party components Metabrowser vendors or bundles, each under its own license,
independent of Metabrowser’s license.

## Vendored and Bundled Components

- **Visual Studio Code Source Control Graph**
  ([MIT License](src/metabrowser/static/vendor/licenses/vscode.txt),
  [Visual Studio Code](https://github.com/microsoft/vscode)). The commit-graph swimlane
  implementation in `src/metabrowser/static/git-graph.js` is derived from Visual Studio
  Code’s `scmHistory.ts`, copied at upstream commit
  `9245212c26af8113b3b96392c04563623cd99811` (2026-08-07).
- **Visual Studio Code Diff Algorithms**
  ([MIT License](src/metabrowser/static/vendor/licenses/vscode.txt),
  [Visual Studio Code](https://github.com/microsoft/vscode)). The browser-local
  changed-run refiner in `src/metabrowser/builtin_plugins/diff/diff-intraline.js` adapts
  the sequence diff, dynamic-programming, Myers, boundary-scoring, and cleanup code from
  `defaultLinesDiffComputer` at upstream commit
  `77f86f3d3a05cf5d6f765705e816341c918b7dae`.
- **Mustache.js** v4.2.0
  ([MIT License](src/metabrowser/static/vendor/licenses/mustache.txt),
  [mustache.js](https://github.com/janl/mustache.js)). The browser runtime is vendored
  as `src/metabrowser/static/vendor/mustache.min.js`.
- **highlight.js** v11.9.0
  ([BSD 3-Clause License](src/metabrowser/static/vendor/licenses/@highlightjs__cdn-assets.txt),
  [highlightjs.org](https://highlightjs.org)). The browser runtime, TOML language
  module, and GitHub stylesheet are vendored under `src/metabrowser/static/vendor/`.
- **Chart.js** v4.5.1
  ([MIT License](src/metabrowser/static/vendor/licenses/chart.js.txt),
  [chartjs.org](https://www.chartjs.org)). The browser bundle is vendored as
  `src/metabrowser/static/vendor/chart.umd.min.js`.
- **chartjs-adapter-date-fns** v3.0.0
  ([MIT License](src/metabrowser/static/vendor/licenses/chartjs-adapter-date-fns.txt),
  [Chart.js adapter repository](https://github.com/chartjs/chartjs-adapter-date-fns)).
  The browser bundle is vendored under `src/metabrowser/static/vendor/`.
- **chartjs-plugin-annotation** v3.1.0
  ([MIT License](src/metabrowser/static/vendor/licenses/chartjs-plugin-annotation.txt),
  [Chart.js annotation plugin](https://www.chartjs.org/chartjs-plugin-annotation/)). The
  browser bundle is vendored under `src/metabrowser/static/vendor/`.

## Runtime Dependencies

Python dependencies are declared in `pyproject.toml`. They are installed under their own
licenses and are not redistributed by this package.

## Development Tooling

Development-only JavaScript dependencies are declared in `package.json`. They are
installed from the committed lockfile under their own licenses and are not redistributed
unless listed above as vendored components.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
