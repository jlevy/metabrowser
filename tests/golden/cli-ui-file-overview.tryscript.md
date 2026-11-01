---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: File Overview for each answer the rollup can give

File Overview’s totals and type distribution both read one rollup.
This session mounts the production panel and answers its rollup each way the route can:
refused, failed and retried, finished without the folder, stopped at the cap, failed
index, a running scan, and complete.
Each step prints what is on screen.
Only a running scan may show a skeleton: every other answer finishes both bodies, and a
control changed after a failure keeps the failure’s message.
On an ordinary folder the distribution’s caption names the tally row its shares are of
and how much that is, and follows Show ignored and the measure.

```console
$ node tests/dom/file-overview-session.js
{
  "a refused rollup finishes both bodies": {
    "refused": {
      "totals": "nothing",
      "distribution": "Could not load file types.",
      "retry": false
    },
    "afterControls": {
      "totals": "nothing",
      "distribution": "Could not load file types.",
      "retry": false
    }
  },
  "a failed request retries into the complete page": {
    "failed": {
      "totals": "nothing",
      "distribution": "Could not load file types. Retry",
      "retry": true
    },
    "retried": {
      "totals": "Files 2 files Ignored 1 files Total 3 files",
      "distribution": "Share of Total (3 files) Code Python 3 files 100%",
      "retry": false
    }
  },
  "an index that finished without the folder says so": {
    "totals": "nothing",
    "distribution": "This folder is not in the current file index.",
    "retry": false
  },
  "an index stopped at its cap says so": {
    "totals": "nothing",
    "distribution": "This folder is not in the current file index.",
    "retry": false
  },
  "a failed index says so": {
    "totals": "nothing",
    "distribution": "Indexing failed; no file summary is available.",
    "retry": false
  },
  "a running scan keeps its skeletons until a refresh fails": {
    "scanning": {
      "totals": "skeleton",
      "distribution": "skeleton",
      "retry": false
    },
    "failedRefresh": {
      "totals": "nothing",
      "distribution": "Could not load file types. Retry",
      "retry": true
    }
  },
  "totals the envelope carries stay beside a failure": {
    "totals": "Files 2 files Ignored 1 files Total 3 files",
    "distribution": "Could not load file types.",
    "retry": false
  },
  "an ordinary folder": {
    "complete": {
      "totals": "Files 2 files Ignored 1 files Total 3 files",
      "distribution": "Share of Total (3 files) Code Python 3 files 100%",
      "retry": false
    },
    "filesOnly": {
      "totals": "Files 2 files Ignored 1 files Total 3 files",
      "distribution": "Share of Files (2 files) Code Python 2 files 100%",
      "retry": false
    },
    "bytes": {
      "totals": "Files 2,000 B Ignored 1,000 B Total 3,000 B",
      "distribution": "Share of Files (2,000 B) Code Python 2,000 B 100%",
      "retry": false
    },
    "allBytes": {
      "totals": "Files 2,000 B Ignored 1,000 B Total 3,000 B",
      "distribution": "Share of Total (3,000 B) Code Python 3,000 B 100%",
      "retry": false
    }
  }
}
? 0
```
