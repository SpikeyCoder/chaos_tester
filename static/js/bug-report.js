var bugReport = (function() {
  var overlay, form, desc, charCount, errorBanner, formView, successView;
  var featureCheckbox, screenshotCheckbox;

  function init() {
    overlay = document.getElementById('bugOverlay');
    form = document.getElementById('bugForm');
    desc = document.getElementById('bugDesc');
    charCount = document.getElementById('bugCharCount');
    errorBanner = document.getElementById('bugError');
    formView = document.getElementById('bugFormView');
    featureCheckbox = document.getElementById('bugIsFeature');
    screenshotCheckbox = document.getElementById('bugScreenshot');

    if (!overlay) return;

    // Bind open button
    var openBtn = document.querySelector('.bug-btn');
    if (openBtn) openBtn.addEventListener('click', open);

    // Bind overlay backdrop click
    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) close();
    });

    // Bind close button
    var closeBtn = overlay.querySelector('.bug-modal-close');
    if (closeBtn) closeBtn.addEventListener('click', close);

    // Bind form submit
    if (form) form.addEventListener('submit', submit);

    // Bind feature toggle
    if (featureCheckbox) featureCheckbox.addEventListener('change', toggleType);

    // Bind char counter
    if (desc) {
      desc.addEventListener('input', function() {
        if (charCount) charCount.textContent = desc.value.length;
      });
    }
  }

  // Capture console errors
  var recentErrors = [];
  var origError = console.error;
  console.error = function() {
    recentErrors.push(Array.from(arguments).join(' '));
    if (recentErrors.length > 5) recentErrors.shift();
    origError.apply(console, arguments);
  };

  function open() {
    if (overlay) overlay.classList.add('open');
  }

  function close() {
    if (overlay) overlay.classList.remove('open');
    // Reset form
    if (form) form.reset();
    if (charCount) charCount.textContent = '0';
    if (errorBanner) errorBanner.style.display = 'none';
  }

  function toggleType() {
    var icon = document.getElementById('bugIcon');
    var title = document.getElementById('bugTitle');
    if (featureCheckbox && featureCheckbox.checked) {
      if (icon) icon.textContent = 'Feature';
      if (title) title.textContent = 'Request a Feature';
      if (desc) desc.placeholder = 'Describe the feature you would like...';
    } else {
      if (icon) icon.textContent = 'Bug';
      if (title) title.textContent = 'Report a Bug';
      if (desc) desc.placeholder = 'Describe the bug or issue you experienced...';
    }
  }

  function submit(e) {
    e.preventDefault();
    if (!desc || !desc.value.trim()) return;

    var submitBtn = form.querySelector('.submit-btn');
    if (submitBtn) submitBtn.disabled = true;

    var techCtx = {
      url: window.location.href,
      pageName: document.title,
      deviceType: window.innerWidth < 768 ? 'mobile' : 'desktop',
      userAgent: navigator.userAgent,
      platform: navigator.platform || '',
      viewportSize: window.innerWidth + 'x' + window.innerHeight,
      screenSize: screen.width + 'x' + screen.height,
      timestamp: new Date().toISOString(),
      recentErrors: recentErrors.slice(-5)
    };

    var payload = {
      description: desc.value.trim(),
      isFeatureRequest: featureCheckbox ? featureCheckbox.checked : false,
      technicalContext: techCtx,
      screenshotData: null
    };

    function send(data) {
      fetch('/api/bug-report', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify(data)
      })
      .then(function(r) { return r.json(); })
      .then(function(resp) {
        if (resp.ok) {
          if (formView) formView.innerHTML = '<div class="status-msg success">Thanks! Your report has been submitted.</div>';
          setTimeout(close, 2000);
        } else {
          showError(resp.error || 'Submission failed');
        }
      })
      .catch(function(err) {
        showError('Network error: ' + err.message);
      })
      .finally(function() {
        if (submitBtn) submitBtn.disabled = false;
      });
    }

    // Capture screenshot if requested
    if (screenshotCheckbox && screenshotCheckbox.checked && typeof html2canvas !== 'undefined') {
      overlay.style.display = 'none';
      html2canvas(document.body, { scale: 0.5, logging: false }).then(function(canvas) {
        payload.screenshotData = canvas.toDataURL('image/png', 0.6);
        overlay.style.display = '';
        overlay.classList.add('open');
        send(payload);
      }).catch(function() {
        overlay.style.display = '';
        overlay.classList.add('open');
        send(payload);
      });
    } else {
      send(payload);
    }
  }

  function showError(msg) {
    if (errorBanner) {
      errorBanner.textContent = msg;
      errorBanner.style.display = 'block';
    }
  }

  document.addEventListener('DOMContentLoaded', init);

  return { open: open, close: close, submit: submit, toggleType: toggleType };
})();
