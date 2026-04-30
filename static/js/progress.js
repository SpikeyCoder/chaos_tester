const bar = document.getElementById('progressBar');
const pct = document.getElementById('progressPct');
const txt = document.getElementById('progressText');
const log = document.getElementById('logBox');
const reportBtn = document.getElementById('viewReportBtn');
const spinner = document.getElementById('runSpinner');

const moduleColors = {
  availability: '#3b82f6',
  links: '#a855f7',
  forms: '#06b6d4',
  chaos: '#f97316',
  auth: '#eab308',
  security: '#ef4444',
  performance: '#10b981',
  ai_visibility: '#8b5cf6',
  runner: '#22c55e',
  done: '#22c55e',
};

const source = new EventSource('/stream');
source.onmessage = function(event) {
  const data = JSON.parse(event.data);
  const color = moduleColors[data.module] || '#8b8fa3';

  bar.style.width = data.pct + '%';
  pct.textContent = data.pct + '%';
  txt.textContent = data.msg;

  const line = document.createElement('div');

  const modSpan = document.createElement('span');
  modSpan.style.cssText = 'color:' + color + ';font-weight:600;';
  modSpan.textContent = '[' + data.module + ']';

  const tsSpan = document.createElement('span');
  tsSpan.style.color = 'var(--text-muted)';
  tsSpan.textContent = ' ' + (data.ts && typeof WATime !== 'undefined' ? WATime.timeFromISO(data.ts) : (data.ts ? data.ts.substring(11, 19) : '')) + ' ';

  const msgSpan = document.createElement('span');
  msgSpan.textContent = data.msg;

  /* Highlight retry messages */
  if (data.msg && data.msg.includes('retrying')) {
    line.style.cssText = 'background:rgba(234,179,8,0.12);border-radius:4px;padding:2px 6px;margin:4px 0;';
  }

  line.appendChild(modSpan);
  line.appendChild(tsSpan);
  line.appendChild(msgSpan);
  log.appendChild(line);
  log.scrollTop = log.scrollHeight;

  /* Update live check items */
  var checkItem = document.querySelector('.check-item[data-module="' + data.module + '"]');
  if (checkItem) {
    var icon = checkItem.querySelector('.check-icon');
    var label = checkItem.querySelector('span:last-child');
    if (!checkItem.classList.contains('check-active') && data.module !== 'done' && data.module !== 'runner') {
      checkItem.classList.add('check-active');
      icon.style.background = color;
      icon.style.color = '#fff';
      icon.innerHTML = '<span class="spinner" style="width:14px;height:14px;border-width:2px;margin:0;"></span>';
      label.style.color = 'var(--text)';
      label.style.fontWeight = '600';
      checkItem.style.borderColor = color;
    }
  }
  /* Mark previous module as complete if a new one started */
  var allChecks = document.querySelectorAll('.check-item.check-active');
  allChecks.forEach(function(item) {
    if (item.getAttribute('data-module') !== data.module && data.module !== 'done' && data.module !== 'runner') {
      var ic = item.querySelector('.check-icon');
      if (ic && !item.classList.contains('check-done')) {
        item.classList.add('check-done');
        ic.style.background = 'rgba(74,222,128,0.15)';
        ic.style.color = '#4ade80';
        ic.innerHTML = '✓';
      }
    }
  });

  if (data.module === 'done') {
    source.close();
    spinner.style.display = 'none';
    reportBtn.style.display = 'inline-flex';
    if (data.run_id) { reportBtn.href = '/report/' + data.run_id; }

    /* Mark all check items as complete */
    document.querySelectorAll('.check-item').forEach(function(item) {
      var ic = item.querySelector('.check-icon');
      if (ic) {
        ic.style.background = data.msg === 'completed' ? 'rgba(74,222,128,0.15)' : 'rgba(248,113,113,0.15)';
        ic.style.color = data.msg === 'completed' ? '#4ade80' : '#f87171';
        ic.innerHTML = data.msg === 'completed' ? '✓' : '✗';
      }
      item.style.borderColor = data.msg === 'completed' ? 'rgba(74,222,128,0.3)' : 'rgba(248,113,113,0.3)';
    });
    /* Stop shimmer animation on progress bar */
    document.getElementById('progressBar').style.animation = 'none';
    document.getElementById('progressBar').style.background = data.msg === 'completed' ? '#4ade80' : '#f87171';

    if (data.msg === 'completed') {
      pct.style.color = 'var(--green)';
      txt.textContent = 'All tests complete!';
    } else if (data.msg === 'idle') {
      /* Status is idle -- but the run may still be starting up.
         Fall back to polling /api/status before giving up. */
      reportBtn.style.display = 'none';
      txt.textContent = 'Waiting for run to start…';
      startPollingFallback();
      return; /* keep spinner running during polling */
    } else {
      pct.style.color = 'var(--red)';
      txt.textContent = 'Run failed after all retry attempts -- see logs for details.';
      reportBtn.textContent = '📊 View Partial Report';
    }

    /* Update stepper to show Report step as active */
    var stepperDots = document.querySelectorAll('nav[aria-label="Audit progress"] div[style*="border-radius:50%"]');
    if (stepperDots.length >= 3) {
      /* Step 2: mark complete */
      stepperDots[1].className = '';
      stepperDots[1].style.background = 'rgba(74,222,128,0.15)';
      stepperDots[1].style.color = '#4ade80';
      stepperDots[1].textContent = '✓';
      stepperDots[1].nextElementSibling.style.color = '#4ade80';
      /* Step 3: make active */
      stepperDots[2].style.background = 'var(--accent)';
      stepperDots[2].style.color = '#fff';
      stepperDots[2].style.borderColor = 'var(--accent)';
      stepperDots[2].nextElementSibling.style.color = 'var(--accent)';
      stepperDots[2].nextElementSibling.style.fontWeight = '600';
      /* Connector line */
      var connectors = document.querySelectorAll('nav[aria-label="Audit progress"] div[style*="height:2px"]');
      if (connectors.length >= 2) {
        connectors[1].style.background = 'linear-gradient(90deg, var(--accent), var(--accent))';
      }
    }
  }
};

source.onerror = function() {
  source.close();
  /* Don't give up immediately -- fall back to polling /api/status */
  txt.textContent = 'Reconnecting…';
  startPollingFallback();
};

/* Fallback: if SSE fails or returns idle prematurely, poll /api/status */
function startPollingFallback() {
  let polls = 0;
  const maxPolls = 20; /* poll for up to ~30 seconds */
  const interval = setInterval(async () => {
    polls++;
    try {
      const resp = await fetch('/api/status');
      const data = await resp.json();
      if (data.status === 'running') {
        /* Run is active! Reconnect SSE */
        clearInterval(interval);
        txt.textContent = 'Run detected -- reconnecting stream…';
        setTimeout(() => { location.reload(); }, 1000);
      } else if (data.status === 'completed' && data.current_run_id) {
        clearInterval(interval);
        spinner.style.display = 'none';
        pct.style.color = 'var(--green)';
        pct.textContent = '100%';
        txt.textContent = 'All tests complete!';
        reportBtn.style.display = 'inline-flex';
        reportBtn.href = '/report/' + data.current_run_id;
      } else if (polls >= maxPolls) {
        clearInterval(interval);
        spinner.style.display = 'none';
        txt.textContent = 'No active run detected. Return to Dashboard to start one.';
      }
    } catch (e) {
      if (polls >= maxPolls) {
        clearInterval(interval);
        spinner.style.display = 'none';
        txt.textContent = 'Connection lost. Refresh to check status.';
      }
    }
  }, 1500);
}