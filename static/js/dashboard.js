function toggleProdWarning() {
  var env = document.getElementById('environment').value;
  document.getElementById('prod-warning').classList.toggle('hidden', env !== 'production');
}

// Intercept form submit to use JSON + X-Requested-With (avoids CSRF cookie issues with proxied domains)
document.getElementById('runForm').addEventListener('submit', function(e) {
  e.preventDefault();
  var form = e.target;
  var btn = form.querySelector('button[type="submit"]');
  var origText = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Starting...';

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
    window.location.href = '/progress';
  })
  .catch(function(err) {
    alert('Failed to start: ' + err.message);
    btn.disabled = false;
    btn.textContent = origText;
  });
});
