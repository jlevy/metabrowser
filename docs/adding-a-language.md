# Adding a Programming Language

A programming language reaches four registries in Metabrowser.
Each copies an upstream source of truth instead of deciding anything here, so adding a
language is mostly reading upstream carefully and changing one entry in each place.
Lean was added this way
([plan](project/specs/active/plan-2026-11-25-lean-language-support.md)); its diff is the
worked example.

| Step | What the reader gets | Upstream source |
| --- | --- | --- |
| 1. Family and kind | The Files filter, Overview’s type breakdown, the Treemap, file colors and icons | [linguist `languages.yml`](https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml) |
| 2. Source highlighting | Highlighted source in every Source view | [Highlight.js supported languages](https://github.com/highlightjs/highlight.js/blob/main/SUPPORTED_LANGUAGES.md) |
| 3. Markdown fences | Highlighted fenced code in rendered Markdown | [Pygments lexers](https://pygments.org/docs/lexers/) |
| 4. Related files | Build, manifest, and toolchain files classified correctly | the language’s own project tooling docs |

Do every step that applies, then [prove it](#5-prove-it).
Values (extensions, colors, versions, sizes) live in the files named below, beside their
definitions; this document does not restate them.

## 1. Family and Kind

Read the language’s entry in linguist’s `languages.yml` on `main`, not a mirror: the
`linguist-languages` npm package lagged a Lean color linguist had already added.
A language whose entry has `group:` takes its group’s color.

In `src/metabrowser/data/file-rollup-format/recommended-file-types.toml`:

- Add a `[[family]]` in the `code` group with `linguist` and `linguist_color` copied
  from upstream, and `hue` set to that color’s oklch hue, unchanged.
  `uv --config-file uv.toml run --frozen python -c "from metabrowser.color_oklch import hex_to_oklch; print(hex_to_oklch('#rrggbb'))"`
  prints it. A language linguist gives no color takes the hue
  `devtools/check_file_type_colors.py --suggest` prints.
- Add a `[[kind]]` listing linguist’s extensions, without dots.
- Increment `registry_revision`.

Then regenerate and check:

```bash
uv --config-file uv.toml run --frozen python devtools/file_type_contract.py --write
uv --config-file uv.toml run --frozen python devtools/file_type_contract.py
uv --config-file uv.toml run --frozen python devtools/check_file_type_colors.py
```

The revision bump changes the registry fingerprint the rollup goldens print; replace the
old fingerprint and revision in `tests/golden/` with the new ones.
The [File Rollup Format](project/architecture/file-rollup-format/file-rollup-format.md)
defines every field and when a change needs more than a revision.

## 2. Source Highlighting

`SYNTAX_LANGUAGE_BY_EXTENSION` in `src/metabrowser/file_extensions.py` maps an extension
to a Highlight.js language name (`SYNTAX_LANGUAGE_BY_BASENAME` for a name such as
`Makefile`). The browser receives the map through `settings.py`, so every Source view
routes alike.

- **A grammar in the vendored common build:** add the mapping and stop.
  `hljs.listLanguages()` in the browser console on any Metabrowser page lists the
  languages the vendored build registers.

- **A grammar Highlight.js ships outside the common build, or a third-party grammar its
  supported-languages table lists:** vendor it first, as `highlight-toml.min.js` and
  `highlight-lean.min.js` are.
  1. Review the package against
     [Review Before Adding](../SUPPLY-CHAIN-SECURITY.md#review-before-adding), and
     prefer one compiled for the vendored Highlight.js release:
     `tests/test_index_cdn_origins.py` requires every `highlight-*.min.js` banner to
     name it.
  2. Pin it in `package.json` with `npm install --save-dev --save-exact <pkg>@<version>`
     under the pinned Node, so `.npmrc`’s cool-off applies.
  3. Add a `VendorEntry` to `devtools/vendor_assets.py` with the destination
     `highlight-<language>.min.js`, and run `make vendor-assets`.
  4. Add the file to the prefetched tier in `server.py`’s `optional_script_assets`, with
     `"requires": "hljs"`
     ([Asset Loading Tiers](project/architecture/arch-browser-shell.md#asset-loading-tiers)),
     and to the lists in `tests/test_index_cdn_origins.py` and
     `tests/test_plugin_sdk_helpers.py`.
  5. Add the component to `NOTICE.md`.

  The syntax shim (`tests/dom/syntax-token-sdk-behavior.js`) loads every vendored
  grammar and fails when a mapped language is not registered.

- **A grammar scope the stylesheet does not color:** map it to an existing
  `--color-syntax-*` or status token in `styles.css`, or leave it plain.
  Never add a color literal.

## 3. Markdown Fences

KPress highlights fenced code on the server with Pygments, so a fence is already
highlighted when Pygments has a lexer for the fence’s name.
Check with
`uv --config-file uv.toml run --frozen python -c "from pygments.lexers import get_lexer_by_name; print(get_lexer_by_name('<name>'))"`.
A missing lexer is Pygments’ to add, not this repository’s.

## 4. Related Files

Classify a build, manifest, or toolchain file only where linguist does.
Most already belong to a family by extension (`*.toml`, `*.json`), and text with no
extension opens as text through content sniffing.
Build output directories are the project’s `.gitignore`’s to hide.
Record what you left out, and why, in the pull request.

## 5. Prove It

- `make test` runs the contracts above: the conformance fixture generated from the
  registry, the syntax shim, the vendored-asset manifest, and the goldens.
- Serve a folder holding a sample file (`metab <folder> --no-open`) and open it in a
  browser: the file’s icon takes the family color, its Source view is highlighted, and
  `metab <folder> --api '/api/rollup?path=.&depth=0'` names the family.
- Write a changelog fragment ([changelog.d](../changelog.d/README.md)).
- `make verify`.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
