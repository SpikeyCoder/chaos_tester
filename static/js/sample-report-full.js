document.addEventListener('DOMContentLoaded', function() {
  var sections = [
    { label: 'Performance', score: 96 },
    { label: 'Security', score: 90 },
    { label: 'Availability', score: 90 },
    { label: 'Links & Forms', score: 95 },
    { label: 'Resilience', score: 100 }
  ];
  var container = document.getElementById('sectionGauges');
  if (!container) return;
  sections.forEach(function(sec) {
    var score = sec.score;
    var color = score >= 90 ? '#4ade80' : (score >= 70 ? '#f97316' : '#ef4444');
    var r = 44, stroke = 7, circ = 2 * Math.PI * r;
    var offset = circ - (score / 100) * circ;
    // Native SVG <text> for the score — same approach as report-page.js so
    // sample and live reports stay visually identical.
    var html = '<div class="section-gauge-item">' +
      '<div class="gauge-ring">' +
        '<svg viewBox="0 0 100 100" width="110" height="110" aria-hidden="true" focusable="false">' +
          '<circle cx="50" cy="50" r="' + r + '" fill="none" stroke="rgba(51,65,85,0.6)" stroke-width="' + stroke + '"/>' +
          '<circle cx="50" cy="50" r="' + r + '" fill="none" stroke="' + color + '" stroke-width="' + stroke + '" ' +
            'stroke-dasharray="' + circ + '" stroke-dashoffset="' + offset + '" ' +
            'stroke-linecap="round" transform="rotate(-90 50 50)"/>' +
          '<text x="50" y="50" text-anchor="middle" dominant-baseline="central" ' +
            'fill="' + color + '" font-size="26" font-weight="700" ' +
            'font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif">' +
            score +
          '</text>' +
        '</svg>' +
      '</div>' +
      '<div class="gauge-label-text">' + sec.label + '</div>' +
    '</div>';
    container.insertAdjacentHTML('beforeend', html);
  });
});

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

// Arrow-key keyboard nav for the Performance tablist (WCAG 2.1)
(function() {
  var tablist = document.querySelector('.perf-tabs[role="tablist"]');
  if (!tablist) return;
  var tabs = Array.prototype.slice.call(tablist.querySelectorAll('[role="tab"]'));
  tabs.forEach(function(tab, i) {
    tab.addEventListener('keydown', function(e) {
      var next = null;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = tabs[(i + 1) % tabs.length];
      else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = tabs[(i - 1 + tabs.length) % tabs.length];
      else if (e.key === 'Home') next = tabs[0];
      else if (e.key === 'End') next = tabs[tabs.length - 1];
      if (next) {
        e.preventDefault();
        switchPerfTab(next.id.replace('tab-', ''));
        next.focus();
      }
    });
  });
})();

(function() {
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

    var PAD = big ? 20 : 14;
    var W = 200 + PAD * 2, H = big ? 150 : 134;
    var CX = 100 + PAD, CY = big ? 115 : 104;
    var R  = big ? 80 : 70;
    var SW = big ? 16 : 12;
    var ARC = Math.PI * R;

    var gP, yP, rP;
    if (cfg.rev) {
      gP = (cfg.max - cfg.g) / cfg.max;
      yP = (cfg.g - cfg.y) / cfg.max;
      rP = cfg.y / cfg.max;
    } else {
      gP = cfg.g / cfg.max;
      yP = (cfg.y - cfg.g) / cfg.max;
      rP = (cfg.max - cfg.y) / cfg.max;
    }
    var gL = gP * ARC, yL = yP * ARC, rL = rP * ARC;

    var nPos;
    if (cfg.rev) {
      nPos = Math.max(0, Math.min(1, (cfg.max - value) / cfg.max));
    } else {
      nPos = Math.max(0, Math.min(1, value / cfg.max));
    }
    var needleDeg = -90 + nPos * 180;

    var nCol;
    if (nPos <= gP + 0.001) nCol = '#0cce6b';
    else if (nPos <= gP + yP + 0.001) nCol = '#ffa400';
    else nCol = '#ff4e42';

    var svg = el('svg', {viewBox: '0 0 ' + W + ' ' + H});
    svg.style.width = '100%';
    svg.style.maxWidth = big ? '260px' : '195px';

    var arcD = 'M ' + (CX - R) + ',' + CY +
               ' A ' + R + ',' + R + ' 0 0,1 ' + (CX + R) + ',' + CY;

    svg.appendChild(el('path', {
      d: arcD, fill: 'none', stroke: 'rgba(255,255,255,0.06)',
      'stroke-width': SW, 'stroke-linecap': 'butt'
    }));

    svg.appendChild(el('path', {
      d: arcD, fill: 'none', stroke: '#0cce6b',
      'stroke-width': SW, 'stroke-linecap': 'butt',
      'stroke-dasharray': gL + ' ' + (ARC * 3)
    }));

    svg.appendChild(el('path', {
      d: arcD, fill: 'none', stroke: '#ffa400',
      'stroke-width': SW, 'stroke-linecap': 'butt',
      'stroke-dasharray': '0.001 ' + gL + ' ' + yL + ' ' + (ARC * 3)
    }));

    svg.appendChild(el('path', {
      d: arcD, fill: 'none', stroke: '#ff4e42',
      'stroke-width': SW, 'stroke-linecap': 'butt',
      'stroke-dasharray': '0.001 ' + (gL + yL) + ' ' + rL + ' ' + (ARC * 3)
    }));

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

    var NL = R - 16;
    var nw = big ? 4.5 : 3.5;

    var g = el('g', {transform: 'rotate(' + needleDeg + ', ' + CX + ', ' + CY + ')'});

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

    g.appendChild(el('polygon', {
      points: [
        (CX - nw * 0.6) + ',' + CY,
        (CX + nw * 0.6) + ',' + CY,
        (CX + nw * 0.4) + ',' + (CY + 10),
        (CX - nw * 0.4) + ',' + (CY + 10)
      ].join(' '),
      fill: '#555', opacity: '0.7'
    }));

    g.appendChild(el('circle', {
      cx: CX, cy: CY, r: big ? 7 : 5.5,
      fill: '#555', stroke: '#777', 'stroke-width': '1.5'
    }));

    svg.appendChild(g);

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

  document.querySelectorAll('.gauge-container').forEach(drawGauge);
})();

let currentStatus = 'all';
let currentModule = 'all';
let _detailedExpanded = false;
let _aiExpanded = false;

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
  document.querySelectorAll('.result-row').forEach(function(row, i) {
    var matchStatus = currentStatus === 'all' || row.dataset.status === currentStatus;
    var matchModule = currentModule === 'all' || row.dataset.module === currentModule;
    if (isFiltering) {
      row.style.display = (matchStatus && matchModule) ? '' : 'none';
    } else if (_detailedExpanded) {
      row.style.display = (matchStatus && matchModule) ? '' : 'none';
    } else {
      row.style.display = (matchStatus && matchModule && i < 5) ? '' : 'none';
    }
  });
}

function toggleDetailedResults() {
  _detailedExpanded = !_detailedExpanded;
  var btn = document.getElementById('detailed-toggle-btn');
  btn.setAttribute('aria-expanded', _detailedExpanded ? 'true' : 'false');
  btn.textContent = _detailedExpanded ? 'Show First 5 Results \u25B2' : 'Show All 94 Results \u25BC';
  applyFilters();
}

function toggleResultDetail(row) {
  var cell = row.querySelector('.result-detail-cell');
  var chevron = row.querySelector('.expand-chevron');
  if (!cell) return;
  var isOpen = cell.style.display !== 'none';
  cell.style.display = isOpen ? 'none' : '';
  if (chevron) chevron.style.transform = isOpen ? '' : 'rotate(90deg)';
}

function toggleAIResults() {
  _aiExpanded = !_aiExpanded;
  var btn = document.getElementById('ai-toggle-btn');
  btn.textContent = _aiExpanded ? 'Show First 4 Results \u25B2' : 'Show All 32 Results \u25BC';
  document.querySelectorAll('.ai-result-row').forEach(function(row, i) {
    row.style.display = _aiExpanded ? '' : (i < 4 ? '' : 'none');
  });
}

function scrollToResults(filter) {
  var el = document.getElementById('detailed-results-card');
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  if (filter && filter !== 'all') {
    var btn = document.querySelector('.filter-btn[data-filter="' + filter + '"]');
    if (btn) filterResults(filter, btn);
  }
}

function downloadPDF() {
  var style = document.createElement('style');
  style.id = 'pdf-print-style';
  style.textContent = '@media print { .report-action-pills, nav, footer, .filter-bar { display: none !important; } body { background: #fff !important; color: #111 !important; } .card, .stat-card { border: 1px solid #ddd !important; background: #fff !important; } .badge { border: 1px solid #999; } @page { margin: 1cm; } }';
  document.head.appendChild(style);
  window.print();
  setTimeout(function() { var ps = document.getElementById('pdf-print-style'); if (ps) ps.remove(); }, 1000);
}

function copyShareLink() {
  var url = window.location.href;
  var btn = document.getElementById('share-link-btn');
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(url).then(function() {
      btn.innerHTML = '\u2713 Copied!';
      setTimeout(function() { btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg> Share'; }, 2000);
    });
  }
}