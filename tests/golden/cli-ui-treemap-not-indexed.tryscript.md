---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Treemap Explains Folders Excluded From the Index

The production Treemap renderer uses the folder envelope’s reason immediately.
Hidden folders and paths through symbolic links ask for no rollup, controls,
subscriptions, observers or timers.
Parent navigation keeps Treemap selected, and repeated mounts and disposal release their
listeners.

```console
$ node tests/dom/treemap-not-indexed-session.js
{
  "folders": [
    {
      "reason": "hidden",
      "text": "Files ↑ / Metabrowser does not index hidden folders, so this one has no file totals.",
      "parent": [
        {
          "path": ""
        },
        {
          "viewId": "treemap"
        }
      ]
    },
    {
      "reason": "symlink",
      "text": "Files ↑ link/ Metabrowser does not follow symbolic links when it indexes, so this folder has no file totals here.",
      "parent": [
        {
          "path": "link"
        },
        {
          "viewId": "treemap"
        }
      ]
    }
  ],
  "repeatMounts": "clean",
  "rollupResources": 0
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
