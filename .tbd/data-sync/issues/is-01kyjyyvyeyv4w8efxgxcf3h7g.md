---
type: is
id: is-01kyjyyvyeyv4w8efxgxcf3h7g
title: Upstream tryscript fixes from the metabrowser golden migration
kind: task
status: open
priority: 2
version: 2
labels:
  - tryscript
dependencies: []
created_at: 2026-07-27T23:36:00.205Z
updated_at: 2026-08-16T08:05:43.300Z
extensions:
  linear:
    id: 1434375c-de30-4a72-8d68-dbb68115ba2b
    linked_at: 2026-08-16T08:05:43.300Z
---
Findings from migrating metabrowser's CLI goldens to tryscript 0.1.7, for upstream fixes in jlevy/tryscript. Verified against dist/src (preprocessPaths, normalizeOutput, patternToRegex) and reproduced in isolation.

1. No escape for literal `[ROOT]`/`[CWD]` in expected output (high). preprocessPaths unconditionally replaceAll-substitutes `[ROOT]` and `[CWD]` before matching. Click/Typer CLIs print `Usage: prog [OPTIONS] [ROOT]`, so their usage line can never be asserted literally; every metabrowser help and usage-error test failed. Workaround in metabrowser: custom pattern `ROOT_ARG: '\[ROOT\]'` plus devtools/golden_fixup.py to re-apply it after --update. Suggested fix: an escape syntax (e.g. `[[ROOT]]`) plus a docs note.

2. Failure diff hides the real mismatch (high). The displayed diff uses raw actual output vs raw expected, while matching uses normalizeOutput plus pattern substitution. Two symptoms: a pattern-substitution failure where text is otherwise identical shows an EMPTY diff (undebuggable without reading source), and ANSI codes appear in the shown diff even though comparison strips them (misleading red herring). Suggested fix: display the diff between the same normalized/preprocessed strings the matcher compares, or annotate when substitution changed expected.

3. Frontmatter env cannot override built-in NO_COLOR/FORCE_COLOR (medium). Built-ins are applied after user env; `env: {FORCE_COLOR: ""}` still yields FORCE_COLOR=0 in the child. User env should win.

4. FORCE_COLOR=0 default forces ANSI on for Rich/Typer (medium). Rich treats any set FORCE_COLOR as force_terminal=true, and NO_COLOR removes colors but not bold/dim attributes, so Rich CLIs emit ANSI escapes under tryscript defaults. Suggested: do not set FORCE_COLOR at all (NO_COLOR is the standard signal), and document TERM=dumb as the recommended pinned env for Rich/Typer CLIs (gives ANSI-free deterministic 80-column output).

5. Multiple `$` commands in one console block are silently merged (medium). They execute and rewrite as one concatenated command line ("$ echo one > f1.txt echo two > f2.txt ls"), corrupting the file on --expand. Either support sequential commands per block or fail with a clear parse error.

6. --update writes trailing-whitespace-padded lines; --expand trims (low). Comparison trims line ends on both sides, so the padding is dead weight that trips git diff --check. Normalize on write in both paths.

7. --update clobbers elision patterns in changed blocks (low/feature). Regenerating a file whose new output still matches an existing pattern replaces the pattern with the literal capture, so regen loops need a post-processing script. A pattern-preserving update (re-elide when the previous pattern still matches the new text) would make `--update` safe for pattern-heavy files.

8. Cosmetic: a successful `--expand` run still ends with "N unknown wildcard(s) found ... Use --expand to fill them in", describing the pre-expansion state.

What worked well: markdown test files read as documentation; sandbox + `before:` fixture setup; trailing-whitespace-tolerant matching; `path:` frontmatter for venv binaries; custom regex patterns.
