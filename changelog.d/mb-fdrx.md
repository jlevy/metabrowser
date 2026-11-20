- Plugin authors: Metabrowser’s own JSONL adapters now register through
  `register_log_adapter` like a plugin’s, so no adapter name is reserved and
  `registered_log_adapters()` lists them all in detection order.
  `register_log_adapter` takes an optional `line_detector` for a stream that opens with
  plain text. Detection asks Metabrowser’s detectors before a plugin’s.

- Plugin authors: a `[[view]]` of the `folder` kind can declare
  `offer = "module:function"`, a predicate that decides which folders show the view; an
  offered default view becomes that folder’s default.

- Plugin authors: a `[[kind]]` with `binary = true` claims a binary file by its path, so
  a format Metabrowser cannot read as text reaches the plugin’s views.

- Plugin authors: `metabrowser.plugin_api` adds `plugin_cache_directory`,
  `PluginCacheUnavailableError`, `jsonl_parse_max_bytes`, `extract_agent_charts_bytes`,
  `lookup_agent_charts`, `remember_agent_charts`, and `registered_log_adapters`.
