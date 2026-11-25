"""Built-in PDF plugin: the browser's own viewer on a file page, and a preview card elsewhere.

Present so the plugin's Python modules resolve as ``metabrowser.builtin_plugins.pdf.*``
rather than as bare top-level names. Pytest collects every ``.py`` under ``src``
(``python_files = ["*.py"]``), and two plugin directories shipping a ``sidekick.py``
without package markers collide on that basename.
"""
