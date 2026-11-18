---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: A Pull Request Text the Server Would Not Render

The Markdown route renders each pull request text in the server’s Markdown child under a
deadline (`pull_markdown.py` in the GitHub plugin), and refuses a text that runs past it
with `422` and the code `render_deadline`, as `tests/test_github_pulls.py` pins in
`tests/fixtures/github-pull-text-refusal.json`.

This browserless session runs the production `createPullController` of
`builtin_plugins/github/pull-page.js` on the pull route’s recorded answer for pull
request 7, with the description refused and a comment rendered.
`asked` is each part the page asked the route for, once: the description asked again on
the same record is not asked of the server again.
`told` is what the page’s glue is told: the refused description is unavailable with the
line `refusedTextNote` says for it, which the glue puts under the text’s plain text as a
warning notice; the comment renders; and a part the record lacks is asked for and
nothing is said.
`notes` is that line for each code the route answers, and nothing for an
answer that needs no word, such as a part the record lacks or a render that arrived.

```console
$ node tests/dom/github-pull-text-refusal-session.js
{
  "asked": [
    "body",
    "issue_comment/3341937855",
    "issue_comment/1"
  ],
  "told": [
    {
      "part": "body",
      "unavailable": true,
      "text": "The app counts to one.\r\n\r\nThis t",
      "note": "This text took longer than 0.2 seconds to render, so it is shown as plain text."
    },
    {
      "part": "issue_comment/3341937855",
      "rendered": true
    }
  ],
  "notes": {
    "render_deadline": "This text took longer than 5 seconds to render, so it is shown as plain text.",
    "renderer_exited": "The renderer stopped while rendering this text, so it is shown as plain text.",
    "renderer_unavailable": "The renderer could not start, so this text is shown as plain text. Reload to try again.",
    "renderer_busy": "The renderer is busy with other texts, so this text is shown as plain text. Reload to try again.",
    "render_failed": "This text could not be rendered, so it is shown as plain text.",
    "recorded": "This text took longer than 0.2 seconds to render, so it is shown as plain text.",
    "unknown_part": null,
    "ok": null
  }
}
? 0
```
