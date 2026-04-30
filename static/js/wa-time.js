/* ── Timezone-aware timestamp formatting (site-wide) ──────── */
var WATime = (function() {
  /* Detect if user is in the US via timezone name or locale */
  var tz = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
  var locale = navigator.language || navigator.languages[0] || 'en-US';

  /* US timezones start with "America/" and are in US proper,
     plus Pacific/Honolulu, etc. We also check locale as fallback. */
  var US_TZ = /^(America\/(New_York|Chicago|Denver|Los_Angeles|Phoenix|Anchorage|Adak|Boise|Indiana|Kentucky|Menominee|Nome|North_Dakota|Sitka|Yakutat|Juneau|Metlakatla|Detroit)|Pacific\/Honolulu|US\/)/;
  var isUS = US_TZ.test(tz) || /^en-US$/i.test(locale);

  var hour12 = isUS;

  /**
   * Parse a UTC ISO string (with or without trailing 'Z') into a Date.
   * The backend stores timestamps like "2026-03-15T04:17:10.320960" (no Z) which are UTC.
   */
  function parseUTC(isoStr) {
    if (!isoStr) return null;
    var s = isoStr.trim();
    /* Ensure the string is treated as UTC */
    if (!/[Zz]$/.test(s) && !/[+\-]\d{2}:\d{2}$/.test(s)) {
      s += 'Z';
    }
    var d = new Date(s);
    return isNaN(d.getTime()) ? null : d;
  }

  /**
   * Format a Date object as a full datetime string in the user's local timezone.
   * US users: "Mar 15, 2026 12:17:10 AM"
   * Non-US:   "15 Mar 2026 00:17:10"
   */
  function formatDatetime(date) {
    if (!date) return '';
    try {
      return date.toLocaleString(isUS ? 'en-US' : locale, {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: hour12,
        timeZone: tz || undefined
      });
    } catch (e) {
      return date.toLocaleString();
    }
  }

  /**
   * Format a Date object as time-only in the user's local timezone.
   * US: "12:17:10 AM"   Non-US: "00:17:10"
   */
  function formatTime(date) {
    if (!date) return '';
    try {
      return date.toLocaleTimeString(isUS ? 'en-US' : locale, {
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: hour12,
        timeZone: tz || undefined
      });
    } catch (e) {
      return date.toLocaleTimeString();
    }
  }

  /**
   * Format a UTC ISO string directly to a local datetime string.
   */
  function fromISO(isoStr) {
    return formatDatetime(parseUTC(isoStr));
  }

  /**
   * Format a UTC ISO string to local time-only string.
   */
  function timeFromISO(isoStr) {
    return formatTime(parseUTC(isoStr));
  }

  /**
   * Auto-convert all elements with data-utc attribute on page load.
   * <span data-utc="2026-03-15T04:17:10" data-utc-format="datetime|time"></span>
   */
  function convertAll() {
    document.querySelectorAll('[data-utc]').forEach(function(el) {
      var iso = el.getAttribute('data-utc');
      var fmt = el.getAttribute('data-utc-format') || 'datetime';
      if (fmt === 'relative') {
        var d = parseUTC(iso); var now = new Date(); var diff = Math.floor((now - d) / 1000);
        if (diff < 60) el.textContent = 'just now';
        else if (diff < 3600) el.textContent = Math.floor(diff / 60) + ' minutes ago';
        else if (diff < 86400) el.textContent = Math.floor(diff / 3600) + ' hours ago';
        else el.textContent = Math.floor(diff / 86400) + ' days ago';
      } else {
        el.textContent = fmt === 'time' ? timeFromISO(iso) : fromISO(iso);
      }
      el.title = iso + ' UTC';
    });
  }

  /* Run after first paint to avoid blocking LCP */
  function scheduleConvert() {
    if (typeof requestIdleCallback === 'function') {
      requestIdleCallback(convertAll, { timeout: 200 });
    } else {
      setTimeout(convertAll, 0);
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scheduleConvert);
  } else {
    scheduleConvert();
  }

  /* Public API for use by page-specific scripts */
  return {
    parseUTC: parseUTC,
    formatDatetime: formatDatetime,
    formatTime: formatTime,
    fromISO: fromISO,
    timeFromISO: timeFromISO,
    isUS: isUS,
    timezone: tz,
    convertAll: convertAll
  };
})();
