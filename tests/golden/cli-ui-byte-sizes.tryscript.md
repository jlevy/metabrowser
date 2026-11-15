---
cwd: ../..
sandbox: false
---
# Golden Test: How a Byte Count Reads

Every size a reader sees is written by one formatter, `formatBytes` in
`static/formatters.js`. The shell’s `formatSize` in `static/app.js`, behind the Files
tree rows, the Files totals line, and the binary preview, and the plugin SDK’s
`mb.formatSize` both hand their count to it.

This browserless session runs the real formatter runtime and plugin SDK, with the
shell’s `formatSize` extracted verbatim from `static/app.js`, and records how each unit
boundary reads: the last count of one unit and the first of the next.
The transcript pins these behaviors:

- Units step by 1024: B, KB, MB, GB, then TB.
- A count under 1024 reads in whole bytes; every larger one reads to one decimal.
- A count just short of the next unit reads as 1024.0 of its own.
- A gigabyte or more reads in GB, not MB: 10.1 billion bytes reads “9.4 GB”.
- The shell and the SDK write every count the same; the session fails if they differ.

```console
$ node tests/dom/byte-sizes-session.js
{
  "nothing": {
    "bytes": 0,
    "reads": "0 B"
  },
  "one byte": {
    "bytes": 1,
    "reads": "1 B"
  },
  "the last count in bytes": {
    "bytes": 1023,
    "reads": "1023 B"
  },
  "the first in kilobytes": {
    "bytes": 1024,
    "reads": "1.0 KB"
  },
  "the last in kilobytes": {
    "bytes": 1048575,
    "reads": "1024.0 KB"
  },
  "the first in megabytes": {
    "bytes": 1048576,
    "reads": "1.0 MB"
  },
  "the last in megabytes": {
    "bytes": 1073741823,
    "reads": "1024.0 MB"
  },
  "the first in gigabytes": {
    "bytes": 1073741824,
    "reads": "1.0 GB"
  },
  "10.1 billion bytes": {
    "bytes": 10100000000,
    "reads": "9.4 GB"
  },
  "the last in gigabytes": {
    "bytes": 1099511627775,
    "reads": "1024.0 GB"
  },
  "the first in terabytes": {
    "bytes": 1099511627776,
    "reads": "1.0 TB"
  }
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
