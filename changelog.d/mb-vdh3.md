- **Plugin manifests:** a new optional `[plugin] python_requires` lists the third-party
  Python distributions a plugin’s own code imports, by distribution name.
  It installs nothing; it records which of Metabrowser’s dependencies only a plugin
  needs. `metab --plugins --json` and `metab --plugin NAME` show it, and every built-in
  plugin declares its list ([Python Dependencies](docs/plugins.md#python-dependencies)).

- **Dependencies:** `psutil` is no longer installed with Metabrowser; only development
  tools use it.
