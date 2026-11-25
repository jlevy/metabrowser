---
cwd: ../..
sandbox: false
---
# Guided Review documents

A file a step names alone, of a format the diff view renders (Markdown, YAML, JSON), is
the diff plugin’s own view of it, read from the comparison route’s one-file answer by
its path and drawn with the options the Docs tab draws with, so its Rendered is asked of
the rendered route by the manifest ID that answer carries.
A range of the same file, a file of another format named alone, and a file past the
step’s budget draw as before.
Moving to another step disposes every view the step drew; a document’s read still on its
way when the reader moves on is aborted, and its late answer draws nothing.
A step read at another comparison than the page’s, and a comparison that names no
rendered route, draw the document’s patch.
A stale guide’s changed document says so above the document’s own view, and the page’s
end disposes it. The Docs tab draws its documents with every option a step’s document
has, and adds only the sentence it says when it has no document.

```console
$ node tests/dom/github-guided-review-documents-behavior.js
[
  "step 1 draws: docs/guide.md: document | docs/guide.md: patch | src/app.py: patch | config/settings.yaml: document | notes.md: says This file's diff is too large to show in this step.",
  "its one-file reads: pull-comparison file=docs/guide.md, pull-comparison file=config/settings.yaml",
  "a document's view is drawn with: changedFiles: object, layout: \"unified\", markdownHoldMs: 200, markdownTargets: function, markdownViews: object, renderMarkdown: function, show: \"current\", showPreference: \"github.docs.show\", showSummary: false, summaryHost: null, unfold: true, viewFile: null",
  "its Rendered is asked of: pull-rendered-diff file=id-docs/guide.md",
  "step 2 disposes step 1's: 2 of 2 documents, 2 of 2 patches",
  "step 2 draws, its read on its way: a document still loading: document",
  "step 3 before it answered: read aborted true; views drawn after 0; src/app.py: patch",
  "a step read at another comparison: docs/guide.md: patch",
  "a comparison with no rendered route: docs/guide.md: patch",
  "a changed document of a stale guide: docs/guide.md: document (This file changed after the guide was written.)",
  "the page ends: its document disposed true",
  "Docs has, and a step's document has not: emptyText",
  "a step's document has, and Docs has not: nothing"
]
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
