"""Process exit codes shared by lightweight and full CLI modules.

1 is a refusal or failure printed as one ``Error:`` line, and 2 a usage error (Click's).
The ``--present`` codes are for a caller that branches on what happened without parsing
the report, as the macOS app and an agent do: refused, no app to take it, or blocked.
The report's ``code`` names the case within each, and ``DELIVERY_EXIT_CODES`` in
``cli/present.py`` maps every delivery code to one of these, to 0 for a target the app
or a server for a browser took, or to 1 for a server that exited before it served.
"""

from __future__ import annotations

# `--present` could not read ROOT as a folder, a file, or a GitHub URL: the refusal
# names why, and nothing was looked up or sent.
PRESENT_REFUSED_EXIT_CODE = 3
# `--present` read ROOT under the `app` preference, and no app takes it: not macOS, no
# Metabrowser app registered with LaunchServices, one that is not installed in an
# Applications folder, one that is not named Metabrowser or does not declare the marker a
# current build declares, or a folder inside ROOT, which the app cannot select. Nothing
# was sent; installing or updating the app, or serving the target, is the remedy. Under
# `auto` such a target opens in a browser instead.
PRESENT_NO_APP_EXIT_CODE = 4
# `--present` found the app, or tried to, and LaunchServices could not be asked or did
# not take the target, as when a sandbox denies it: the lookup or `open` failed. What was
# sent, if anything, is unconfirmed; running the same command where LaunchServices is
# reachable is the remedy.
PRESENT_BLOCKED_EXIT_CODE = 5
INTERRUPTED_EXIT_CODE = 130
