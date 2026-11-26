---
name: mb-add-language
description: >-
  Add a programming language to Metabrowser end to end: its file-type family and GitHub
  color, its syntax highlighting in Source and diff views, its Markdown fences, and its
  related project files. Use when someone asks Metabrowser to support, recognize, color,
  or highlight a language or source-file extension.
---
# Add a Language to Metabrowser

Follow [Adding a Language](../../../docs/adding-a-language.md) step by step: it names
every file to change and every check to run.
This skill adds only the rules for reading upstream.
A file type that is not a programming language (a data format, a log, a binary) is
[mb-add-plugin](../mb-add-plugin/SKILL.md)’s.

## Copy Upstream, Decide Nothing

- **Identity, extensions, color:** GitHub linguist’s
  [`languages.yml`](https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml)
  on `main`, never a mirror package. A `group:` entry takes its group’s color.
- **Highlighting:** in order of preference, a grammar in the vendored Highlight.js
  build; one Highlight.js’s
  [supported languages](https://github.com/highlightjs/highlight.js/blob/main/SUPPORTED_LANGUAGES.md)
  lists that is current for the language, vendored; or a port of the language project’s
  own grammar, pinned and tested as the Lean port is.
  Review any package against [SUPPLY-CHAIN-SECURITY.md](../../../SUPPLY-CHAIN-SECURITY.md).
- **Markdown fences:** [Pygments lexers](https://pygments.org/docs/lexers/), which
  KPress uses.
- **Related files:** classify one only where linguist does, and say in the pull request
  what was left out and why.

When upstream lacks something, say so and link its tracker instead of inventing a value.

## Before Handoff

Plan with `tbd shortcut new-plan-spec`, and finish with `make verify` and a changelog
fragment. The guide links the Lean change as its worked example.
