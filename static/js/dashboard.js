function toggleProdWarning() {
  var env = document.getElementById('environment').value;
  document.getElementById('prod-warning').classList.toggle('hidden', env !== 'production');
}

/* -- Inline progress overlay for BUG-018 -------------------------------- */
function showLaunchProgress() {
  // Create overlay if it doesn't exist
  var overlay = document.getElementById('launch-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'launch-overlay';
    overlay.setAttribute('role', 'status');
    overlay.setAttribute('aria-live', 'polite');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(15,23,42,0.88);z-index:100;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:20px;';

    var spinner = document.createElement('div');
    spinner.style.cssText = 'width:48px;height:48px;border:4px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:launchSpin 0.8s linear infinite;';

    var msg = document.createElement('div');
    msg.id = 'launch-msg';
    msg.style.cssText = 'color:var(--accent);font-size:1.1rem;font-weight:600;text-align:center;';
    msg.textContent = 'Launching audit...';

    var sub = document.createElement('div');
    sub.id = 'launch-sub';
    sub.style.cssText = 'color:var(--text-muted);font-size:0.85rem;text-align:center;max-width:400px;';
    sub.textContent = 'Initializing crawler and test modules. You will be redirected to the progress page shortly.';

    var bar = document.createElement('div');
    bar.style.cssText = 'width:200px;height:4px;background:var(--border);border-radius:2px;overflow:hidden;';
    var fill = document.createElement('div');
    fill.style.cssText = 'width:0%;height:100%;background:var(--accent);border-radius:2px;transition:width 0.5s;';
    fill.id = 'launch-bar-fill';
    bar.appendChild(fill);

    overlay.appendChild(spinner);
    overlay.appendChild(msg);
    overlay.appendChild(sub);
    overlay.appendChild(bar);
    document.body.appendChild(overlay);

    // Add keyframes if not present
    if (!document.getElementById('launch-spin-style')) {
      var style = document.createElement('style');
      style.id = 'launch-spin-style';
      style.textContent = '@keyframes launchSpin { to { transform: rotate(360deg); } }';
      document.head.appendChild(style);
    }
  }
  overlay.style.display = 'flex';

  // Animate the progress bar
  var fill = document.getElementById('launch-bar-fill');
  setTimeout(function() { fill.style.width = '30%'; }, 200);
  setTimeout(function() { fill.style.width = '60%'; }, 800);
  setTimeout(function() { fill.style.width = '80%'; }, 1500);
}

function hideLaunchProgress() {
  var overlay = document.getElementById('launch-overlay');
  if (overlay) overlay.style.display = 'none';
}

function updateLaunchMsg(msg, sub) {
  var el = document.getElementById('launch-msg');
  if (el) el.textContent = msg;
  var subEl = document.getElementById('launch-sub');
  if (subEl && sub) subEl.textContent = sub;
}

// Intercept form submit to use JSON + X-Requested-With (avoids CSRF cookie issues with proxied domains)
document.getElementById('runForm').addEventListener('submit', function(e) {
  e.preventDefault();
  var form = e.target;
  var btn = form.querySelector('button[type="submit"]');
  var origText = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Starting...';

  // Show the full-screen progress overlay immediately
  showLaunchProgress();

  var data = {};
  var formData = new FormData(form);
  formData.forEach(function(value, key) {
    if (key === 'csrf_token') return;
    if (form.querySelector('[name="' + key + '"]') && form.querySelector('[name="' + key + '"]').type === 'checkbox') {
      data[key] = form.querySelector('[name="' + key + '"]').checked;
    } else {
      data[key] = value;
    }
  });

  console.log("[DEBUG] Sending data:", JSON.stringify(data));
  fetch('/run', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest'
    },
    body: JSON.stringify(data)
  })
  .then(function(r) {
    if (!r.ok) return r.json().then(function(d) { throw new Error(d.error || r.statusText); });
    updateLaunchMsg('Audit started!', 'Redirecting to progress page...');
    var fill = document.getElementById('launch-bar-fill');
    if (fill) fill.style.width = '100%';
    setTimeout(function() { window.location.href = '/progress'; }, 600);
  })
  .catch(function(err) {
    hideLaunchProgress();
    alert('Failed to start: ' + err.message);
    btn.disabled = false;
    btn.textContent = origText;
  });
});
