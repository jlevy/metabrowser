---
name: add-language-support
description: >-
  Add a programming language, or a related source format, to Metabrowser: its file-type
  family and GitHub color, its syntax highlighting, its Markdown fences, and its related
  project files. Use when someone asks Metabrowser to support, recognize, color, or
  highlight a language or file extension.
---
# Add Language Support

Follow [Adding a Language](../../../docs/adding-a-language.md) step by step.
It names every file to change and every check to run; this skill only adds the rules
for reading upstream.

## Copy Upstream, Decide Nothing

- **Identity, extensions, color:** GitHub linguist’s
  [`languages.yml`](https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml)
  on `main`. A `group:` entry takes its group’s color. Do not use a mirror package.
- **Source highlighting:** a grammar from Highlight.js’s
  [supported languages](https://github.com/highlightjs/highlight.js/blob/main/SUPPORTED_LANGUAGES.md),
  compiled for the vendored Highlight.js release.
  Review it against [SUPPLY-CHAIN-SECURITY.md](../../../SUPPLY-CHAIN-SECURITY.md)
  before pinning it.
- **Markdown fences:** [Pygments lexers](https://pygments.org/docs/lexers/), which
  KPress already uses.
- **Related files:** classify one only where linguist does, and say in the pull request
  what was left out and why.

When upstream lacks something (no color, no grammar, a missing keyword), say so and
link the upstream issue tracker instead of inventing a value or forking a grammar.

## Before Handoff

Plan with `tbd shortcut new-plan-spec` when the language needs a vendored grammar, then
finish with `make verify` and a changelog fragment.
The Lean change (`changelog.d/mb-h7f9.md`, its plan in `docs/project/specs/active/`)
is the worked example.
