# Roadmap

MetaBrowser treats compression as a transport layer around one logical file.
For example, `report.html.zst` should classify and render like `report.html` while all
reads remain bounded.
Checked items below are supported today; unchecked items are planned work.

## Transparent Single-File Compression

- [x] Gzip (`.gz`)
- [x] Raw zlib streams (`.zlib`)
- [ ] Zstandard (`.zst`)
- [ ] Evaluate common single-file formats such as xz (`.xz`), bzip2 (`.bz2`), and Brotli
  (`.br`) as real artifact demand appears

Adding a format requires logical-name and extension handling, streaming input/output and
CPU limits, malformed-stream behavior, and parity across preview, classification,
rendering, export, and raw serving.

## Archive and Container Formats

- [ ] Add safe browsing for ZIP archives (`.zip`)
- [ ] Add safe browsing for tar archives and compressed tarballs (`.tar`, `.tar.gz`,
  `.tgz`, `.tar.zst`)
- [ ] Define archive navigation, member preview, symlink and traversal rejection,
  duplicate-name handling, nesting limits, and aggregate decompression limits before
  enabling any container format

Archives contain multiple logical files, so they need a navigable virtual tree and a
stronger security boundary than transparent single-file compression.
They are not part of the v0.1.0 core contract.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
