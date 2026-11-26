// Loaded with the settings menu. The comparison reads the same preference when it mounts.
(function mountDefaultDiffLayout() {
  const select = /** @type {HTMLSelectElement | null} */ (
    document.getElementById("default-diff-layout")
  );
  if (!select) {
    return;
  }
  const prefs = window.metabrowser.prefs;
  select.value =
    prefs.get("diff.layout", /** @type {unknown} */ ("split")) === "unified" ? "unified" : "split";
  select.addEventListener("change", () => prefs.set("diff.layout", select.value));
  select.disabled = false;
})();
