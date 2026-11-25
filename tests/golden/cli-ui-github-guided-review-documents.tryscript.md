---
cwd: ../..
sandbox: false
---
# Guided Review documents

A file a step names alone that the guided route answers `rendered`, a file the rendered
route renders by its own rule, is the diff plugin’s own view of it, read from the
comparison route’s one-file answer by its path: a Markdown file is drawn with the
options the Docs tab draws with, and a YAML file with those Changes draws with.
Its Rendered is asked of the rendered route by the manifest ID that answer carries.
A step that cites no such file never loads the rendered layer, and a document loads no
File type filter and asks for no type counts.
A range of the same file, a file the route answers with its hunks, and a file past the
step’s budget draw as before.
Moving to another step disposes every view the step drew; a document’s read still on its
way when the reader moves on is aborted, and its late answer draws nothing.
A document shows its progress mark while its read is on its way, and not once it is
drawn. A step read at another merge base or another head than the page’s says the file’s
diff is unavailable, and a comparison that names no rendered route draws the document
without the rendered layer.
A document the view could not draw, because the view threw or its one-file read failed,
shows the guide’s bar for it, with its name and its Open full diff, above the view’s
notice, and the page’s end removes the notice.
A stale guide’s changed document says so above the document’s own view, and the page’s
end disposes it. The Docs tab draws its documents with every option a step’s Markdown
document has, and adds only the sentence it says when it has no document; Changes draws
its files with exactly the options a step’s YAML document has.

```console
$ node tests/dom/github-guided-review-documents-behavior.js
[
  "a step of patches alone: src/app.py: patch; the rendered layer loaded false",
  "step 1 draws: docs/guide.md: document | docs/guide.md: patch | src/app.py: patch | config/settings.yaml: document | notes.md: says This file's diff is too large to show in this step.",
  "its one-file reads: pull-comparison file=docs/guide.md, pull-comparison file=config/settings.yaml",
  "its documents load the rendered layer true, the File type filter false",
  "its documents' other reads: none",
  "a Markdown document's view is drawn with: changedFiles: object, layout: \"unified\", markdownHoldMs: 200, markdownTargets: function, markdownViews: object, renderMarkdown: function, show: \"current\", showPreference: \"github.docs.show\", showSummary: false, summaryHost: null, unfold: true, viewFile: null",
  "a YAML document's view is drawn with: changedFiles: object, markdownHoldMs: 200, markdownTargets: function, markdownViews: object, renderMarkdown: function, showSummary: false, summaryHost: null, viewFile: null",
  "its Rendered is asked of: pull-rendered-diff file=id-docs/guide.md",
  "step 2 disposes step 1's: 2 of 2 documents, 2 of 2 patches",
  "step 2 draws, its read on its way: a document still loading",
  "step 3 before it answered: read aborted true; views drawn after 0; src/app.py: patch",
  "a held document: progress marks 1 while its read is held, 0 once drawn; docs/held.md: document",
  "a step read at another merge base: docs/guide.md: says This file's diff is unavailable.",
  "a step read at another head: docs/guide.md: says This file's diff is unavailable.",
  "a comparison with no rendered route: docs/guide.md: document, its rendered layer absent",
  "documents that could not be drawn: docs/threw.md: document says Could not load this diff. Reload the page to try again. (its bar opens /pull/7/files/docs/threw.md) | docs/refused.md: document says Could not load this diff. Reload the page to try again. (its bar opens /pull/7/files/docs/refused.md)",
  "their failures are logged: 2",
  "the page ends: 0 of 2 notices left",
  "a changed document of a stale guide: docs/guide.md: document (This file changed after the guide was written.)",
  "the page ends: its document disposed true",
  "Docs has, and a step's docs/guide.md has not: emptyText",
  "a step's docs/guide.md has, and Docs has not: nothing",
  "Changes has, and a step's config/settings.yaml has not: nothing",
  "a step's config/settings.yaml has, and Changes has not: nothing"
]
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
