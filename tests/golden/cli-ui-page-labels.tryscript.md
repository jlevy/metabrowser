---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Navigation Page Labels

The shell gives the browser tab its page title and sends a compact label to the native
host when the current pane shows an identity that matches the address.
This session runs the production route readers and label publisher over the pane’s
committed headings. It covers a retained file while a different address loads, same-page
pull request tabs, traversal between equal URLs, stack and commit details, list filters,
and an ordinary browser without a native bridge.

```console
$ node tests/dom/page-labels-session.js
{"name":"direct file link and selected lines","browser":"index.md","messages":1,"native":{"title":"index.md","icon":"fileText","context":"src · Lines 12–18"}}
{"name":"address changes while the previous file is retained","browser":"index.md","messages":1,"native":null}
{"name":"new file commits","browser":"index.md","messages":2,"native":{"title":"index.md","icon":"fileText","context":"docs"}}
{"name":"addressed file view","browser":"index.md","messages":3,"native":{"title":"index.md","icon":"fileText","context":"docs · Table"}}
{"name":"served root preserves its distinct folder glyph","browser":"demo","messages":4,"native":{"title":"demo","icon":"folderDot","context":null}}
{"name":"PR commits with its draft icon and changed file","browser":"Refine navigation","messages":5,"native":{"title":"Refine navigation","icon":"gitPullRequestDraft","context":"#23 · Changes · src/index.md"}}
{"name":"another tab uses the same PR heading","browser":"Refine navigation","messages":6,"native":{"title":"Refine navigation","icon":"gitPullRequestDraft","context":"#23 · Conversation"}}
{"name":"traversal to an equal URL reports the new entry","browser":"Refine navigation","messages":7,"native":{"title":"Refine navigation","icon":"gitPullRequestDraft","context":"#23 · Conversation"}}
{"name":"redundant address notification is silent","browser":"Refine navigation","messages":7,"native":{"title":"Refine navigation","icon":"gitPullRequestDraft","context":"#23 · Conversation"}}
{"name":"stack overview and selected view","browser":"Stack Overview","messages":8,"native":{"title":"Stack Overview","icon":"layers","context":"#23 · Guided Review"}}
{"name":"commit subject and change context","browser":"feat: share page labels","messages":9,"native":{"title":"feat: share page labels","icon":"gitCommit","context":"abc1234 · src/index.md"}}
{"name":"pulls overview and filter","browser":"Pull requests","messages":10,"native":{"title":"Pull requests","icon":"list","context":"Closed"}}
{"name":"neutral Commits entry owns the preview","browser":"Commits","messages":11,"native":{"title":"Commits","icon":"gitCommit","context":null}}
{"name":"ordinary browser updates its title without posting","browser":"index.md","messages":11,"native":null}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
