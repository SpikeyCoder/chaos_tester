// HTML escape helper — used to neutralise content sourced from third-party
// AI APIs (Perplexity, etc.) before it reaches innerHTML. See pentest report
// 2026-05-03 finding WA-3.
function _escHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Scroll to a specific result row and auto-expand its detail panel
  function openResultById(idx) {
    setTimeout(function() {
      var row = document.getElementById('result-row-' + idx);
      if (!row) return;
      // Make sure it's visible even if current filter is hiding it
      row.style.display = '';
      // Expand the detail cell if collapsed
      var cell = row.querySelector('.result-detail-cell');
      if (cell && cell.style.display === 'none' && typeof toggleResultDetail === 'function') {
        toggleResultDetail(row);
      }
      // Gentle highlight
      row.style.transition = 'background-color 0.4s ease';
      var prev = row.style.backgroundColor;
      row.style.backgroundColor = 'rgba(249,115,22,0.15)';
      setTimeout(function() { row.style.backgroundColor = prev; }, 1800);
    }, 100);
  }

document.addEventListener('DOMContentLoaded', function() {
  if (typeof reportData === 'undefined') return;
  var results = (reportData.results || []);
  /* Build per-module pass rates */
  var modules = {};
  results.forEach(function(r) {
    var m = r.module || 'other';
    if (!modules[m]) modules[m] = { total: 0, passed: 0 };
    modules[m].total++;
    if (r.status === 'passed') modules[m].passed++;
  });
  function rate(m) {
    if (!modules[m]) return null;
    return Math.round((modules[m].passed / modules[m].total) * 100);
  }
  function combine() {
    var total = 0, passed = 0;
    for (var i = 0; i < arguments.length; i++) {
      var m = modules[arguments[i]];
      if (m) { total += m.total; passed += m.passed; }
    }
    return total > 0 ? Math.round((passed / total) * 100) : null;
  }

  /* Check for Lighthouse performance score */
  var perf = reportData.performance_metrics || {};
  var perfScore = null;
  if (perf.mobile && perf.mobile.score != null) perfScore = Math.round(perf.mobile.score * 100);
  else if (perf.desktop && perf.desktop.score != null) perfScore = Math.round(perf.desktop.score * 100);

  var sections = [];
  if (perfScore !== null) sections.push({ label: 'Performance', score: perfScore });
  var sec = combine('security', 'auth');
  if (sec !== null) sections.push({ label: 'Security', score: sec });
  var avail = rate('availability');
  if (avail !== null) sections.push({ label: 'Availability', score: avail });
  var lf = combine('links', 'forms');
  if (lf !== null) sections.push({ label: 'Links & Forms', score: lf });
  var ch = rate('chaos');
  if (ch !== null) sections.push({ label: 'Resilience', score: ch });

  /* If we don't have enough sections, add an overall */
  if (sections.length < 3) {
    var s = reportData.summary || {};
    if (s.pass_rate != null) sections.push({ label: 'Overall', score: Math.round(s.pass_rate) });
  }

  /* Render SVG ring gauges */
  var container = document.getElementById('sectionGauges');
  if (!container || sections.length === 0) return;

  sections.forEach(function(sec) {
    var score = sec.score;
    var color = score >= 90 ? '#4ade80' : (score >= 70 ? '#f97316' : '#ef4444');
    var bg = score >= 90 ? 'rgba(74,222,128,0.12)' : (score >= 70 ? 'rgba(249,115,22,0.12)' : 'rgba(239,68,68,0.12)');
    var r = 44, stroke = 7, circ = 2 * Math.PI * r;
    var offset = circ - (score / 100) * circ;
    var html = '<div class="section-gauge-item">' +
      '<div class="gauge-ring" style="position:relative;width:110px;height:110px;">' +
        '<svg viewBox="0 0 100 100" width="110" height="110" aria-hidden="true" focusable="false">' +
          '<circle cx="50" cy="50" r="' + r + '" fill="none" stroke="rgba(51,65,85,0.6)" stroke-width="' + stroke + '"/>' +
          '<circle cx="50" cy="50" r="' + r + '" fill="none" stroke="' + color + '" stroke-width="' + stroke + '" ' +
            'stroke-dasharray="' + circ + '" stroke-dashoffset="' + offset + '" ' +
            'stroke-linecap="round" transform="rotate(-90 50 50)" ' +
            'style="transition:stroke-dashoffset 1s ease;"/>' +
        '</svg>' +
        '<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;">' +
          '<span style="font-size:1.6rem;font-weight:700;color:' + color + ';">' + score + '</span>' +
        '</div>' +
      '</div>' +
      '<div class="gauge-label-text">' + sec.label + '</div>' +
    '</div>';
    container.insertAdjacentHTML('beforeend', html);
  });
});

let currentStatus = 'issues';
let currentModule = 'all';
const RESULTS_VISIBLE_LIMIT = 10;
let _resultsExpanded = false;

/* F-05: Expand/collapse result row details */
function toggleResultDetail(row) {
  var detailCell = row.querySelector('.result-detail-cell');
  var chevron = row.querySelector('.expand-chevron');
  if (!detailCell) return;
  var isOpen = detailCell.style.display !== 'none';
  detailCell.style.display = isOpen ? 'none' : '';
  if (chevron) chevron.style.transform = isOpen ? '' : 'rotate(90deg)';
}

function scrollToResults(filter) {
  /* Optionally apply a filter before scrolling */
  if (filter && filter !== 'all') {
    var btn = document.querySelector('.filter-btn[data-filter="' + filter + '"]');
    if (btn) filterResults(filter, btn);
  } else if (filter === 'all') {
    var allBtn = document.querySelector('.filter-btn[data-filter="all"]');
    if (allBtn) filterResults('all', allBtn);
  }
  /* Smooth scroll to the Detailed Results heading */
  var target = document.getElementById('detailed-results-heading');
  if (target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function filterResults(status, btn) {
  currentStatus = status;
  document.querySelectorAll('.filter-btn').forEach(b => { b.classList.remove('active'); b.setAttribute('aria-pressed', 'false'); });
  btn.classList.add('active');
  btn.setAttribute('aria-pressed', 'true');
  applyFilters();
}
function filterModule(mod, btn) {
  currentModule = mod;
  document.querySelectorAll('.module-btn').forEach(b => { b.classList.remove('active'); b.setAttribute('aria-pressed', 'false'); });
  btn.classList.add('active');
  btn.setAttribute('aria-pressed', 'true');
  applyFilters();
}
function applyFilters() {
  var isFiltering = currentStatus !== 'all' || currentModule !== 'all';
  var container = document.getElementById('detailed-results-wrapper');
  if (isFiltering) {
    container.classList.add('scrollable-table');
  } else if (!_detailedExpanded) {
    container.classList.remove('scrollable-table');
  }
  var shownCount = 0;
  var matchedTotal = 0;
  document.querySelectorAll('.result-row').forEach(function(row, i) {
    var st = row.dataset.status;
    var matchStatus;
    if (currentStatus === 'all') {
      matchStatus = true;
    } else if (currentStatus === 'issues') {
      matchStatus = (st === 'failed' || st === 'error' || st === 'warning');
    } else {
      matchStatus = (st === currentStatus);
    }
    var matchModule = currentModule === 'all' || row.dataset.module === currentModule;
    var matches = matchStatus && matchModule;
    if (matches) matchedTotal++;
    if (matches && (_resultsExpanded || shownCount < RESULTS_VISIBLE_LIMIT)) {
      row.style.display = '';
      if (!_resultsExpanded) shownCount++;
    } else {
      row.style.display = 'none';
    }
  });
  updateShowAllButton(matchedTotal);
}

function updateShowAllButton(matchedTotal) {
  var wrap = document.getElementById('show-all-results-wrap');
  var btn = document.getElementById('show-all-toggle-btn');
  if (!wrap || !btn) return;
  if (matchedTotal > RESULTS_VISIBLE_LIMIT) {
    wrap.hidden = false;
    btn.textContent = _resultsExpanded
      ? 'Show First ' + RESULTS_VISIBLE_LIMIT + ' Results'
      : 'Show All ' + matchedTotal + ' Results';
    btn.setAttribute('aria-expanded', _resultsExpanded ? 'true' : 'false');
  } else {
    wrap.hidden = true;
  }
}

function toggleShowAllResults(btn) {
  _resultsExpanded = !_resultsExpanded;
  applyFilters();
}

function switchPerfTab(strategy) {
  document.querySelectorAll('.perf-panel').forEach(function(p) { p.style.display = 'none'; });
  document.querySelectorAll('.perf-tab').forEach(function(t) {
    t.classList.remove('active');
    t.setAttribute('aria-selected', 'false');
    t.setAttribute('tabindex', '-1');
  });
  document.getElementById('panel-' + strategy).style.display = 'block';
  var tab = document.getElementById('tab-' + strategy);
  tab.classList.add('active');
  tab.setAttribute('aria-selected', 'true');
  tab.setAttribute('tabindex', '0');
}

// Click listeners for perf tabs (restored after CSP refactoring removed inline onclick)
(function() {
  document.querySelectorAll('.perf-tab').forEach(function(tab) {
    tab.addEventListener('click', function() {
      var strategy = this.id.replace('tab-', '');
      if (typeof switchPerfTab === 'function') switchPerfTab(strategy);
    });
  });
})();

// Arrow-key keyboard navigation for the Performance tablist (WCAG 2.1 keyboard)
(function() {
  var tablist = document.querySelector('.perf-tabs[role="tablist"]');
  if (!tablist) return;
  var tabs = Array.prototype.slice.call(tablist.querySelectorAll('[role="tab"]'));
  tabs.forEach(function(tab, i) {
    tab.setAttribute('tabindex', tab.classList.contains('active') ? '0' : '-1');
    tab.addEventListener('keydown', function(e) {
      var next = null;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = tabs[(i + 1) % tabs.length];
      else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = tabs[(i - 1 + tabs.length) % tabs.length];
      else if (e.key === 'Home') next = tabs[0];
      else if (e.key === 'End') next = tabs[tabs.length - 1];
      if (next) {
        e.preventDefault();
        var strategy = next.id.replace('tab-', '');
        if (typeof switchPerfTab === 'function') switchPerfTab(strategy);
        next.focus();
      }
    });
  });
})();

(function() {
  /* Lighthouse performance thresholds (values in same units as metric data) */
  var TH = {
    'overall':                  {g:90,  y:50,   max:100,  rev:true, gl:'90', yl:'50'},
    'first-contentful-paint':   {g:1.8, y:3.0,  max:6.0,  rev:false, gl:'1.8s', yl:'3.0s'},
    'speed-index':              {g:3.4, y:5.8,  max:10.0, rev:false, gl:'3.4s', yl:'5.8s'},
    'largest-contentful-paint': {g:2.5, y:4.0,  max:8.0,  rev:false, gl:'2.5s', yl:'4.0s'},
    'cumulative-layout-shift':  {g:0.1, y:0.25, max:0.5,  rev:false, gl:'0.1',  yl:'0.25'},
    'interactive':              {g:3.8, y:7.3,  max:12.0, rev:false, gl:'3.8s', yl:'7.3s'},
    'total-blocking-time':      {g:200, y:600,  max:1200, rev:false, gl:'200ms',yl:'600ms'}
  };

  var NS = 'http://www.w3.org/2000/svg';

  function el(tag, attrs) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  function arcPt(cx, cy, r, proportion) {
    var a = Math.PI * (1 - proportion);
    return { x: cx + r * Math.cos(a), y: cy - r * Math.sin(a) };
  }

  function drawGauge(container) {
    var type  = container.getAttribute('data-type');
    var value = parseFloat(container.getAttribute('data-value'));
    var disp  = container.getAttribute('data-display') || '';
    var big   = container.classList.contains('gauge-main');

    var cfg = TH[type];
    if (!cfg) return;

    /* Dimensions */
    var PAD = big ? 20 : 14;
    var W = 200 + PAD * 2, H = big ? 150 : 134;
    var CX = 100 + PAD, CY = big ? 115 : 104;
    var R  = big ? 80 : 70;
    var SW = big ? 16 : 12;
    var ARC = Math.PI * R;

    /* Color band proportions (fraction of arc) */
    var gP, yP, rP;
    if (cfg.rev) {
      gP = (cfg.max - cfg.g) / cfg.max;          /* 10% */
      yP = (cfg.g - cfg.y) / cfg.max;            /* 40% */
      rP = cfg.y / cfg.max;                       /* 50% */
    } else {
      gP = cfg.g / cfg.max;
      yP = (cfg.y - cfg.g) / cfg.max;
      rP = (cfg.max - cfg.y) / cfg.max;
    }
    var gL = gP * ARC, yL = yP * ARC, rL = rP * ARC;

    /* Needle position (0 = left, 1 = right) */
    var nPos;
    if (cfg.rev) {
      nPos = Math.max(0, Math.min(1, (cfg.max - value) / cfg.max));
    } else {
      nPos = Math.max(0, Math.min(1, value / cfg.max));
    }
    var needleDeg = -90 + nPos * 180;

    /* Needle color = zone it points to */
    var nCol;
    if (nPos <= gP + 0.001) nCol = '#0cce6b';
    else if (nPos <= gP + yP + 0.001) nCol = '#ffa400';
    else nCol = '#ff4e42';

    /* Build SVG */
    var svg = el('svg', {viewBox: '0 0 ' + W + ' ' + H});
    svg.style.width = '100%';
    svg.style.maxWidth = big ? '260px' : '195px';

    var arcD = 'M ' + (CX - R) + ',' + CY +
               ' A ' + R + ',' + R + ' 0 0,1 ' + (CX + R) + ',' + CY;

    /* Background track */
    svg.appendChild(el('path', {
      d: arcD, fill: 'none', stroke: 'rgba(255,255,255,0.06)',
      'stroke-width': SW, 'stroke-linecap': 'butt'
    }));

    /* Green band */
    svg.appendChild(el('path', {
      d: arcD, fill: 'none', stroke: '#0cce6b',
      'stroke-width': SW, 'stroke-linecap': 'butt',
      'stroke-dasharray': gL + ' ' + (ARC * 3)
    }));

    /* Yellow band */
    svg.appendChild(el('path', {
      d: arcD, fill: 'none', stroke: '#ffa400',
      'stroke-width': SW, 'stroke-linecap': 'butt',
      'stroke-dasharray': '0.001 ' + gL + ' ' + yL + ' ' + (ARC * 3)
    }));

    /* Red band */
    svg.appendChild(el('path', {
      d: arcD, fill: 'none', stroke: '#ff4e42',
      'stroke-width': SW, 'stroke-linecap': 'butt',
      'stroke-dasharray': '0.001 ' + (gL + yL) + ' ' + rL + ' ' + (ARC * 3)
    }));

    /* -- Transition tick marks & labels ------------------- */
    function addTick(prop, label) {
      var oP = arcPt(CX, CY, R + SW / 2 + 1, prop);
      var iP = arcPt(CX, CY, R - SW / 2 - 1, prop);
      svg.appendChild(el('line', {
        x1: oP.x, y1: oP.y, x2: iP.x, y2: iP.y,
        stroke: 'rgba(255,255,255,0.4)', 'stroke-width': '1.5'
      }));
      var lP = arcPt(CX, CY, R + SW / 2 + (big ? 13 : 11), prop);
      var t = el('text', {
        x: lP.x, y: lP.y, 'text-anchor': 'middle',
        'dominant-baseline': 'middle',
        fill: 'rgba(255,255,255,0.55)',
        'font-size': big ? '10' : '8',
        'font-family': 'system-ui, sans-serif'
      });
      t.textContent = label;
      svg.appendChild(t);
    }

    addTick(gP, cfg.gl);
    addTick(gP + yP, cfg.yl);

    /* -- Moylan Arrow needle ------------------------------ */
    var NL = R - 16;
    var nw = big ? 4.5 : 3.5;

    var g = el('g', {transform: 'rotate(' + needleDeg + ', ' + CX + ', ' + CY + ')'});

    /* Arrow shaft – tapers to point */
    g.appendChild(el('polygon', {
      points: [
        (CX - nw) + ',' + CY,
        (CX + nw) + ',' + CY,
        (CX + 1.2) + ',' + (CY - NL + 6),
        CX + ',' + (CY - NL),
        (CX - 1.2) + ',' + (CY - NL + 6)
      ].join(' '),
      fill: nCol, opacity: '0.92'
    }));

    /* Small counterweight tail */
    g.appendChild(el('polygon', {
      points: [
        (CX - nw * 0.6) + ',' + CY,
        (CX + nw * 0.6) + ',' + CY,
        (CX + nw * 0.4) + ',' + (CY + 10),
        (CX - nw * 0.4) + ',' + (CY + 10)
      ].join(' '),
      fill: '#555', opacity: '0.7'
    }));

    /* Hub circle */
    g.appendChild(el('circle', {
      cx: CX, cy: CY, r: big ? 7 : 5.5,
      fill: '#555', stroke: '#777', 'stroke-width': '1.5'
    }));

    svg.appendChild(g);

    /* -- Value display ------------------------------------ */
    var vt = el('text', {
      x: CX, y: CY + (big ? 28 : 22),
      'text-anchor': 'middle', fill: nCol,
      'font-size': big ? '24' : '16',
      'font-weight': 'bold',
      'font-family': 'system-ui, sans-serif'
    });
    vt.textContent = disp;
    svg.appendChild(vt);

    container.appendChild(svg);
  }

  /* Render all gauges on the page */
  document.querySelectorAll('.gauge-container').forEach(drawGauge);
})();

/* Table column sorting */
(function() {
  var table = document.getElementById('resultsTable');
  if (!table) return;
  var headers = table.querySelectorAll('th');
  headers.forEach(function(th, colIdx) {
    th.style.cursor = 'pointer';
    th.setAttribute('role', 'columnheader');
    th.setAttribute('aria-sort', 'none');
    th.title = 'Click to sort';
    th.addEventListener('click', function() {
      var tbody = table.querySelector('tbody');
      var rows = Array.from(tbody.querySelectorAll('tr'));
      var asc = th.getAttribute('aria-sort') !== 'ascending';
      headers.forEach(function(h) { h.setAttribute('aria-sort', 'none'); h.textContent = h.textContent.replace(/ [▲▼]$/, ''); });
      th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');
      th.textContent = th.textContent + (asc ? ' ▲' : ' ▼');
      rows.sort(function(a, b) {
        var aVal = (a.children[colIdx] || {}).textContent || '';
        var bVal = (b.children[colIdx] || {}).textContent || '';
        var aNum = parseFloat(aVal); var bNum = parseFloat(bVal);
        if (!isNaN(aNum) && !isNaN(bNum)) return asc ? aNum - bNum : bNum - aNum;
        return asc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      });
      rows.forEach(function(r) { tbody.appendChild(r); });
    });
  });
})();

/* Detailed Results table toggle */
var _detailedExpanded = false;
function toggleDetailedResults() {
  _detailedExpanded = !_detailedExpanded;
  var rows = document.querySelectorAll('.result-row');
  var container = document.getElementById('detailed-results-wrapper');
  var btn = document.getElementById('detailed-toggle-btn');
  btn.setAttribute('aria-expanded', _detailedExpanded ? 'true' : 'false');
  if (_detailedExpanded) {
    rows.forEach(function(r) { r.style.display = ''; });
    container.classList.add('scrollable-table');
    btn.textContent = 'Show First 5 Results \u25B2';
  } else {
    rows.forEach(function(r, i) { r.style.display = i >= 5 ? 'none' : ''; });
    container.classList.remove('scrollable-table');
    btn.textContent = 'Show All ' + rows.length + ' Results \u25BC';
  }
}

/* ── AI Visibility Recommendations ─────────────────────── */
(function() {
  var ai = (reportData || {}).ai_visibility;
  var container = document.getElementById('ai-recs-list');
  if (!ai || !container) return;

  var recs = [];
  var score = ai.overall_score || 0;
  var appearances = ai.total_appearances || 0;
  var total = ai.total_queries || 1;

  // Analyze platform gaps
  var platformScores = ai.platform_scores || {};
  var weakPlatforms = [];
  var strongPlatforms = [];
  for (var pname in platformScores) {
    var ps = platformScores[pname];
    if (ps.score < 30) weakPlatforms.push(pname);
    else if (ps.score >= 60) strongPlatforms.push(pname);
  }

  // Analyze query results for patterns
  var results = ai.all_results || [];
  var noAppearCount = 0;
  var lowPosCount = 0;
  for (var i = 0; i < results.length; i++) {
    if (!results[i].client_appears) noAppearCount++;
    else if (results[i].position > 3) lowPosCount++;
  }

  // Generate recommendations based on data
  if (score < 25) {
    recs.push({
      icon: '!',
      title: 'Strengthen Your Online Presence',
      text: 'Your business appears in only ' + score + '% of AI queries. Focus on building authoritative content, earning quality backlinks, and maintaining consistent NAP (Name, Address, Phone) across directories.'
    });
  }
  if (weakPlatforms.length > 0) {
    recs.push({
      icon: '*',
      title: 'Improve Visibility on ' + weakPlatforms.join(' & '),
      text: 'Your business scores below 30% on ' + weakPlatforms.join(', ') + '. Ensure your Google Business Profile is complete, encourage customer reviews, and add structured data (schema.org) to your website.'
    });
  }
  if (noAppearCount > total * 0.5) {
    recs.push({
      icon: '>',
      title: 'Create Sector-Specific Content',
      text: 'AI models aren\'t recommending your business for ' + noAppearCount + ' out of ' + total + ' queries. Publish authoritative blog posts, case studies, and FAQs targeting the exact phrases customers use.'
    });
  }
  if (lowPosCount > 3) {
    recs.push({
      icon: '⬆️',
      title: 'Boost Ranking Position',
      text: 'You appear in results but often below position 3. Increase review count and ratings, add testimonials to your site, and pursue local press mentions to strengthen authority signals.'
    });
  }
  if (score >= 50 && strongPlatforms.length >= 2) {
    recs.push({
      icon: '+',
      title: 'Maintain Your Strong Visibility',
      text: 'Great performance on ' + strongPlatforms.join(', ') + '! Keep your business listings updated, continue generating fresh reviews, and regularly publish new content to maintain this advantage.'
    });
  }
  // Always provide at least one recommendation
  if (recs.length === 0) {
    recs.push({
      icon: 'i',
      title: 'Optimize for AI Discovery',
      text: 'Add structured data markup (LocalBusiness schema), maintain an active Google Business Profile, and ensure your website clearly states your services, location, and business name.'
    });
  }

  // Render top 3
  var html = '';
  for (var j = 0; j < Math.min(recs.length, 3); j++) {
    var r = recs[j];
    html += '<div style="display:flex;gap:12px;align-items:flex-start;margin-bottom:10px;padding:12px;background:var(--surface);border-radius:8px;">';
    html += '<span style="font-size:1.3rem;flex-shrink:0;">' + r.icon + '</span>';
    html += '<div><div style="font-weight:600;font-size:0.9rem;">' + r.title + '</div>';
    html += '<div style="color:var(--text-muted);font-size:0.82rem;margin-top:2px;">' + r.text + '</div></div></div>';
  }
  container.innerHTML = html;
})();

/* ── Custom AI Query ─────────────────────────────────────── */
function runCustomAIQuery() {
  var input = document.getElementById('custom-ai-query');
  var btn = document.getElementById('custom-ai-btn');
  var statusEl = document.getElementById('custom-ai-status');
  var errorEl = document.getElementById('custom-ai-error');
  var resultsEl = document.getElementById('custom-ai-results');
  var query = input.value.trim();

  if (!query) {
    input.focus();
    input.style.borderColor = 'var(--danger)';
    setTimeout(function() { input.style.borderColor = ''; }, 2000);
    return;
  }

  // Get run_id from reportData
  var runId = reportData.run_id;

  btn.disabled = true;
  btn.textContent = 'Querying...';
  statusEl.style.display = 'block';
  errorEl.style.display = 'none';
  resultsEl.style.display = 'none';

  fetch('/api/ai-query', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest'
    },
    body: JSON.stringify({ query: query, run_id: runId })
  })
  .then(function(r) {
    // Subscription gate: render an upsell card with a real CTA instead
    // of the generic "Query failed: subscription_required" string.
    if (r.status === 403) {
      return r.json().catch(function() { return {}; }).then(function(body) {
        if (body && body.error === 'subscription_required') {
          statusEl.style.display = 'none';
          btn.disabled = false;
          btn.textContent = 'Run Query';
          errorEl.textContent = '';
          var url = body.upgrade_url || 'https://api.website-auditor.io/admin_portal/';
          var card = document.createElement('div');
          card.style.cssText = 'background:var(--surface);border-left:4px solid var(--accent);padding:16px;border-radius:8px;text-align:left;';
          var h = document.createElement('div');
          h.style.cssText = 'font-weight:600;margin-bottom:6px;';
          h.textContent = 'Subscription required';
          var p = document.createElement('div');
          p.style.cssText = 'color:var(--text-muted);font-size:0.9rem;margin-bottom:10px;';
          p.textContent = body.message || 'Custom AI Visibility queries require an active subscription or free trial.';
          var a = document.createElement('a');
          a.className = 'btn btn-primary';
          a.href = url;
          a.target = '_blank';
          a.rel = 'noopener';
          a.textContent = 'Upgrade or start a free trial';
          card.appendChild(h);
          card.appendChild(p);
          card.appendChild(a);
          errorEl.appendChild(card);
          errorEl.style.display = 'block';
          var stop = new Error('handled');
          stop.handled = true;
          throw stop;
        }
        throw new Error((body && body.error) || r.statusText);
      });
    }
    if (!r.ok) return r.json().then(function(d) { throw new Error(d.error || r.statusText); });
    return r.json();
  })
  .then(function(data) {
    statusEl.style.display = 'none';
    btn.disabled = false;
    btn.textContent = 'Run Query';

    if (!data.results || data.results.length === 0) {
      errorEl.textContent = 'No results returned. The AI platforms may be unavailable.';
      errorEl.style.display = 'block';
      return;
    }

    // Check if API key is not configured
    var hasNoApiKey = data.results.some(function(r) {
      return r.recommended === "(no API key configured)";
    });

    if (hasNoApiKey) {
      errorEl.textContent = 'API key not configured. Custom queries require PERPLEXITY_API_KEY environment variable to be set.';
      errorEl.style.display = 'block';
      return;
    }

    // Build results cards
    var html = '<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));gap:12px;">';
    data.results.forEach(function(r) {
      var color = r.client_appears ? 'var(--green)' : 'var(--red)';
      var safeColor = /^#[0-9a-fA-F]{3,8}$|^var\(--[a-z0-9-]+\)$/.test(String(r.platform_color || ''))
        ? r.platform_color
        : 'var(--text-muted)';
      var safeLogo = _escHtml(r.platform_logo_url);
      var safePlatform = _escHtml(r.platform);
      var safePos = Number(r.position) || 0;
      var safeRecommended = _escHtml(r.recommended);
      html += '<div style="background:var(--surface);border-radius:10px;padding:16px;border-left:4px solid ' + safeColor + ';">';
      html += '<div style="font-weight:600;margin-bottom:8px;display:flex;align-items:center;gap:6px;">';
      html += '<img src="' + safeLogo + '" width="18" height="18" alt="' + safePlatform + '"> ' + safePlatform + '</div>';
      html += '<div style="font-size:0.85rem;margin-bottom:6px;">';
      if (r.client_appears) {
        html += '<span class="badge badge-passed">Found at #' + safePos + '</span>';
      } else {
        html += '<span class="badge badge-failed">Not found</span>';
      }
      html += '</div>';
      html += '<div style="color:var(--text-muted);font-size:0.8rem;"><strong>Recommended:</strong> ' + safeRecommended + '</div>';
      html += '</div>';
    });
    html += '</div>';
    resultsEl.innerHTML = html;
    resultsEl.style.display = 'block';
  })
  .catch(function(err) {
    if (err && err.handled) return;
    statusEl.style.display = 'none';
    btn.disabled = false;
    btn.textContent = 'Run Query';
    errorEl.textContent = 'Query failed: ' + err.message;
    errorEl.style.display = 'block';
  });
}

// Allow Enter key to trigger custom query
document.getElementById('custom-ai-query') && document.getElementById('custom-ai-query').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') runCustomAIQuery();
});

/* AI Results table toggle */
var _aiExpanded = false;
function toggleAIResults() {
  _aiExpanded = !_aiExpanded;
  var rows = document.querySelectorAll('.ai-result-row');
  var container = document.getElementById('ai-results-table');
  var btn = document.getElementById('ai-toggle-btn');
  if (_aiExpanded) {
    rows.forEach(function(r) { r.style.display = ''; });
    container.classList.add('scrollable-table');
    btn.textContent = 'Show First 5 Results \u25B2';
  } else {
    rows.forEach(function(r, i) { r.style.display = i >= 5 ? 'none' : ''; });
    container.classList.remove('scrollable-table');
    btn.textContent = 'Show All ' + rows.length + ' Results \u25BC';
  }
}

/* ====== Finding Guidance System ====== */
var findingGuidance = {
  '404': {
    meaning: 'This page doesn\'t exist anymore. When visitors or Google\'s crawler hits this link, they get an error. This can hurt your search rankings and frustrate customers.',
    action: 'Either fix the link to point to the correct page, set up a redirect to a working page, or remove the broken link entirely.'
  },
  'redirect_chain': {
    meaning: 'This link bounces through multiple redirects before reaching the final page. Each redirect slows down page load and can confuse search engines.',
    action: 'Update the link to point directly to the final destination URL, skipping the intermediate redirects.'
  },
  'security_headers': {
    meaning: 'Your site is missing important security protections that help prevent attacks like cross-site scripting and clickjacking.',
    action: 'Ask your web developer or hosting provider to add the recommended security headers to your server configuration.'
  },
  'form_labels': {
    meaning: 'Screen readers and assistive technologies can\'t identify what information this form field needs. This makes your site harder to use for people with disabilities.',
    action: 'Add a descriptive label to each form field so all users can understand what information to enter.'
  },
  'slow_page': {
    meaning: 'This page takes too long to load. Most visitors will leave if a page takes more than 3 seconds. Slow pages also rank lower in Google search results.',
    action: 'Compress images, enable browser caching, and minimize JavaScript and CSS files. Consider using a CDN.'
  },
  'missing_https': {
    meaning: 'Your site isn\'t using a secure connection. Visitors may see a "Not Secure" warning in their browser, and Google penalizes non-HTTPS sites in search rankings.',
    action: 'Install an SSL certificate (many hosts offer this for free) and redirect all HTTP traffic to HTTPS.'
  },
  'mixed_content': {
    meaning: 'Your secure (HTTPS) page is loading some resources over insecure HTTP. This can trigger browser warnings and compromise your site\'s security.',
    action: 'Update all resource URLs (images, scripts, stylesheets) to use HTTPS instead of HTTP.'
  }
};

// Pattern matching rules for finding types
var findingPatterns = [
  { key: '404', patterns: ['404', 'broken', 'not found', 'does not exist'] },
  { key: 'redirect_chain', patterns: ['redirect chain', 'multiple redirect', 'chained redirect'] },
  { key: 'security_headers', patterns: ['content-security-policy', 'x-frame-options', 'security header', 'missing.*header'] },
  { key: 'form_labels', patterns: ['missing label', 'no label', 'form field.*label', 'label.*form'] },
  { key: 'slow_page', patterns: ['slow load', 'page load', 'load time', 'performance', 'speed'] },
  { key: 'missing_https', patterns: ['not https', 'no https', 'missing https', 'http://', 'not secure'] },
  { key: 'mixed_content', patterns: ['mixed content', 'http.*https', 'insecure.*resource'] }
];

// Find matching guidance for a finding
function matchFindingGuidance(name, description, url) {
  var combined = (name + ' ' + description + ' ' + (url || '')).toLowerCase();

  for (var i = 0; i < findingPatterns.length; i++) {
    var patterns = findingPatterns[i].patterns;
    for (var p = 0; p < patterns.length; p++) {
      if (combined.indexOf(patterns[p]) !== -1) {
        return findingGuidance[findingPatterns[i].key];
      }
    }
  }
  return null;
}

// Initialize guidance for all result rows
function initializeFindingGuidance() {
  var rows = document.querySelectorAll('.result-row');
  rows.forEach(function(row, idx) {
    var nameEl = row.querySelector('[data-label="Test"] div:first-child');
    var descEl = row.querySelector('[data-label="Test"] .text-muted');
    var detailsEl = row.querySelector('.cell-details');

    var name = nameEl ? nameEl.textContent : '';
    var desc = descEl ? descEl.textContent : '';
    var details = detailsEl ? detailsEl.textContent : '';

    var guidance = matchFindingGuidance(name, desc, details);

    if (guidance) {
      // Create guidance wrapper
      var wrapper = document.createElement('div');
      wrapper.className = 'finding-guidance-wrapper';
      wrapper.id = 'guidance-' + idx;

      var html = '<button type="button" class="guidance-toggle" onclick="toggleGuidance(\'guidance-' + idx + '\')">';
      html += '<span class="guidance-icon">ℹ️</span> What this means';
      html += '</button>';
      html += '<div class="guidance-content" style="display:none;">';
      html += '<div class="guidance-section">';
      html += '<span class="guidance-label">What This Means</span>';
      html += '<div class="guidance-text">' + guidance.meaning + '</div>';
      html += '</div>';
      html += '<div class="guidance-section">';
      html += '<span class="guidance-label">What To Do</span>';
      html += '<div class="guidance-text">' + guidance.action + '</div>';
      html += '</div>';
      html += '</div>';

      wrapper.innerHTML = html;

      // Insert after the row
      row.parentNode.insertBefore(wrapper, row.nextSibling);
    }
  });
}

// Toggle guidance visibility
function toggleGuidance(wrapperID) {
  var wrapper = document.getElementById(wrapperID);
  var toggle = wrapper.querySelector('.guidance-toggle');
  var content = wrapper.querySelector('.guidance-content');
  var isVisible = content.style.display !== 'none';

  content.style.display = isVisible ? 'none' : 'block';
  wrapper.classList.toggle('visible', !isVisible);
  toggle.classList.toggle('expanded', !isVisible);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
  initializeFindingGuidance();
  /* Auto-apply Issues Only filter on page load */
  if (typeof applyFilters === 'function') applyFilters();
});

/* Back-to-top button */
(function() {
  var btn = document.createElement('button');
  btn.id = 'back-to-top';
  btn.type = 'button';
  btn.setAttribute('aria-label', 'Scroll back to top of page');
  btn.textContent = '↑';
  btn.style.cssText = 'position:fixed;bottom:32px;right:32px;width:40px;height:40px;background:var(--accent);color:var(--bg);border:none;border-radius:50%;font-size:1.2rem;font-weight:bold;cursor:pointer;opacity:0;visibility:hidden;transition:opacity .3s, visibility .3s;z-index:99;display:flex;align-items:center;justify-content:center;';

  function toggleVisibility() {
    if (window.scrollY > 300) {
      btn.style.opacity = '1';
      btn.style.visibility = 'visible';
    } else {
      btn.style.opacity = '0';
      btn.style.visibility = 'hidden';
    }
  }

  btn.addEventListener('click', function() {
    window.scrollTo({top: 0, behavior: 'smooth'});
  });

  btn.addEventListener('mouseenter', function() {
    if (btn.style.visibility === 'visible') {
      btn.style.background = 'var(--accent-hover)';
    }
  });

  btn.addEventListener('mouseleave', function() {
    btn.style.background = 'var(--accent)';
  });

  window.addEventListener('scroll', toggleVisibility);
  document.body.appendChild(btn);
})();

/* -- TOC scroll spy -- */
(function() {
  var tocLinks = document.querySelectorAll('.toc-link');
  var sections = [];
  tocLinks.forEach(function(link) {
    var id = link.getAttribute('data-section');
    var el = document.getElementById(id);
    if (el) sections.push({ id: id, el: el, link: link });
  });
  if (!sections.length) return;

  function onScroll() {
    var scrollY = window.scrollY + 120;
    var active = sections[0];
    for (var i = 0; i < sections.length; i++) {
      if (sections[i].el.offsetTop <= scrollY) active = sections[i];
    }
    tocLinks.forEach(function(l) { l.classList.remove('active'); });
    if (active) active.link.classList.add('active');
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
})();

var reportData = JSON.parse(document.getElementById("reportData-data").textContent);

function downloadJSON() {
  var b = new Blob([JSON.stringify(reportData, null, 2)], {type: 'application/json'});
  var u = URL.createObjectURL(b);
  var a = document.createElement('a');
  a.href = u; a.download = 'audit_' + reportData.run_id + '.json';
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(u);
}

function downloadCSV() {
  var r = reportData.results || [];
  if (!r.length) { alert('No results'); return; }
  var h = ['module','check','status','detail'];
  var c = h.join(',') + '\n';
  r.forEach(function(x) {
    var row = h.map(function(k) {
      return '"' + ((x[k] || '') + '').replace(/"/g, '""') + '"';
    });
    c += row.join(',') + '\n';
  });
  var b = new Blob([c], {type: 'text/csv'});
  var u = URL.createObjectURL(b);
  var a = document.createElement('a');
  a.href = u; a.download = 'audit_' + reportData.run_id + '.csv';
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(u);
}

async function downloadPDF() {
  var btn = document.querySelector('.pill-btn.pill-pdf');
  var origText = btn ? btn.innerHTML : '';
  if (btn) { btn.innerHTML = '⏳ Generating PDF…'; btn.disabled = true; }

  try {
    /* Dynamically load jsPDF + autoTable if not present */
    if (typeof window.jspdf === 'undefined') {
      await new Promise(function(resolve, reject) {
        var s = document.createElement('script');
        s.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js';
        s.onload = resolve; s.onerror = reject;
        document.head.appendChild(s);
      });
    }
    if (typeof window.jspdf.jsPDF.API.autoTable === 'undefined') {
      await new Promise(function(resolve, reject) {
        var s = document.createElement('script');
        s.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.8.2/jspdf.plugin.autotable.min.js';
        s.onload = resolve; s.onerror = reject;
        document.head.appendChild(s);
      });
    }

    var jsPDF = window.jspdf.jsPDF;
    var doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    var pageW = doc.internal.pageSize.getWidth();
    var pageH = doc.internal.pageSize.getHeight();
    var margin = 16;
    var usable = pageW - margin * 2;
    var bottomLimit = pageH - 14;
    var y = 16;

    /* ── Color palette (light/print theme) ─────────── */
    var colors = {
      brand:    [59, 130, 246],   // brand blue (table header bg)
      cardBg:   [245, 247, 250],  // light gray card surface
      altRow:   [248, 250, 252],  // very light gray alt row
      white:    [255, 255, 255],
      text:     [30, 41, 59],     // near-black body text
      heading:  [15, 23, 42],     // darker for headings
      muted:    [100, 116, 139],  // mid gray for subtext
      green:    [22, 163, 74],    // legible green on white
      red:      [220, 38, 38],    // legible red on white
      yellow:   [161, 98, 7],     // dark amber - legible on white
      orange:   [194, 65, 12],    // dark orange - legible on white
      border:   [203, 213, 225],  // soft border on white
      alertBg:  [254, 242, 242]   // soft red wash for alert
    };

    /* ── Helpers ──────────────────────────────────── */
    function roundRect(x, ry, w, h, r, fill, stroke) {
      doc.setFillColor.apply(doc, fill || colors.cardBg);
      if (stroke) doc.setDrawColor.apply(doc, stroke);
      doc.roundedRect(x, ry, w, h, r, r, stroke ? 'FD' : 'F');
    }
    function ensureSpace(needed) {
      if (y + needed > bottomLimit) {
        doc.addPage();
        y = margin;
      }
    }
    function newSection(title, subtitle) {
      ensureSpace(subtitle ? 18 : 12);
      doc.setFontSize(13); doc.setFont('helvetica', 'bold');
      doc.setTextColor.apply(doc, colors.heading);
      doc.text(title, margin, y + 6);
      if (subtitle) {
        doc.setFontSize(8); doc.setFont('helvetica', 'normal');
        doc.setTextColor.apply(doc, colors.muted);
        doc.text(subtitle, margin, y + 11);
        y += 16;
      } else {
        y += 12;
      }
    }
    function truncate(str, n) {
      str = (str == null ? '' : String(str));
      if (str.length <= n) return str;
      return str.substring(0, n - 1).trimEnd() + '…';
    }
    function severityBadgeColor(sev) {
      sev = (sev || '').toLowerCase();
      if (sev === 'critical') return colors.red;
      if (sev === 'high') return colors.orange;
      if (sev === 'medium') return colors.yellow;
      if (sev === 'low') return colors.brand;
      return colors.muted;
    }
    function statusColor(st) {
      st = (st || '').toLowerCase();
      if (st === 'passed') return colors.green;
      if (st === 'failed' || st === 'error') return colors.red;
      if (st === 'warning') return colors.yellow;
      return colors.muted;
    }
    function autoTableShared(extra) {
      return Object.assign({
        margin: { left: margin, right: margin },
        theme: 'plain',
        styles: {
          fontSize: 7,
          cellPadding: 2.5,
          textColor: colors.text,
          lineColor: colors.border,
          lineWidth: 0.2,
          overflow: 'linebreak',
          font: 'helvetica'
        },
        headStyles: {
          fillColor: colors.brand,
          textColor: colors.white,
          fontStyle: 'bold',
          fontSize: 7.5,
          halign: 'left'
        },
        alternateRowStyles: { fillColor: colors.altRow },
        bodyStyles: { fillColor: colors.white }
      }, extra);
    }

    /* ── Header bar ───────────────────────────────── */
    var domain = (reportData.base_url || '').replace(/^https?:\/\//, '');
    var startedAt = (reportData.started_at || '').slice(0, 19);
    var s = reportData.summary || {};
    var totalIssues = (s.failed || 0) + (s.errors || 0) + (s.warnings || 0);
    var critIssues = (s.failed || 0) + (s.errors || 0);
    var score = Math.round(s.pass_rate || 0);
    var scoreColor = score >= 90 ? colors.green : (score >= 70 ? colors.orange : colors.red);

    roundRect(margin, y, usable, 24, 3, colors.cardBg, colors.border);
    doc.setFontSize(17); doc.setFont('helvetica', 'bold');
    doc.setTextColor.apply(doc, colors.heading);
    doc.text('Audit Report', margin + 6, y + 10);
    doc.setFontSize(9); doc.setFont('helvetica', 'normal');
    doc.setTextColor.apply(doc, colors.text);
    doc.text(domain, margin + 6, y + 16);
    doc.setFontSize(8); doc.setTextColor.apply(doc, colors.muted);
    doc.text(startedAt + '  •  ' + (reportData.duration_s || 0) + 's', margin + 6, y + 21);
    /* Score on right of header */
    doc.setFontSize(22); doc.setFont('helvetica', 'bold');
    doc.setTextColor.apply(doc, scoreColor);
    doc.text(score.toString(), pageW - margin - 6, y + 14, { align: 'right' });
    doc.setFontSize(7); doc.setFont('helvetica', 'normal');
    doc.setTextColor.apply(doc, colors.muted);
    doc.text('Overall Score', pageW - margin - 6, y + 20, { align: 'right' });
    y += 30;

    /* ── Executive Summary metrics ─────────────────── */
    var metricCardH = 22;
    var mw = (usable - 12) / 4;
    var metrics = [
      { label: 'Total Issues',    value: totalIssues.toString(),       color: colors.yellow },
      { label: 'Critical Issues', value: critIssues.toString(),        color: colors.red },
      { label: 'Checks Passed',   value: (s.passed || 0).toString(),   color: colors.green },
      { label: 'Scan Duration',   value: (reportData.duration_s || 0) + 's', color: colors.brand }
    ];
    metrics.forEach(function(m, i) {
      var mx = margin + i * (mw + 4);
      roundRect(mx, y, mw, metricCardH, 2, colors.cardBg, colors.border);
      doc.setFontSize(15); doc.setFont('helvetica', 'bold');
      doc.setTextColor.apply(doc, m.color);
      doc.text(m.value, mx + 4, y + 10);
      doc.setFontSize(7); doc.setFont('helvetica', 'normal');
      doc.setTextColor.apply(doc, colors.muted);
      doc.text(m.label, mx + 4, y + 17);
    });
    y += metricCardH + 6;

    /* Alert banner */
    if (critIssues > 0) {
      ensureSpace(14);
      roundRect(margin, y, usable, 12, 2, colors.alertBg, colors.red);
      doc.setFontSize(9); doc.setFont('helvetica', 'bold');
      doc.setTextColor.apply(doc, colors.red);
      doc.text('!  ' + critIssues + ' Critical Issue' + (critIssues !== 1 ? 's' : '') + ' require immediate attention', margin + 6, y + 7.5);
      y += 16;
    }

    /* ── Fix First section ─────────────────────────── */
    var allResults = reportData.results || [];
    var actionable = allResults.filter(function(r) {
      return r.status === 'failed' || r.status === 'error' || r.status === 'warning';
    });
    var sevOrder = ['critical', 'high', 'medium', 'low', 'info'];
    var modOrder = ['security', 'chaos', 'forms', 'availability', 'auth', 'links'];
    function rankKey(r) {
      var sIdx = sevOrder.indexOf((r.severity || '').toLowerCase());
      if (sIdx === -1) sIdx = sevOrder.length;
      var mIdx = modOrder.indexOf((r.module || '').toLowerCase());
      if (mIdx === -1) mIdx = modOrder.length;
      return sIdx * 10 + mIdx;
    }
    var ranked = actionable.slice().sort(function(a, b) { return rankKey(a) - rankKey(b); });
    var fixFirst = ranked.slice(0, 3);

    var impactByModule = {
      security: 'Leaves your site exposed to attacks that can deface pages, inject malware, or leak customer data. Search engines push insecure sites lower in results.',
      chaos:    'Slow load times cost you customers — 53% of mobile visitors abandon pages that take longer than 3 seconds, and search engines rank slow sites lower.',
      forms:    'Broken forms block customers from contacting you, signing up, or completing a purchase — direct lost revenue.',
      availability: 'Pages returning errors mean customers cannot reach parts of your site. Search engines stop indexing broken pages, so they disappear from results.',
      auth:     'Login or session problems lock customers out of their accounts, trigger support tickets, and erode trust in your brand.',
      links:    'Broken links frustrate visitors mid-journey and signal to search engines that your site is not well maintained, dragging down rankings.'
    };

    if (fixFirst.length > 0) {
      newSection('Fix These Things First', fixFirst.length + ' high-impact issue' + (fixFirst.length !== 1 ? 's' : '') + ' — start here for the biggest business impact');
      fixFirst.forEach(function(item, i) {
        var impact = impactByModule[(item.module || '').toLowerCase()] || item.recommendation || 'This issue affects how visitors and search engines experience your site.';
        var sev = (item.severity || 'info').toLowerCase();
        var effort, effortColor;
        if (sev === 'low' || sev === 'info') { effort = 'Quick fix'; effortColor = colors.green; }
        else if (sev === 'medium')           { effort = '~30 minutes'; effortColor = colors.orange; }
        else                                  { effort = 'Needs a developer'; effortColor = colors.red; }

        var titleStr = item.name || '(unnamed check)';
        var titleLines = doc.splitTextToSize(titleStr, usable - 24);
        var impactLines = doc.splitTextToSize(impact, usable - 24);
        var cardH = 14 + titleLines.length * 4.5 + impactLines.length * 4 + 6;
        ensureSpace(cardH + 4);

        roundRect(margin, y, usable, cardH, 3, colors.cardBg, colors.border);
        /* Numbered circle */
        var sevColor = severityBadgeColor(sev);
        doc.setFillColor.apply(doc, sevColor);
        doc.circle(margin + 8, y + 8, 4.5, 'F');
        doc.setFontSize(9); doc.setFont('helvetica', 'bold');
        doc.setTextColor.apply(doc, colors.white);
        doc.text((i + 1).toString(), margin + 8, y + 9.5, { align: 'center' });

        /* Title */
        doc.setFontSize(10); doc.setFont('helvetica', 'bold');
        doc.setTextColor.apply(doc, colors.heading);
        doc.text(titleLines, margin + 16, y + 8);

        /* Severity badge (right-aligned with title row) */
        doc.setFontSize(7); doc.setFont('helvetica', 'bold');
        doc.setTextColor.apply(doc, sevColor);
        doc.text(sev.toUpperCase(), pageW - margin - 6, y + 8, { align: 'right' });

        /* Impact body */
        var bodyY = y + 8 + titleLines.length * 4.5 + 2;
        doc.setFontSize(8); doc.setFont('helvetica', 'normal');
        doc.setTextColor.apply(doc, colors.text);
        doc.text(impactLines, margin + 16, bodyY);

        /* Effort tag */
        var tagY = bodyY + impactLines.length * 4 + 1;
        doc.setFontSize(7); doc.setFont('helvetica', 'bold');
        doc.setTextColor.apply(doc, effortColor);
        doc.text(effort, margin + 16, tagY);
        /* Module label on the right */
        doc.setTextColor.apply(doc, colors.muted);
        doc.setFont('helvetica', 'normal');
        doc.text((item.module || '').toUpperCase(), pageW - margin - 6, tagY, { align: 'right' });

        y += cardH + 4;
      });
      y += 4;
    }

    /* ── Overview (per-module summary) ────────────── */
    var modules = {};
    allResults.forEach(function(r) {
      var m = r.module || 'other';
      if (!modules[m]) modules[m] = { total: 0, passed: 0 };
      modules[m].total++;
      if (r.status === 'passed') modules[m].passed++;
    });
    function rate(m) { return modules[m] ? Math.round((modules[m].passed / modules[m].total) * 100) : null; }
    function combine() {
      var t = 0, p = 0;
      for (var i = 0; i < arguments.length; i++) { var m = modules[arguments[i]]; if (m) { t += m.total; p += m.passed; } }
      return t > 0 ? Math.round((p / t) * 100) : null;
    }
    var perfData = reportData.performance_metrics || {};
    var perfScore = null;
    if (perfData.mobile && perfData.mobile.score != null) perfScore = Math.round(perfData.mobile.score * 100);
    else if (perfData.desktop && perfData.desktop.score != null) perfScore = Math.round(perfData.desktop.score * 100);

    var overviewSections = [];
    if (perfScore !== null) overviewSections.push({ label: 'Performance', score: perfScore });
    var sec = combine('security', 'auth');
    if (sec !== null) overviewSections.push({ label: 'Security', score: sec });
    var avail = rate('availability');
    if (avail !== null) overviewSections.push({ label: 'Availability', score: avail });
    var lf = combine('links', 'forms');
    if (lf !== null) overviewSections.push({ label: 'Links & Forms', score: lf });
    var ch = rate('chaos');
    if (ch !== null) overviewSections.push({ label: 'Resilience', score: ch });

    if (overviewSections.length > 0) {
      newSection('Overview', 'Per-module summary scores');
      var gaugeBlockH = 30;
      ensureSpace(gaugeBlockH + 6);
      roundRect(margin, y, usable, gaugeBlockH, 3, colors.cardBg, colors.border);
      var gCount = overviewSections.length;
      var gSpacing = usable / gCount;
      overviewSections.forEach(function(secItem, i) {
        var gx = margin + gSpacing * (i + 0.5);
        var gy = y + 12;
        var gr = 6;
        var gScore = secItem.score;
        var gColor = gScore >= 90 ? colors.green : (gScore >= 70 ? colors.orange : colors.red);

        doc.setDrawColor.apply(doc, colors.border);
        doc.setLineWidth(1.6);
        doc.circle(gx, gy, gr, 'S');

        doc.setDrawColor.apply(doc, gColor);
        doc.setLineWidth(1.6);
        var startA = -Math.PI / 2;
        var endA = startA + (gScore / 100) * 2 * Math.PI;
        var steps = Math.max(Math.round(gScore / 2), 2);
        for (var st = 0; st < steps; st++) {
          var a1 = startA + (st / steps) * (endA - startA);
          var a2 = startA + ((st + 1) / steps) * (endA - startA);
          doc.line(gx + gr * Math.cos(a1), gy + gr * Math.sin(a1),
                   gx + gr * Math.cos(a2), gy + gr * Math.sin(a2));
        }
        doc.setFontSize(9); doc.setFont('helvetica', 'bold');
        doc.setTextColor.apply(doc, gColor);
        doc.text(gScore.toString(), gx, gy + 1.5, { align: 'center' });
        doc.setFontSize(7); doc.setFont('helvetica', 'normal');
        doc.setTextColor.apply(doc, colors.muted);
        doc.text(secItem.label, gx, gy + gr + 6, { align: 'center' });
      });
      y += gaugeBlockH + 8;
    }

    /* ── Performance (Mobile + Desktop) ─────────── */
    var hasPerf = (perfData.mobile && perfData.mobile.score != null) || (perfData.desktop && perfData.desktop.score != null);
    if (hasPerf) {
      newSection('Performance Metrics', 'Lighthouse Core Web Vitals — mobile and desktop');
      ['mobile', 'desktop'].forEach(function(strategy) {
        var sdata = perfData[strategy];
        if (!sdata || sdata.score == null) return;
        var label = strategy.charAt(0).toUpperCase() + strategy.slice(1);
        var lhScore = Math.round(sdata.score * 100);
        var lhColor = lhScore >= 90 ? colors.green : (lhScore >= 50 ? colors.orange : colors.red);

        ensureSpace(14);
        /* Sub-header bar */
        roundRect(margin, y, usable, 10, 2, colors.cardBg, colors.border);
        doc.setFontSize(10); doc.setFont('helvetica', 'bold');
        doc.setTextColor.apply(doc, colors.heading);
        doc.text(label + ' — Lighthouse Score', margin + 4, y + 6.8);
        doc.setFontSize(11); doc.setTextColor.apply(doc, lhColor);
        doc.text(lhScore.toString(), pageW - margin - 4, y + 6.8, { align: 'right' });
        y += 12;

        /* Metrics table */
        var metricRows = [];
        var metricsObj = sdata.metrics || {};
        Object.keys(metricsObj).forEach(function(mid) {
          var m = metricsObj[mid];
          var mScore = m.score == null ? null : Math.round(m.score * 100);
          metricRows.push([
            m.label || mid,
            m.display || (m.value != null ? String(m.value) : '—'),
            mScore == null ? '—' : (mScore + '/100')
          ]);
        });
        if (metricRows.length > 0) {
          doc.autoTable(autoTableShared({
            startY: y,
            head: [['Metric', 'Value', 'Score']],
            body: metricRows,
            columnStyles: {
              0: { cellWidth: usable * 0.55 },
              1: { cellWidth: usable * 0.25 },
              2: { cellWidth: usable * 0.20, halign: 'right', fontStyle: 'bold' }
            },
            didParseCell: function(data) {
              if (data.section === 'body' && data.column.index === 2) {
                var raw = (data.cell.raw || '').toString();
                var n = parseInt(raw, 10);
                if (!isNaN(n)) {
                  data.cell.styles.textColor = n >= 90 ? colors.green : (n >= 50 ? colors.orange : colors.red);
                }
              }
            }
          }));
          y = doc.lastAutoTable.finalY + 4;
        }

        /* Top recommendations */
        var perfRecs = sdata.recommendations || [];
        if (perfRecs.length > 0) {
          ensureSpace(8);
          doc.setFontSize(9); doc.setFont('helvetica', 'bold');
          doc.setTextColor.apply(doc, colors.heading);
          doc.text('Top Recommendations', margin, y + 4);
          y += 7;
          perfRecs.slice(0, 3).forEach(function(rec) {
            var title = truncate(rec.title || '', 90);
            var desc = truncate(rec.description || '', 220);
            var titleLines = doc.splitTextToSize(title, usable - 8);
            var descLines = doc.splitTextToSize(desc, usable - 8);
            var savings = rec.savings_ms && rec.savings_ms > 0 ? 'Potential savings: ' + (rec.savings_ms / 1000).toFixed(1) + 's' : '';
            var cardH = 5 + titleLines.length * 4 + descLines.length * 3.6 + (savings ? 4 : 0) + 4;
            ensureSpace(cardH + 3);
            var recColor = rec.score == null ? colors.muted : (rec.score < 0.5 ? colors.red : (rec.score < 0.9 ? colors.yellow : colors.green));
            roundRect(margin, y, usable, cardH, 2, colors.altRow, colors.border);
            /* Color indicator stripe */
            doc.setFillColor.apply(doc, recColor);
            doc.rect(margin, y, 1.5, cardH, 'F');
            doc.setFontSize(8.5); doc.setFont('helvetica', 'bold');
            doc.setTextColor.apply(doc, colors.heading);
            doc.text(titleLines, margin + 4, y + 5);
            doc.setFontSize(7.5); doc.setFont('helvetica', 'normal');
            doc.setTextColor.apply(doc, colors.text);
            doc.text(descLines, margin + 4, y + 5 + titleLines.length * 4 + 0.5);
            if (savings) {
              doc.setFontSize(7); doc.setFont('helvetica', 'bold');
              doc.setTextColor.apply(doc, colors.brand);
              doc.text(savings, margin + 4, y + cardH - 2.5);
            }
            y += cardH + 2;
          });
        }
        y += 4;
      });
    }

    /* ── Detailed Results table ──────────────────── */
    if (allResults.length > 0) {
      newSection('Detailed Results', allResults.length + ' total tests');

      var sortOrder = { failed: 0, error: 1, warning: 2, passed: 3, skipped: 4 };
      var sortedResults = allResults.slice().sort(function(a, b) {
        var as = sortOrder[a.status]; if (as == null) as = 9;
        var bs = sortOrder[b.status]; if (bs == null) bs = 9;
        if (as !== bs) return as - bs;
        return rankKey(a) - rankKey(b);
      });

      var tableBody = sortedResults.map(function(r) {
        var details = r.details || r.description || '';
        var rec = r.recommendation || '';
        if (r.url && details.indexOf(r.url) === -1) {
          details = details ? (details + ' — ' + r.url) : r.url;
        }
        return [
          (r.status || '').toUpperCase(),
          (r.severity || '').toUpperCase(),
          r.module || '',
          truncate(r.name || '', 80),
          truncate(details, 280),
          truncate(rec, 220) || '—'
        ];
      });

      doc.autoTable(autoTableShared({
        startY: y,
        head: [['Status', 'Severity', 'Module', 'Check', 'Details', 'Recommendation']],
        body: tableBody,
        columnStyles: {
          0: { cellWidth: 14, halign: 'center', fontStyle: 'bold' },
          1: { cellWidth: 16, halign: 'center', fontStyle: 'bold' },
          2: { cellWidth: 18 },
          3: { cellWidth: 32 },
          4: { cellWidth: 50 },
          5: { cellWidth: usable - 14 - 16 - 18 - 32 - 50 }
        },
        didParseCell: function(data) {
          if (data.section !== 'body') return;
          if (data.column.index === 0) {
            data.cell.styles.textColor = statusColor(data.cell.raw);
          }
          if (data.column.index === 1) {
            data.cell.styles.textColor = severityBadgeColor(data.cell.raw);
          }
        }
      }));
      y = doc.lastAutoTable.finalY + 8;
    }

    /* ── AI Visibility ───────────────────────────── */
    var ai = reportData.ai_visibility;
    if (ai && ai.overall_score != null) {
      newSection('AI Visibility', 'Platform-by-platform appearance in AI search results');

      /* Summary cards row */
      ensureSpace(26);
      var aiScoreColor = ai.overall_score >= 50 ? colors.green : (ai.overall_score >= 25 ? colors.yellow : colors.red);
      var sumW = (usable - 8) / 3;
      var sumH = 22;
      var bizInfo = ai.business_info || {};
      var sumCards = [
        { value: ai.overall_score + '%', label: 'Overall AI Visibility', color: aiScoreColor },
        { value: (ai.total_appearances || 0) + '/' + (ai.total_queries || 0), label: 'Appearances in AI Results', color: colors.heading },
        { value: bizInfo.business_name || '—', label: ((bizInfo.sector || '') + (bizInfo.location ? ' — ' + bizInfo.location : '')) || 'Business', color: colors.heading }
      ];
      sumCards.forEach(function(c, i) {
        var cx = margin + i * (sumW + 4);
        roundRect(cx, y, sumW, sumH, 2, colors.cardBg, colors.border);
        doc.setFontSize(c.value.length > 18 ? 9 : 13); doc.setFont('helvetica', 'bold');
        doc.setTextColor.apply(doc, c.color);
        doc.text(truncate(c.value, 32), cx + sumW / 2, y + 10, { align: 'center' });
        doc.setFontSize(7); doc.setFont('helvetica', 'normal');
        doc.setTextColor.apply(doc, colors.muted);
        doc.text(truncate(c.label, 38), cx + sumW / 2, y + 17, { align: 'center' });
      });
      y += sumH + 6;

      /* Platform scores table */
      var platforms = ai.platform_scores || {};
      var platformRows = [];
      Object.keys(platforms).forEach(function(pname) {
        var p = platforms[pname];
        platformRows.push([
          pname,
          p.score + '%',
          (p.appearances || 0) + '/' + (p.total || 0)
        ]);
      });
      if (platformRows.length > 0) {
        ensureSpace(8);
        doc.setFontSize(9); doc.setFont('helvetica', 'bold');
        doc.setTextColor.apply(doc, colors.heading);
        doc.text('Platform Scores', margin, y + 4);
        y += 7;
        doc.autoTable(autoTableShared({
          startY: y,
          head: [['Platform', 'Score', 'Appearances']],
          body: platformRows,
          columnStyles: {
            0: { cellWidth: usable * 0.45, fontStyle: 'bold' },
            1: { cellWidth: usable * 0.25, halign: 'right', fontStyle: 'bold' },
            2: { cellWidth: usable * 0.30, halign: 'right' }
          },
          didParseCell: function(data) {
            if (data.section === 'body' && data.column.index === 1) {
              var n = parseInt((data.cell.raw || '').toString(), 10);
              if (!isNaN(n)) {
                data.cell.styles.textColor = n >= 50 ? colors.green : (n >= 25 ? colors.yellow : colors.red);
              }
            }
          }
        }));
        y = doc.lastAutoTable.finalY + 6;
      }

      /* All AI query results */
      var aiAll = ai.all_results || [];
      if (aiAll.length > 0) {
        ensureSpace(8);
        doc.setFontSize(9); doc.setFont('helvetica', 'bold');
        doc.setTextColor.apply(doc, colors.heading);
        doc.text('Query Results (' + aiAll.length + ')', margin, y + 4);
        y += 7;

        var aiBody = aiAll.map(function(row) {
          return [
            row.platform || '',
            truncate(row.query || '', 70),
            truncate(row.recommended || '', 110) + (row.is_real === false ? ' (sim)' : ''),
            row.client_appears ? 'Yes' : 'No',
            row.position ? String(row.position) : 'N/A',
            truncate(row.competitors || '', 90),
            (row.visibility_score != null ? row.visibility_score + '%' : '—')
          ];
        });

        doc.autoTable(autoTableShared({
          startY: y,
          head: [['Platform', 'Query', 'Recommended', 'Found', 'Pos', 'Competitors', 'Score']],
          body: aiBody,
          styles: {
            fontSize: 6.5,
            cellPadding: 2,
            textColor: colors.text,
            lineColor: colors.border,
            lineWidth: 0.2,
            overflow: 'linebreak',
            font: 'helvetica'
          },
          columnStyles: {
            0: { cellWidth: 18, fontStyle: 'bold' },
            1: { cellWidth: 32 },
            2: { cellWidth: 42 },
            3: { cellWidth: 12, halign: 'center', fontStyle: 'bold' },
            4: { cellWidth: 10, halign: 'center' },
            5: { cellWidth: 38 },
            6: { cellWidth: usable - 18 - 32 - 42 - 12 - 10 - 38, halign: 'right', fontStyle: 'bold' }
          },
          didParseCell: function(data) {
            if (data.section !== 'body') return;
            if (data.column.index === 3) {
              var v = (data.cell.raw || '').toString();
              data.cell.styles.textColor = v === 'Yes' ? colors.green : colors.red;
            }
            if (data.column.index === 6) {
              var n = parseInt((data.cell.raw || '').toString(), 10);
              if (!isNaN(n)) {
                data.cell.styles.textColor = n >= 75 ? colors.green : (n >= 50 ? colors.yellow : colors.red);
              }
            }
          }
        }));
        y = doc.lastAutoTable.finalY + 6;
      }
    }

    /* ── Footer + page numbers on every page ─────── */
    var totalPages = doc.internal.getNumberOfPages();
    var footY = pageH - 6;
    for (var i = 1; i <= totalPages; i++) {
      doc.setPage(i);
      doc.setFontSize(7); doc.setFont('helvetica', 'normal');
      doc.setTextColor.apply(doc, colors.muted);
      doc.text('Generated by Website Auditor  •  ' + domain, margin, footY);
      doc.text('Page ' + i + ' of ' + totalPages, pageW - margin, footY, { align: 'right' });
    }

    doc.save('audit_' + reportData.run_id + '.pdf');
  } catch (e) {
    console.error('PDF generation failed:', e);
    alert('PDF generation failed. Please try again.');
  } finally {
    if (btn) { btn.innerHTML = origText; btn.disabled = false; }
  }
}

function copyShareLink() {
  var url = window.location.href;
  var btn = document.getElementById('share-link-btn');
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(url).then(function() {
      btn.textContent = '✓ Copied!';
      setTimeout(function() { btn.textContent = 'Copy Link'; }, 2000);
    }).catch(function() {
      fallbackCopy(url, btn);
    });
  } else {
    fallbackCopy(url, btn);
  }
}

function fallbackCopy(text, btn) {
  var ta = document.createElement('textarea');
  ta.value = text;
  ta.style.cssText = 'position:fixed;left:-9999px;';
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand('copy');
    btn.textContent = '✓ Copied!';
    setTimeout(function() { btn.textContent = 'Copy Link'; }, 2000);
  } catch(e) {
    prompt('Copy this link:', text);
  }
  document.body.removeChild(ta);
}

/* Wire up the report top-bar action pills (CSP-compliant; no inline handlers) */
(function initReportActionPills() {
  var shareBtn = document.getElementById('share-link-btn');
  if (shareBtn) shareBtn.addEventListener('click', copyShareLink);

  var pdfBtn = document.querySelector('.pill-btn.pill-pdf');
  if (pdfBtn) pdfBtn.addEventListener('click', downloadPDF);

  var scheduleBtn = document.querySelector('.pill-btn.pill-schedule');
  if (scheduleBtn) scheduleBtn.addEventListener('click', function() {
    /* Send the user back to the home page where they can submit a new audit */
    window.location.href = '/';
  });
})();