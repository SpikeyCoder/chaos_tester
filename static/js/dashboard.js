function toggleProdWarning() {
  var env = document.getElementById('environment').value;
  document.getElementById('prod-warning').classList.toggle('hidden', env === 'production');
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
  var origText = btn ? btn.textContent : 'Audit Website';

  /* ── Sync override fields into hidden form fields ── */
  var bizNameInput = document.getElementById('override_biz_name');
  var bizHidden = document.getElementById('business_name');
  if (bizNameInput && bizNameInput.value.trim() && bizHidden) {
    bizHidden.value = bizNameInput.value.trim();
  }

  var overrideCityInput = document.getElementById('override_biz_city');
  var locInput = document.getElementById('business_location');
  if (overrideCityInput && overrideCityInput.value.trim() && locInput) {
    locInput.value = overrideCityInput.value.trim();
  }

  /* Sync city from promoted quick_city field into hidden form field */
  var quickCity = document.getElementById('quick_city');
  if (quickCity && quickCity.value.trim() && locInput && !locInput.value.trim()) {
    locInput.value = quickCity.value.trim();
  }

  /* ── Validate: city/location is required ── */
  if (locInput && !locInput.value.trim()) {
    if (typeof showCityField === 'function') showCityField(false);
    return;
  }

  /* ── Normalize URL: auto-add https:// if missing ── */
  var urlField = document.getElementById('base_url');
  if (urlField) {
    var urlVal = urlField.value.trim();
    if (urlVal && !/^https?:\/\//i.test(urlVal)) {
      urlField.value = 'https://' + urlVal;
    }
  }

  /* ── Validate: URL is required ── */
  if (!urlField || !urlField.value.trim()) {
    urlField.focus();
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.style.opacity = '0.7';
    btn.innerHTML = '<span style="display:inline-block;width:16px;height:16px;border:2px solid rgba(255,255,255,0.3);border-top-color:#fff;border-radius:50%;animation:spin .6s linear infinite;vertical-align:middle;margin-right:8px;"></span> Running Audit...';
  }

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

  /* ── Ensure base_url in payload has the normalized value ──
     On some mobile browsers, FormData may read the pre-normalization value
     from type="url" inputs even after we set urlField.value above.
     Explicitly overwrite with the (already-normalised) DOM value. */
  if (urlField) {
    data.base_url = urlField.value.trim();
  }

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
    if (btn) {
      btn.disabled = false;
      btn.style.opacity = '1';
      btn.textContent = origText;
    }
  });
});
