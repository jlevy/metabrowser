"""Process exit codes shared by lightweight and full CLI modules.

1 is a refusal or failure printed as one ``Error:`` line, and 2 a usage error (Click's).
The ``--present`` codes are for a caller that branches on what happened without parsing
the report, as the macOS app and an agent do.
"""

from __future__ import annotations

# `--present` could not read TARGET as a folder, a file, or a GitHub URL: the refusal
# names why, and nothing was looked up or sent.
PRESENT_REFUSED_EXIT_CODE = 3
# `--present` read TARGET but sent nothing: no app, an app that cannot take it, or an
# `open` that failed. The report's reason says which.
PRESENT_NOT_DELIVERED_EXIT_CODE = 4
INTERRUPTED_EXIT_CODE = 130
