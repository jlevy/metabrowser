"""Built-in binary plugin: the generic Bytes fallback preview.

Present so ``sidekick`` resolves as
``metabrowser.builtin_plugins.binary.sidekick`` rather than a bare
top-level ``sidekick``. Pytest collects every ``.py`` under ``src``
(``python_files = ["*.py"]``), and two plugin directories shipping a
``sidekick.py`` without package markers collide on that basename.
"""
