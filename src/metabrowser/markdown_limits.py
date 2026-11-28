"""Input budget shared by the Markdown diff and structured fence readers."""

import re

# Measured on the development Mac (Python 3.14, warm, minimum of three runs, load
# average 2-5 from other agents) over the 434 Markdown pairs this repository's last 200
# Markdown-touching first-parent commits made, each at most this many combined bytes:
# p50 12 ms, p90 31-33 ms, max 49-51 ms, against p50 26-27 ms, p90 52-54 ms and max
# 87-89 ms in adjacent runs of the earlier two-parse pipeline with highlighting.
# The slowest input found inside every budget is a 48 KiB side of `<`, 222 ms (258-268 ms
# at load average 17-18, as at round 2 of #349); `&#` took 188 ms and `<!-` 167 ms, the
# same at 128-byte, 1 KiB and 4 KiB lines, and in a worker process they delay no other
# request. Line length changed no measured cost (tables, prose and code at 1-23 KiB
# lines are linear in bytes), so lines are not bounded on their own. Bytes alone do not
# bound MarkdownIt's link-label scan: a 45 KiB nested bracket pair took 2.17 s.
MARKDOWN_DIFF_MAX_BYTES = 48 * 1024

# A side's lines that open or close a `:::` container. KPress's container rules rescan
# each one, and a run of them parses into a handful of tokens, so the token budget cannot
# refuse it early: 256 lines took 11.5 ms, 1,024 took 42 ms, and 11,000 (44 KB) took
# 456 ms to refuse (load average 19). A real document holds a few dozen.
_MAX_CONTAINER_LINES = 256

# A line that opens or closes a container block (`:::`), after any quote or list marker.
_CONTAINER_LINE = re.compile(rb"^[ \t]*(?:(?:>|[-*+]|\d{1,9}[.)])[ \t]*)*:::", re.MULTILINE)

# MarkdownIt stops parsing blocks at this depth, so a side that reaches it is refused
# rather than shown without its rest. KPress's own limit is 100: 48 KiB of `1. ` lines
# nest 85 deep and parsed in 243 ms; at 32 the same input parsed in 3.0 ms. The render
# tree is held to the same depth.
_MAX_NESTING = 32
