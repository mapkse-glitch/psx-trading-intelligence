/* Display-only ordering. Never mutate API arrays used for indicators or exports. */
(function (root) {
  'use strict';
  function dateKey(value) {
    if (value === null || value === undefined || value === '') return -Infinity;
    const text = String(value).trim();
    let m = text.match(/^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?(Z|[+-]\d{2}:\d{2})?)?$/);
    if (!m) {
      const dayFirst = text.match(/^(\d{2})-(\d{2})-(\d{4})$/);
      if (!dayFirst) return -Infinity;
      m = [text, dayFirst[3], dayFirst[2], dayFirst[1]];
    }
    const year = Number(m[1]), month = Number(m[2] || 1), day = Number(m[3] || 1);
    const hour = Number(m[4] || 0), minute = Number(m[5] || 0), second = Number(m[6] || 0);
    if (year < 1000 || month < 1 || month > 12 || day < 1 || hour > 23 || minute > 59 || second > 59) return -Infinity;
    const date = new Date(Date.UTC(year, month - 1, day, hour, minute, second));
    if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return -Infinity;
    if (m[8]) {
      const instant = Date.parse(text.replace(' ', 'T'));
      return Number.isFinite(instant) ? instant : -Infinity;
    }
    return date.getTime() + Number(('0.' + (m[7] || '0'))) * 1000;
  }
  function newestFirst(rows, getDate = value => value) {
    return (Array.isArray(rows) ? rows : []).map((row, index) => ({row, index, key: dateKey(getDate(row))}))
      .sort((a, b) => a.key === b.key ? a.index - b.index : (a.key > b.key ? -1 : 1))
      .map(item => item.row);
  }
  const api = Object.freeze({dateKey, newestFirst});
  root.TableDisplay = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
