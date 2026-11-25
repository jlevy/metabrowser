# Reader Messages

A **reader message** is any sentence the app writes to tell a reader about the state of
what they are looking at, rather than showing them the thing itself: an empty list, a
load in progress, a partial or stale view, a failure, a refusal, or an action that
finished.
This guide says what such a message may say, how it looks, and where everything
it leaves out goes instead.

The rule is short: **say what happened in the reader’s terms, in one statement, and
offer at most one simple remedy the reader can act on.** Nothing about how Metabrowser
found out belongs in it.

The reason is what a message is for.
A reader who meets commit IDs, merge-base arithmetic, or an exception’s text in a notice
cannot act on any of it, and has to read all of it to learn that there is nothing to do.
A page that answers a minor condition with a paragraph of diagnostics also makes the
condition look like a breakdown, when the page is usually still fine.
Agents and developers do need the detail, so it stays, in the route’s JSON and the logs
([Where the Detail Goes](#where-the-detail-goes)), not on the page.

It covers every surface Metabrowser ships: the browser shell and the built-in plugins,
the server’s answers that pages show, and the macOS app’s alerts and status views.

This guide sits beside the [design system](design-system.md), whose
[Notices](design-system.md#notices) section owns the notice box’s look, and
`tests/test_reader_messages.py` enforces what a machine can hold of it
([The Check](#the-check)).

## Kinds of Message

| Kind | Says | Example | Box and role |
| --- | --- | --- | --- |
| Empty state | What is absent | “No files were modified during the selected time range.” | `.preview-empty`, `.recent-empty`, `.git-panel-empty`; no severity |
| Loading | What is coming | “Loading charts…” | Inline text, only once [Motion](design-system.md#motion) allows any |
| Notice or warning | The content is partial, stale, or degraded, and fine as far as it goes | “Recent files may be out of date. Change the filter or refresh to try again.” | `.notice[data-severity="warning"]`, `role="status"` |
| Error | Something could not be done at all | “Could not load this folder. Collapse and reopen it to try again.” | `.notice[data-severity="error"]`, `.nav-error`, or the preview pane’s `.preview-error`, `role="alert"` |
| Refusal | Metabrowser declines by design, and the content is safe | “This document took too long to render, so its source is shown.” | A warning, since nothing failed |
| Confirmation | An action finished | “Link copied” | Brief status text, `role="status"` |

A tooltip on a control that failed is the same message in a smaller place: it follows
these rules too, and it adds no more than the visible text would.

## What a Message Contains

**One statement of what happened, from the reader’s side.** Say what the reader can or
cannot see or do: “Changes are not shown,” “This file is only partly loaded,” “Could not
reach GitHub.” Name things by the words the reader already uses here: files, folders,
branches, tags, commits, pull requests, the checkout, GitHub.

**At most one remedy, and only a real one.** A remedy is something the reader can do now
that has a fair chance of working: reload, try again, open another tab, ask the author.
Prefer a control in the message to a sentence about one, as
[State Progress Once](design-system.md#state-progress-once) requires of a notice that
content is missing. When nothing the reader does would help, give no remedy rather than
invent one.

**A cause only when it changes what the reader does.** “Could not reach GitHub” already
implies the remedy; “GitHub refused the request because the token’s scopes lack
`read:org`” is a diagnosis, and belongs to the detail.

## What a Message Never Shows

- **Commit IDs or lists of commits.** Name the branch, or say “a newer commit” or “an
  earlier commit.” A commit’s ID belongs on the row or header that identifies it
  ([Short Commit IDs](design-system.md#short-commit-ids)), never in a sentence about a
  state.
- **Internal file paths**: specs, plans, source files, and cache or staging directories.
  The reader’s own file may be named where it says which one failed.
- **Exception text or stack traces**: a caught error’s `message` or `stack`, a Python
  exception’s `str()`, its type name, or an operating-system error’s `strerror`.
- **Schema or validation locations**: field paths such as `manifest.files[3].id`, schema
  versions, and a validator’s own wording.
- **Internal mechanics**: merge bases, rebases, and force pushes as explanations; caches
  and their contents; workers, child processes, reader pools, and queues; deadlines and
  budgets, in bytes or seconds; decompression; log segments, envelopes, protocols, and
  route names.
- **HTTP statuses and internal codes**, such as “(HTTP 502)” or `object_unavailable`.

## Tone

Calm and plain, and never blaming.

- Start a failure with “Could not,” not “Failed to,” “Error:,” or “Oops.”
- No exclamation marks, “unfortunately,” or “please.”
- Name the thing, not the reader: “This link’s address is not a commit,” not “You
  entered an invalid commit.”
- Use the lowest severity that is true.
  A partial, stale, or capped view is a warning; an error is only for something that
  could not be done at all ([Notices](design-system.md#notices)).

## Length and Punctuation

- **The statement and its remedy, and no more sentences.** `MAX_SENTENCES` in
  `tests/test_reader_messages.py` holds the limit for any one string the code writes; a
  message assembled from several strings is held to it in review.
- **Every sentence ends with a period**, a failure’s bold title included.
  Never end a statement with a colon that introduces detail.
  A short status on a control, such as “Link copied” or “Copy failed,” is a label rather
  than a sentence, and takes none.
- **A loading line ends with an ellipsis character**, “…”, not three periods.
- **Typographic quotes and apostrophes**, as the rest of the interface’s copy uses.

## Layout

- **A message is one paragraph**, or a bold title and one line beneath it, as
  `previewErrorHtml` in `static/app.js` draws a failed preview.
  It is never a bulleted or numbered list, and never a stack of paragraphs.
- **It uses the notice primitive and the design tokens only**: `.notice` with a
  `data-severity`, whose fill, border, and type [Notices](design-system.md#notices)
  owns, and whose role `tests/test_plugin_design_consistency.py` checks.
  The preview pane’s failure is the one other box, `.preview-empty.preview-error` with
  `role="alert"`, which `previewErrorHtml` draws.
- **One condition, one message.** When one view has several things to report, say the
  one that matters most to the reader.

## Degrade Gracefully

A condition worth a message is rarely a reason to stop showing the page.

- **Keep the page usable.** Show what can still be shown: a stale guide keeps its steps,
  a partly loaded file shows what loaded, a failed refresh keeps the last good copy.
- **Mark only what is affected.** Put a quiet mark on the affected step, row, or file
  rather than a banner over the page.
- **Recover by itself where it can**, as the navigation tree retries a failed folder
  when the connection returns, and say so only when the reader would otherwise wait.

## Where the Detail Goes

Everything a message leaves out stays reachable for the people and agents who need it.

- **The route’s JSON.** A route that answers with a reader message keeps the detail
  beside it, in fields such as `detail`, `code`, and the commits and paths involved.
  The page shows only the reader field.
  The [parity rules](../AGENTS.md#cli-and-functional-ui-parity) require every route the
  page uses to be reachable through `metab --api`, so an agent reads the same answer in
  full.
- **The console and the logs.** The browser writes a caught exception to
  `console.error`; the server records its exceptions in the event log
  ([Real-Time Debugging](realtime-debugging.md)).
- **Diagnostic views show recorded text as content.** The event log’s views and a
  database’s Info view display what a file or log holds, and their rows are that
  content. Their own notices about it still follow this guide.

The command line’s own errors are terminal output for a developer and are outside this
guide; `metab` may print a path or an exception there.

## The Check

`tests/test_reader_messages.py` holds the parts of this guide a machine can.
It reads every string and template in the shipped browser scripts, `static/*.js` and the
built-in plugins’, through `tests/dom/reader-message-literals.mjs`, which parses them
with the TypeScript compiler’s parser and leaves out what no reader sees: console
arguments, a built-in `Error`’s arguments, module specifiers, property keys, and
comparison operands.
Each rule fails on planted violations in the same module:

- internal mechanics in a sentence: every term of the list above, which `MECHANICS`
  holds;
- an internal path, such as a `.md` or `.py` file, in a sentence;
- an HTTP status in a sentence;
- a commit ID interpolated into a sentence (a `sha` or `oid`, a name ending in one, or
  the first characters of anything), or a `shortCommit` call in a notice’s builder;
- a list built inside a notice’s builder, or written in a notice’s markup;
- a caught exception’s `message`, `stack`, or `String()` read anywhere but a console
  call, or the exception itself written into a template, a `+`, or a property;
- a failure’s detail, status, or code appended to a sentence, as `: ${error}` or
  `(${response.status})`;
- an exclamation mark, or a “please,” “unfortunately,” or “oops,” or a failure that
  opens with “Failed to” or “Error:”;
- a string with more than `MAX_SENTENCES` sentences.

On the server it parses every module under `src/metabrowser/` except the command line’s.
It fails when an answer’s reader field (`error`, `message`, or `summary`), or a
Metabrowser error that becomes one, carries the text or type name of a caught exception
whose text is not reader copy: one Metabrowser did not define, or one of its errors with
a `reader_message`, whose `str()` is detail.
It follows that text through a local, an assignment to a reader field, a traceback, and
a helper in the same module that writes the field.
It also holds the literal sentences of those fields, and every error’s `reader_message`,
to the text rules above: mechanics, internal path, HTTP status, commit ID, appended
detail, tone, and length.

Its allowlists are explicit, keyed by file, rule, and function, each entry with its
reason, and an entry whose violation is gone fails the check until it is removed.

What it cannot see is review’s: a message assembled from several strings, whether a
remedy is real, an exception’s text read under a name the check does not know as one,
and the rest of tone.
It does not read the macOS app’s Swift yet, so review holds the app’s alerts and status
views to this guide.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
