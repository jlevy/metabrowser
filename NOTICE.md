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

- **vscode-lean4** Lean 4 grammar
  ([Apache License 2.0](src/metabrowser/static/syntax/lean.license.txt),
  [leanprover/vscode-lean4](https://github.com/leanprover/vscode-lean4)).
  `src/metabrowser/static/syntax/lean.js` ports `syntaxes/lean4.json` to Highlight.js,
  copying its patterns; `tests/fixtures/vscode-lean4/` holds the pinned original.

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

- **Mermaid** v12.3.0
  ([MIT License](src/metabrowser/static/vendor/licenses/mermaid.txt),
  [mermaid.js.org](https://mermaid.js.org)). Its ES module build is vendored under
  `src/metabrowser/static/vendor/mermaid/`. The build bundles its own dependencies,
  among them DOMPurify (MPL-2.0 or Apache-2.0), D3 (ISC), dagre (MIT), Cytoscape (MIT),
  KaTeX (MIT), and the Eclipse Layout Kernel’s elkjs (EPL-2.0 or GPL-3.0-or-later, used
  here under GPL-3.0-or-later, which is compatible with Metabrowser’s license; its text
  is [elkjs.GPL-3.0.txt](src/metabrowser/static/vendor/licenses/elkjs.GPL-3.0.txt)). The
  source code of elkjs is available from
  [github.com/kieler/elkjs](https://github.com/kieler/elkjs).
  The license texts of all its production dependencies are vendored as
  [mermaid.bundled.txt](src/metabrowser/static/vendor/licenses/mermaid.bundled.txt).

- **Primer Octicons GitHub mark**
  ([MIT License](https://github.com/primer/octicons/blob/ea8e6bb79894cc7e85564ee9b53d86b418738d04/LICENSE),
  [Primer Octicons](https://github.com/primer/octicons)). The inline GitHub destination
  mark in `src/metabrowser/static/plugin-sdk-views.js` uses `mark-github-16.svg` at
  upstream commit `ea8e6bb79894cc7e85564ee9b53d86b418738d04`. Its copyright and license
  accompany the inline glyph in the distributed script.

- **Lucide neutral destination icons**
  ([ISC License](https://github.com/lucide-icons/lucide/blob/896aba0d195a4fec38ad7c4a90d00cb3389ebfea/LICENSE),
  [Lucide](https://github.com/lucide-icons/lucide)). The inline neutral issue and PR
  destination glyphs in `src/metabrowser/static/plugin-sdk-views.js` use
  `circle-dot.svg` and `git-pull-request.svg`, and the person glyph an author with no
  avatar shows in the same script uses `circle-user-round.svg`, and Open in Browser uses
  `arrow-up-right.svg`, all from release 1.17.0 at upstream commit
  `896aba0d195a4fec38ad7c4a90d00cb3389ebfea`. Their copyright and license accompany the
  glyphs in the distributed script.
  The browser and macOS app use `folder-git-2.svg`, `folder-dot.svg`, and a cloud-folder
  mark adapted from `folder-git-2.svg` and `cloud.svg` from the same release and commit.
  The ordinary folder’s `folder.svg` appears in the browser’s icon registry and in
  `RootMark.swift`. `source-kind-glyphs.license.txt` accompanies the glyphs in the
  distributed browser assets and macOS app resources:

  > ISC License
  > 
  > Copyright (c) 2026 Lucide Icons and Contributors
  > 
  > Permission to use, copy, modify, and/or distribute this software for any purpose
  > with or without fee is hereby granted, provided that the above copyright notice and
  > this permission notice appear in all copies.
  > 
  > THE SOFTWARE IS PROVIDED “AS IS” AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD
  > TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN
  > NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR
  > CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR
  > PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION,
  > ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

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
