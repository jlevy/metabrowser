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
| 2. Source highlighting | Highlighted source in Source views and diffs | [Highlight.js supported languages](https://github.com/highlightjs/highlight.js/blob/main/SUPPORTED_LANGUAGES.md) |
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
`Makefile`). The browser receives the map through `settings.py`, so Source views and
diffs route alike. Take the first grammar that applies:

1. **One in the vendored common build:** add the mapping and stop.
   `hljs.listLanguages()` in the browser console on any Metabrowser page lists the
   languages the vendored build registers.

2. **One Highlight.js publishes outside the common build, or a third-party grammar its
   supported-languages table lists, if it is current for the language:** vendor it, as
   `highlight-toml.min.js` is.
   1. Review the package against
      [Review Before Adding](../SUPPLY-CHAIN-SECURITY.md#review-before-adding).
      `tests/test_index_cdn_origins.py` requires a vendored grammar to be compiled for
      the vendored Highlight.js release.
   2. Pin it with `npm install --save-dev --save-exact <pkg>@<version>` under the pinned
      Node, so `.npmrc`’s cool-off applies.
   3. Add a `VendorEntry` to `devtools/vendor_assets.py` with the destination
      `highlight-<language>.min.js`, and run `make vendor-assets`.
   4. Add the component to `NOTICE.md`.

3. **Otherwise, port the language project’s own grammar,** usually the TextMate grammar
   its editor extension ships, to `src/metabrowser/static/syntax/<language>.js`, as
   `lean.js` ports the official Lean 4 grammar.
   The Lean 3 grammar Highlight.js lists missed most of Lean 4, which is why Lean took
   this path.
   - Copy every upstream regex verbatim into a `String.raw` constant of its own, so one
     no rule reads fails the lint as an unused variable, and map its TextMate scopes to
     the
     [standard Highlight.js scopes](https://highlightjs.readthedocs.io/en/latest/css-classes-reference.html).
   - Change a regex only where it is compiled, through a named adaptation, as
     `ADAPTATIONS` in `lean.js` does.
     A TextMate grammar runs on Oniguruma, one line at a time; Highlight.js runs
     JavaScript regexes over the whole file.
     So `\b` and `\w` are Unicode upstream and ASCII in JavaScript, POSIX classes do not
     exist in JavaScript, and a scan that upstream stops at the end of its line runs to
     the end of the file here, at every occurrence.
     Bound each such scan, and measure a file of `SYNTAX_HIGHLIGHT_MAX_BYTES` made of
     the unclosed opener before and after.
   - Highlight.js tries a mode’s contents before its `end`, the reverse of TextMate;
     guard a contained pattern with a lookahead of the `end` where the two can meet.
     It scopes one capture of a `begin` only when the `begin` is an array of parts.
   - Pin the upstream file and its license under `tests/fixtures/`, and test as
     `tests/test_lean_grammar.py` does: the port’s constants are every upstream regex
     and no other, so refreshing the fixture fails until the port follows it, and every
     constant and every adaptation has source run through the vendored runtime with the
     scopes it should take.
   - Put the license beside the port and add it to `NOTICE.md`.

The first path adds no script.
The other two add one, and it needs a loading tier chosen from its measured size
([Asset Loading Tiers](project/architecture/arch-browser-shell.md#asset-loading-tiers)).
A grammar that is small beside the Highlight.js runtime joins the prefetched tier:
`optional_script_assets` in `server.py` with `"requires": "hljs"`, where a comment
records each grammar’s size; add the new one’s. That tier is fetched on every page, so
when the grammars together are no longer small beside the runtime, the next step is to
load each on demand by language.
Add the script to the lists in `tests/test_index_cdn_origins.py` and
`tests/test_plugin_sdk_helpers.py` as well.

The syntax shim (`tests/dom/syntax-token-sdk-behavior.js`) loads every grammar in
`static/vendor/` and `static/syntax/` and fails when a language the extension map names
is not registered. That mapping check is the shim’s whole coverage of a new language;
what the grammar highlights is for the grammar’s own test.

A scope the stylesheet does not color takes an existing `--color-syntax-*` or status
token in `styles.css`, or stays plain.
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

Look at the language’s own documentation generator too (Lean’s doc-gen4, Rust’s
rustdoc): how it presents a source file, and the line-range links it makes, show what a
reader of that language expects.
Record a view worth building as a follow-up in the plan.

## 5. Prove It

- `make test` runs the contracts above: the conformance fixture generated from the
  registry, the syntax shim, the vendored-asset manifest, and the goldens.
- Serve a folder holding a sample file (`metab <folder> --no-open`) and open it in a
  browser: the file’s icon takes the family color, its Source view and a diff of it are
  highlighted, and `metab <folder> --api '/api/rollup?path=.&depth=0'` names the family.
- Write a changelog fragment ([changelog.d](../changelog.d/README.md)).
- `make verify`.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
