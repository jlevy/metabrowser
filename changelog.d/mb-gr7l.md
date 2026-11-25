- Make every notice, empty state, and error the app shows say what happened in one
  statement, with at most one remedy.
  Commit IDs, internal paths, exception text, HTTP statuses, and internal mechanics no
  longer appear in them, in the shell, the built-in plugins, or the server answers the
  pages show; the detail stays in each route’s JSON, as `detail` and `code`, for
  `metab --api`, and in the browser console.
  [Reader Messages](docs/design-system-messages.md) sets the rules, and
  `tests/test_reader_messages.py` checks the browser scripts and the server’s answers
  against them.

- Stop showing a commit ID in the source freshness offer to switch to a branch that has
  moved, and in the moved and gone lines of its tooltip; the route still reports the
  commit.

- Drop the detail block under a Markdown document that could not be rendered; the notice
  says what happened and points to the Source tab.

- Answer a capability the opened folder lacks, and a Git too old for a checkout’s
  branches and tags, with a reader sentence as `error`; what was missing, and the Git
  release needed, move to `detail`.
