// Locale-aware numeric formatting shared by the shell and plugins.

(() => {
  const integerFormatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
  const byteUnits = ["B", "KB", "MB", "GB", "TB", "PB"];

  /** @param {number} value */
  function formatBytes(value) {
    let amount = Number.isFinite(value) && value > 0 ? value : 0;
    let unit = 0;
    while (amount >= 1024 && unit < byteUnits.length - 1) {
      amount /= 1024;
      unit += 1;
    }
    if (unit === 0) {
      return `${Math.round(amount)} B`;
    }
    return `${amount.toFixed(1)} ${byteUnits[unit]}`;
  }

  /** @param {number} value */
  function formatInteger(value) {
    return integerFormatter.format(Math.max(0, Math.trunc(Number(value) || 0)));
  }

  /** @param {number} value */
  function formatFileCount(value) {
    const count = Math.max(0, Math.trunc(Number(value) || 0));
    return `${formatInteger(count)} ${count === 1 ? "file" : "files"}`;
  }

  window.MetabrowserFormatters = Object.freeze({ formatBytes, formatFileCount, formatInteger });
})();
