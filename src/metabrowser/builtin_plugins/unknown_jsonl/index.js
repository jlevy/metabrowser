// Unknown-jsonl built-in plugin — fallback for .jsonl files whose
// adapter sniff doesn't match a built-in or plugin-registered adapter.
//
// Owns two views:
//   ("unknown-jsonl", "log") — same body as agent-log/log; reused via
//                              mb.builtins.agentLog.renderLog
//   ("unknown-jsonl", "raw") — same body as agent-log/raw; reused via
//                              mb.builtins.agentLog.renderRaw
//
// The agent-log built-in plugin (loaded first because builtin_plugins/
// is alphabetical and agent_log < unknown_jsonl) sets the namespace.
// If the agent-log plugin isn't loaded for some reason, the registrations
// fall back to an unavailable-view message from the shell.
(() => {
  const mb = window.metabrowser;
  if (!mb) {
    console.error("metabrowser unknown-jsonl plugin: window.metabrowser missing — SDK not loaded");
    return;
  }
  if (!mb.builtins?.agentLog) {
    console.warn(
      "metabrowser unknown-jsonl plugin: agent-log built-in not loaded; " +
        "log/raw views will fall back to the shell's empty state",
    );
    return;
  }

  mb.registerView("unknown-jsonl", "log", {
    render: mb.builtins.agentLog.renderLog,
    dispose: mb.builtins.agentLog.disposeLog,
  });
  mb.registerView("unknown-jsonl", "raw", { render: mb.builtins.agentLog.renderRaw });
})();
