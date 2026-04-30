var reportData = JSON.parse(document.getElementById("report-data").textContent);

// ── Report page scripts (extracted for CSP) ──

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
      '<div class="gauge-ring u-33975c"u-33975c">' +
        '<svg viewBox="0 0 100 100" width="110" height="110" aria-hidden="true" focusable="false">' +
          '<circle cx="50" cy="50" r="' + r + '" fill="none" stroke="rgba(51,65,85,0.6)" stroke-width="' + stroke + '"/>' +
          '<circle cx="50" cy="50" r="' + r + '" fill="none" stroke="' + color + '" stroke-width="' + stroke + '" ' +
            'stroke-dasharray="' + circ + '" stroke-dashoffset="' + offset + '" ' +
            'stroke-linecap="round" transform="rotate(-90 50 50)" ' +
            'style="transition:stroke-dashoffset 1s ease;"/>' +
        '</svg>' +
        '<div class="u-0a898d">' +
          '<span class="u-1f3ad7">' + score + '</span>' +
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
    html += '<div class="u-3922d6">';
    html += '<span class="u-b86d40">' + r.icon + '</span>';
    html += '<div><div class="u-e6f0a0">' + r.title + '</div>';
    html += '<div class="u-912e7c">' + r.text + '</div></div></div>';
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
    var html = '<div class="u-86a9f6">';
    data.results.forEach(function(r) {
      var color = r.client_appears ? 'var(--green)' : 'var(--red)';
      html += '<div class="u-d4ac60">';
      html += '<div class="u-21e3fb">';
      html += '<img src="' + r.platform_logo_url + '" width="18" height="18" alt="' + r.platform + '"> ' + r.platform + '</div>';
      html += '<div class="u-32f230">';
      if (r.client_appears) {
        html += '<span class="badge badge-passed">Found at #' + r.position + '</span>';
      } else {
        html += '<span class="badge badge-failed">Not found</span>';
      }
      html += '</div>';
      html += '<div class="u-e91b5f"><strong>Recommended:</strong> ' + r.recommended + '</div>';
      html += '</div>';
    });
    html += '</div>';
    resultsEl.innerHTML = html;
    resultsEl.style.display = 'block';
  })
  .catch(function(err) {
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

      var html = '<button type="button" class="guidance-toggle">';
      html += '<span class="guidance-icon">ℹ️</span> What this means';
      html += '</button>';
      html += '<div class="guidance-content u-93b8ea"u-93b8ea">';
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
