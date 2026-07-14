// Built-in `lmdb` plugin: keys / entry / stats views for any LMDB env folder.
// Higher-level plugins can teach the renderer about specific value schemas via
// `mb.builtins.lmdb.registerValueDecoder(predicate, decode)`. The server-side
// decoder chain (see metabrowser/lmdb_reader.py) does the heavy lifting; the
// client-side hook is for the rare case of re-decoding bytes the server didn't
// recognise.

(() => {
  const mb = window.metabrowser;
  if (!mb) {
    return;
  }

  const clientDecoders = [];

  function registerValueDecoder(predicate, decode) {
    clientDecoders.push({ predicate, decode });
  }

  function decodeValue(subdb, keyHex, valueBytes, ctx) {
    for (let i = clientDecoders.length - 1; i >= 0; i--) {
      const d = clientDecoders[i];
      try {
        if (d.predicate(subdb, keyHex, valueBytes, ctx)) {
          return d.decode(valueBytes);
        }
      } catch (_e) {
        // fall through
      }
    }
    return null;
  }

  function escapeHtml(s) {
    return mb.escapeHtml(String(s == null ? "" : s));
  }

  function fmtSize(n) {
    return mb.formatSize ? mb.formatSize(n) : `${n} B`;
  }

  async function renderKeys(container, ctx) {
    container.innerHTML = '<div class="mb-plugin-lmdb-keys">Loading keys…</div>';
    let data;
    try {
      data = await mb.fetchPluginData("lmdb", "keys", { path: ctx.path });
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      container.innerHTML = `<div class="mb-plugin-lmdb-error">Failed to load keys: ${escapeHtml(message)}</div>`;
      return;
    }
    const rows = data?.keys || [];
    const nextCursor = data?.nextCursor;
    const tableRows = rows
      .map(
        (r) =>
          '<tr><td class="mb-plugin-lmdb-key">' +
          escapeHtml(r.key) +
          '</td><td class="mb-plugin-lmdb-subdb">' +
          escapeHtml(r.subdb || "(main)") +
          '</td><td class="mb-plugin-lmdb-size">' +
          escapeHtml(fmtSize(r.valueSize)) +
          '</td><td class="mb-plugin-lmdb-decoder">' +
          escapeHtml(r.decoderUsed) +
          '</td><td class="mb-plugin-lmdb-preview"><code>' +
          escapeHtml(r.valuePreview) +
          "</code></td></tr>",
      )
      .join("");
    const more = nextCursor
      ? '<div class="mb-plugin-lmdb-more">More keys available (cursor: <code>' +
        escapeHtml(nextCursor) +
        "</code>)</div>"
      : "";
    container.innerHTML =
      '<div class="mb-plugin-lmdb-keys md-body"><div class="table-container"><table class="data-table mb-plugin-lmdb-keys-table"><thead><tr><th>Key (hex)</th><th>Subdb</th><th>Size</th><th>Decoder</th><th>Preview</th></tr></thead><tbody>' +
      tableRows +
      "</tbody></table></div>" +
      more +
      "</div>";
  }

  async function renderEntry(container, _ctx) {
    container.innerHTML =
      '<div class="mb-plugin-lmdb-entry">Open a key from the Keys view to inspect its value.</div>';
  }

  async function renderStats(container, ctx) {
    container.innerHTML = '<div class="mb-plugin-lmdb-stats">Loading stats…</div>';
    let data;
    try {
      data = await mb.fetchPluginData("lmdb", "stats", { path: ctx.path });
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      container.innerHTML = `<div class="mb-plugin-lmdb-error">Failed to load stats: ${escapeHtml(message)}</div>`;
      return;
    }
    const rows = (data?.subdbs || [])
      .map(
        (s) =>
          "<tr><td>" +
          escapeHtml(s.name || "(main)") +
          "</td><td>" +
          escapeHtml(String(s.entries)) +
          "</td><td>" +
          escapeHtml(String(s.depth)) +
          "</td></tr>",
      )
      .join("");
    container.innerHTML =
      '<div class="mb-plugin-lmdb-stats md-body"><p>Total entries: <strong>' +
      escapeHtml(String(data?.totalEntries || 0)) +
      "</strong> · Map size: <strong>" +
      escapeHtml(fmtSize(data?.sizeBytes || 0)) +
      '</strong></p><div class="table-container"><table class="data-table mb-plugin-lmdb-stats-table"><thead><tr><th>Subdb</th><th>Entries</th><th>Depth</th></tr></thead><tbody>' +
      rows +
      "</tbody></table></div></div>";
  }

  mb.builtins = mb.builtins || {};
  mb.builtins.lmdb = {
    registerValueDecoder: registerValueDecoder,
    decodeValue: decodeValue,
    renderKeys: renderKeys,
    renderEntry: renderEntry,
    renderStats: renderStats,
  };

  mb.registerView("lmdb-database", "keys", { render: renderKeys });
  mb.registerView("lmdb-database", "entry", { render: renderEntry });
  mb.registerView("lmdb-database", "stats", { render: renderStats });
})();
