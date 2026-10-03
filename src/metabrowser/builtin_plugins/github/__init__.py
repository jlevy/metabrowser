"""GitHub support: URL reducer, ``gh`` credential helper, first-clone size check, and
pull-request records and their page.

Core reaches it through ``metabrowser.cache.providers``. Its manifest mounts the
pull-request data routes under ``/api/plugin/github/`` and the view the shell mounts at
``/pull/<n>``, the served pull request's page.
"""
