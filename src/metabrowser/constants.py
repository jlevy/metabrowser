"""metabrowser constants — directory names, well-known paths, etc.

These are convention strings the metabrowser shell and its built-in
plugins recognize as interesting paths inside a served root. Consumers
that use a different runtime layout can ignore them.
"""

from __future__ import annotations

# Subdirectories under a run dir where logs / state are conventionally
# written. The activity tracker and tree walker treat dotfiles as
# hidden by default, but these two are unhidden.
LOGS_DIR = ".logs"
STATE_DIR = ".state"

__all__ = ["LOGS_DIR", "STATE_DIR"]
