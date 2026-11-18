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
A later answer that the scan is running brings both skeletons back, whatever ended them.
A hidden folder or a symbolic link to a folder, which the inventory leaves out, asks for
no rollup and says why it has no totals, and the folder header shows no tally for it.
The file list’s note on a capped index names the limit once.
On an ordinary folder the distribution’s caption names the tally row its shares are of
and how much that is, and follows Show ignored and the measure.
The caption is for screen readers only, so each step prints it apart from the visible
text. A legend names the five largest file-type families above the 1% share floor, then
Other for the rest; the table of every group, family, and type waits behind Details.
On a folder of many types, Details starts closed, opens to the full table, stays open
through a measure change, Show ignored, a refresh, and a rescan, closes back to the
compact summary, and starts closed again on the next mount.
Pointing at a legend entry marks every mark of its family on screen: its segment in each
tally row that has one, Files, Ignored, and Total, and, while Details is open, its own
row’s bar there, not its extensions’ rows.
Pointing at a segment marks that segment alone, the one value it is.
Either way the family’s legend entry is marked too.
There is one tooltip, anchored on the handle the pointer is on, the entry or the
segment: on the segment it names the family and its counts; on the entry, which shows
the name, the counts alone of the family’s segment in the tally row the legend’s shares
are of, Total with Show ignored on and Files with it off.
Other draws nothing.
Details opened or closed under a pointer still on an entry marks or unmarks its row.
When the folder’s sums redraw the bars under the pointer, an entry keeps its hover.
Show ignored, a rescan that empties the legend, a refresh, or the section’s disposal
under the pointer puts it away, and the browser’s entering the rebuilt entry brings it
back.

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
      "distribution": "Python 100% Details",
      "caption": "Share of Total (3 files)",
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
  "a capped index says its summary is partial": {
    "totals": "Files 2 files Ignored 1 files Total 3 files",
    "distribution": "Python 100% Details Summary is partial: 3 files indexed at the 3-file cap.",
    "caption": "Share of Total (3 files)",
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
  "a refresh failing during a scan, then Retry brings both skeletons back": {
    "stopped": {
      "totals": "nothing",
      "distribution": "Could not load file types. Retry",
      "retry": true
    },
    "resumed": {
      "totals": "skeleton",
      "distribution": "skeleton",
      "retry": false
    }
  },
  "a refresh failing during a scan, then a change brings both skeletons back": {
    "stopped": {
      "totals": "nothing",
      "distribution": "Could not load file types. Retry",
      "retry": true
    },
    "resumed": {
      "totals": "skeleton",
      "distribution": "skeleton",
      "retry": false
    }
  },
  "an index that finished without the folder, then a rescan brings both skeletons back": {
    "stopped": {
      "totals": "nothing",
      "distribution": "This folder is not in the current file index.",
      "retry": false
    },
    "resumed": {
      "totals": "skeleton",
      "distribution": "skeleton",
      "retry": false
    }
  },
  "a failed first request, then a change brings both skeletons back": {
    "stopped": {
      "totals": "nothing",
      "distribution": "Could not load file types. Retry",
      "retry": true
    },
    "resumed": {
      "totals": "skeleton",
      "distribution": "skeleton",
      "retry": false
    }
  },
  "a failed first request, then Retry brings both skeletons back": {
    "stopped": {
      "totals": "nothing",
      "distribution": "Could not load file types. Retry",
      "retry": true
    },
    "resumed": {
      "totals": "skeleton",
      "distribution": "skeleton",
      "retry": false
    }
  },
  "a resumed scan still finishes": {
    "resumed": {
      "totals": "skeleton",
      "distribution": "skeleton",
      "retry": false
    },
    "finished": {
      "totals": "nothing",
      "distribution": "This folder is not in the current file index.",
      "retry": false
    }
  },
  "a rescan leaves the totals the envelope carries": {
    "totals": "Files 2 files Ignored 1 files Total 3 files",
    "distribution": "skeleton",
    "retry": false
  },
  "a hidden folder says why it has no totals": {
    "totals": "nothing",
    "distribution": "Metabrowser does not index hidden folders, so this one has no file totals.",
    "retry": false
  },
  "a symlink folder says why it has no totals": {
    "totals": "nothing",
    "distribution": "Metabrowser does not follow symbolic links when it indexes, so this folder has no file totals here.",
    "retry": false
  },
  "totals the envelope carries stay beside a failure": {
    "totals": "Files 2 files Ignored 1 files Total 3 files",
    "distribution": "Could not load file types.",
    "retry": false
  },
  "an ordinary folder": {
    "complete": {
      "totals": "Files 2 files Ignored 1 files Total 3 files",
      "distribution": "Python 100% Details",
      "caption": "Share of Total (3 files)",
      "retry": false
    },
    "filesOnly": {
      "totals": "Files 2 files Ignored 1 files Total 3 files",
      "distribution": "Python 100% Details",
      "caption": "Share of Files (2 files)",
      "retry": false
    },
    "bytes": {
      "totals": "Files 2,000 B Ignored 1,000 B Total 3,000 B",
      "distribution": "Python 100% Details",
      "caption": "Share of Files (2,000 B)",
      "retry": false
    },
    "allBytes": {
      "totals": "Files 2,000 B Ignored 1,000 B Total 3,000 B",
      "distribution": "Python 100% Details",
      "caption": "Share of Total (3,000 B)",
      "retry": false
    }
  },
  "the compact summary and its Details": {
    "closed": {
      "details": "false",
      "caption": "Share of Total (1,000 files)",
      "distribution": "JSON 24% YAML 17% Markdown 15% TypeScript 6% Python 3.3% Other 34.7% Details",
      "step": "mounted"
    },
    "opened": {
      "details": "true",
      "caption": "Share of Total (1,000 files)",
      "distribution": "JSON 24% YAML 17% Markdown 15% TypeScript 6% Python 3.3% Other 34.7% Details Documentation Markdown 150 files 15% Code TypeScript 60 files 6% Python 33 files 3.3% JavaScript 25 files 2.5% 1 more 8 files 0.8% Data JSON 240 files 24% YAML 170 files 17% Other Other types 253 files 25.3% No extension 40 files 4% Log files 21 files 2.1%",
      "step": "Details opened"
    },
    "bySize": {
      "details": "true",
      "caption": "Share of Total (1,000 B)",
      "distribution": "Markdown 30% TypeScript 20% Python 15% JavaScript 12% JSON 10% Other 13% Details Documentation Markdown 300 B 30% Code TypeScript 200 B 20% Python 150 B 15% JavaScript 120 B 12% 1 more 5 B 0.5% Data JSON 100 B 10% YAML 50 B 5% Other Other types 30 B 3% Log files 25 B 2.5% No extension 20 B 2%",
      "step": "measure changed to bytes"
    },
    "unignored": {
      "details": "true",
      "caption": "Share of Files (920 B)",
      "distribution": "Markdown 32.6% TypeScript 21.7% Python 16.3% JavaScript 13% YAML 5.4% Other 10.9% Details Documentation Markdown 300 B 32.6% Code TypeScript 200 B 21.7% Python 150 B 16.3% JavaScript 120 B 13% 1 more 5 B 0.5% Data YAML 50 B 5.4% JSON 20 B 2.2% Other Other types 30 B 3.3% Log files 25 B 2.7% No extension 20 B 2.2%",
      "step": "Show ignored turned off"
    },
    "refreshed": {
      "details": "true",
      "caption": "Share of Files (920 B)",
      "distribution": "Markdown 32.6% TypeScript 21.7% Python 16.3% JavaScript 13% YAML 5.4% Other 10.9% Details Documentation Markdown 300 B 32.6% Code TypeScript 200 B 21.7% Python 150 B 16.3% JavaScript 120 B 13% 1 more 5 B 0.5% Data YAML 50 B 5.4% JSON 20 B 2.2% Other Other types 30 B 3.3% Log files 25 B 2.7% No extension 20 B 2.2%",
      "step": "rollup refreshed"
    },
    "rescanning": "skeleton",
    "rescanned": {
      "details": "true",
      "caption": "Share of Files (920 B)",
      "distribution": "Markdown 32.6% TypeScript 21.7% Python 16.3% JavaScript 13% YAML 5.4% Other 10.9% Details Documentation Markdown 300 B 32.6% Code TypeScript 200 B 21.7% Python 150 B 16.3% JavaScript 120 B 13% 1 more 5 B 0.5% Data YAML 50 B 5.4% JSON 20 B 2.2% Other Other types 30 B 3.3% Log files 25 B 2.7% No extension 20 B 2.2%",
      "step": "a rescan answered"
    },
    "reclosed": {
      "details": "false",
      "caption": "Share of Files (920 B)",
      "distribution": "Markdown 32.6% TypeScript 21.7% Python 16.3% JavaScript 13% YAML 5.4% Other 10.9% Details",
      "step": "Details closed"
    },
    "disposed, then mounted again": {
      "details": "false"
    }
  },
  "a legend entry hovers its family's marks": {
    "at rest": {
      "marked": [],
      "tooltip": null,
      "anchoredOn": null
    },
    "pointer on the JSON entry, Show ignored on": {
      "marked": [
        "Files family:json",
        "Ignored family:json",
        "Total family:json",
        "legend family:json"
      ],
      "tooltip": "240 files · 100 B",
      "anchoredOn": "legend family:json"
    },
    "left the entry": {
      "marked": [],
      "tooltip": null,
      "anchoredOn": null
    },
    "pointer on the Total row's JSON segment": {
      "marked": [
        "Total family:json",
        "legend family:json"
      ],
      "tooltip": "JSON 240 files · 100 B",
      "anchoredOn": "Total family:json"
    },
    "pointer on Other": {
      "marked": [],
      "tooltip": null,
      "anchoredOn": null
    },
    "Details opened under the pointer on the JSON entry": {
      "marked": [
        "Files family:json",
        "Ignored family:json",
        "Total family:json",
        "legend family:json",
        "Details family:json"
      ],
      "tooltip": "240 files · 100 B",
      "anchoredOn": "legend family:json"
    },
    "pointer on the Total row's JSON segment, Details open": {
      "marked": [
        "Total family:json",
        "legend family:json"
      ],
      "tooltip": "JSON 240 files · 100 B",
      "anchoredOn": "Total family:json"
    },
    "Details closed under the pointer on the JSON entry": {
      "marked": [
        "Files family:json",
        "Ignored family:json",
        "Total family:json",
        "legend family:json"
      ],
      "tooltip": "240 files · 100 B",
      "anchoredOn": "legend family:json"
    },
    "Show ignored turned off under the pointer": {
      "marked": [],
      "tooltip": null,
      "anchoredOn": null
    },
    "pointer on the Markdown entry, Show ignored off": {
      "marked": [
        "Files family:markdown",
        "Total family:markdown",
        "legend family:markdown"
      ],
      "tooltip": "150 files · 300 B",
      "anchoredOn": "legend family:markdown"
    },
    "the folder's sums redrew the bars under the pointer": {
      "marked": [
        "Files family:markdown",
        "Total family:markdown",
        "legend family:markdown"
      ],
      "tooltip": "150 files · 300 B",
      "anchoredOn": "legend family:markdown"
    },
    "a rescan emptied the legend under the pointer": {
      "marked": [],
      "tooltip": null,
      "anchoredOn": null
    },
    "the rollup refreshed under the pointer": {
      "marked": [],
      "tooltip": null,
      "anchoredOn": null
    },
    "the browser entered the rebuilt entry": {
      "marked": [
        "Files family:markdown",
        "Total family:markdown",
        "legend family:markdown"
      ],
      "tooltip": "150 files · 300 B",
      "anchoredOn": "legend family:markdown"
    },
    "the section disposed under the pointer": {
      "marked": [],
      "tooltip": null,
      "anchoredOn": null
    }
  },
  "the folder header's tally": {
    "still scanning": {
      "skeleton": true,
      "text": "· ·"
    },
    "complete": {
      "skeleton": false,
      "text": "3000 B · 3 files · 3h"
    },
    "hidden": {
      "skeleton": false,
      "text": ""
    },
    "symlink": {
      "skeleton": false,
      "text": ""
    }
  },
  "the file list's note on a capped index": {
    "3 files": "File list incomplete. Metabrowser stopped after 3 files, so some files and folders are not shown.",
    "1 file": "File list incomplete. Metabrowser stopped after 1 file, so some files and folders are not shown.",
    "no limit named": "File list incomplete. Metabrowser reached its file limit, so some files and folders are not shown."
  }
}
? 0
```
