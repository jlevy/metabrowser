// Locale-aware numeric formatting shared by the shell and plugins.

(() => {
  const integerFormatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
  const byteUnits = ["B", "KB", "MB", "GB", "TB", "PB"];
  /** Byte counts above this boundary receive the shared stronger emphasis. */
  const SIZE_LARGE_THRESHOLD_BYTES = 1024 * 1024;
  /** File counts at or above this boundary receive the shared stronger emphasis. */
  const COUNT_LARGE_THRESHOLD = 1000;

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

  /** @param {number} value */
  function sizeClass(value) {
    return (Number(value) || 0) > SIZE_LARGE_THRESHOLD_BYTES ? "size-large" : "";
  }

  /** @param {number} value */
  function countClass(value) {
    return (Number(value) || 0) >= COUNT_LARGE_THRESHOLD ? "count-large" : "";
  }

  window.MetabrowserFormatters = Object.freeze({
    countClass,
    formatBytes,
    formatFileCount,
    formatInteger,
    sizeClass,
  });
})();
