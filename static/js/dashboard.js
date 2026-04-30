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
    var cityErr = document.getElementById('city-error');
    if (cityErr) cityErr.style.display = 'block';
    var cityInput = document.getElementById('override_biz_city');
    if (cityInput) {
      cityInput.style.borderColor = '#f87171';
      cityInput.focus();
      cityInput.addEventListener('input', function clearCityErr() {
        cityInput.style.borderColor = '';
        if (cityErr) cityErr.style.display = 'none';
        cityInput.removeEventListener('input', clearCityErr);
      });
    }
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


// ── Extracted from inline scripts ──

/* ── Business name detection + city detection ────────────────────── */
var _detectTimer = null;
var _blurTimer = null;
var _lastDetectedUrl = '';
var _overrideListenerAdded = false;
var _isMobile = /Mobi|Android|iPhone|iPad|iPod|webOS/i.test(navigator.userAgent) || ('ontouchstart' in window);

/* State tracking for business detection */
var _detectedBizName = '';
var _detectedCity = '';
var _cityWasAutoDetected = false;

function enableAuditBtn() {
  var btn = document.getElementById('auditBtn');
  if (!btn) return;
  btn.disabled = false;
  btn.style.opacity = '1';
  btn.style.cursor = 'pointer';
}

function disableAuditBtn() {
  var btn = document.getElementById('auditBtn');
  if (!btn) return;
  btn.disabled = true;
  btn.style.opacity = '0.5';
  btn.style.cursor = 'not-allowed';
}

/* ── Slide-panel helpers ─────────────────────────────────────────── */
function slideDown(el) {
  el.style.display = 'block';
  void el.offsetHeight;
  el.style.maxHeight = '300px';
  el.style.opacity = '1';
  el.style.marginTop = '16px';
}

function slideUp(el, cb) {
  el.style.maxHeight = '0';
  el.style.opacity = '0';
  el.style.marginTop = '0';
  setTimeout(function() {
    el.style.display = 'none';
    if (cb) cb();
  }, 400);
}

/* ── Business name confirmation row ────────────────────────────── */
function showBizConfirmed(name) {
  var row = document.getElementById('biz-name-confirmed');
  var display = document.getElementById('biz-name-display');
  if (!row || !display) return;
  display.textContent = name;
  slideDown(row);
}

function hideBizConfirmed() {
  var row = document.getElementById('biz-name-confirmed');
  if (!row) return;
  slideUp(row);
}

/* ── Business name override fields ─────────────────────────────── */
function showBizOverride(showCity, hideConfirmed) {
  var wrapper = document.getElementById('biz-name-override');
  var cityWrap = document.getElementById('override-city-wrapper');
  if (!wrapper) return;

  /* Only hide the confirmation row if explicitly requested (e.g. from "Not the right business?" click) */
  if (hideConfirmed !== false) {
    var confirmedRow = document.getElementById('biz-name-confirmed');
    if (confirmedRow) slideUp(confirmedRow);
  } else {
    /* Keep the green name visible but hide the "Not the right business?" button
       since the override fields are already showing */
    var wrongBtn = document.getElementById('biz-name-wrong-btn');
    if (wrongBtn) wrongBtn.style.display = 'none';
  }

  cityWrap.style.display = showCity ? 'block' : 'none';
  slideDown(wrapper);

  /* After the override section becomes visible, try to attach Google
     Places Autocomplete to the city field (it cannot attach while hidden). */
  if (showCity && typeof window._tryInitPlacesAutocomplete === 'function') {
    setTimeout(window._tryInitPlacesAutocomplete, 450);
  }

  /* Wire up listeners once */
  if (!_overrideListenerAdded) {
    _overrideListenerAdded = true;
    var nameInput = document.getElementById('override_biz_name');
    var cityInput = document.getElementById('override_biz_city');
    var bizHidden = document.getElementById('business_name');
    var locHidden = document.getElementById('business_location');

    nameInput.addEventListener('input', function() {
      bizHidden.value = nameInput.value;
      syncAuditBtnState();
    });
    cityInput.addEventListener('input', function() {
      locHidden.value = cityInput.value;
      locHidden._userEdited = true;
      syncAuditBtnState();
    });
  }

  /* On desktop, focus the business name field */
  if (!_isMobile) {
    setTimeout(function() {
      var urlField = document.getElementById('base_url');
      if (document.activeElement !== urlField) {
        document.getElementById('override_biz_name').focus();
      }
    }, 100);
  }
}

function hideBizOverride() {
  var wrapper = document.getElementById('biz-name-override');
  if (!wrapper) return;
  slideUp(wrapper);
}

/* ── Reset all business-related state ──────────────────────────── */
function resetBusinessState() {
  _detectedBizName = '';
  _detectedCity = '';
  _cityWasAutoDetected = false;
  document.getElementById('business_name').value = '';
  var locInput = document.getElementById('business_location');
  locInput.value = '';
  locInput._userEdited = false;
  document.getElementById('override_biz_name').value = '';
  document.getElementById('override_biz_city').value = '';
  var detectedLabel = document.getElementById('detected-biz-label');
  if (detectedLabel) {
    detectedLabel.style.display = 'none';
    detectedLabel.textContent = '';
  }
  /* Restore the "Not the right business?" button visibility for next detection */
  var wrongBtn = document.getElementById('biz-name-wrong-btn');
  if (wrongBtn) wrongBtn.style.display = '';
  hideBizConfirmed();
  hideBizOverride();
}

/* ── Enable/disable audit button based on current state ────────── */
function syncAuditBtnState() {
  var bizHidden = document.getElementById('business_name');
  var locHidden = document.getElementById('business_location');
  var hasBiz = bizHidden && bizHidden.value.trim();
  var hasLoc = locHidden && locHidden.value.trim();

  /* If we have both business name and location, enable */
  if (hasBiz && hasLoc) {
    enableAuditBtn();
    return;
  }

  /* If confirmed row is visible (business name set, city auto-detected), enable */
  var confirmedRow = document.getElementById('biz-name-confirmed');
  if (confirmedRow && confirmedRow.style.display !== 'none' && confirmedRow.style.opacity !== '0' && hasBiz && hasLoc) {
    enableAuditBtn();
    return;
  }

  /* If override is showing, require name + city from visible fields */
  var overrideWrap = document.getElementById('biz-name-override');
  if (overrideWrap && overrideWrap.style.display !== 'none' && overrideWrap.style.opacity !== '0') {
    var overrideName = document.getElementById('override_biz_name').value.trim();
    var cityWrap = document.getElementById('override-city-wrapper');
    var needsCity = cityWrap && cityWrap.style.display !== 'none';
    var overrideCity = document.getElementById('override_biz_city').value.trim();
    if (overrideName && (!needsCity || overrideCity)) {
      enableAuditBtn();
      return;
    }
  }

  disableAuditBtn();
}

/* ── "Not the right business?" click handler ──────────────────── */
document.getElementById('biz-name-wrong-btn').addEventListener('click', function() {
  /* Hide the confirmation row */
  hideBizConfirmed();

  /* Show override fields: city field only if city was NOT auto-detected */
  var needCityField = !_cityWasAutoDetected;
  showBizOverride(needCityField, true);

  /* Show the detected name as green text above the Business Name input */
  var detectedLabel = document.getElementById('detected-biz-label');
  if (detectedLabel && _detectedBizName) {
    detectedLabel.textContent = 'Detected: ' + _detectedBizName;
    detectedLabel.style.display = 'block';
  }

  /* Pre-fill the Business Name input with the detected name so user can edit */
  var overrideNameInput = document.getElementById('override_biz_name');
  if (overrideNameInput && _detectedBizName) {
    overrideNameInput.value = _detectedBizName;
    document.getElementById('business_name').value = _detectedBizName;
  } else {
    document.getElementById('business_name').value = '';
  }

  disableAuditBtn();
});

/* ── Auto-detect on blur -- debounced for mobile ─────────────── */
document.getElementById('base_url').addEventListener('blur', function() {
  var urlField = this;
  var url = urlField.value.trim();
  clearTimeout(_blurTimer);
  if (url && url !== _lastDetectedUrl) {
    var delay = _isMobile ? 400 : 150;
    _blurTimer = setTimeout(function() {
      if (document.activeElement === urlField) return;
      clearTimeout(_detectTimer);
      detectBusiness();
    }, delay);
  }
});

/* Auto-detect when user changes the URL field (debounced 600ms) */
document.getElementById('base_url').addEventListener('input', function() {
  clearTimeout(_detectTimer);
  clearTimeout(_blurTimer);
  _lastDetectedUrl = '';
  resetBusinessState();
  disableAuditBtn();
  _detectTimer = setTimeout(function() { detectBusiness(); }, 600);
});

/* Cancel blur detection if user returns to URL field */
document.getElementById('base_url').addEventListener('focus', function() {
  clearTimeout(_blurTimer);
});

/* Detect on page load if URL is already filled */
(function() {
  var url = document.getElementById('base_url').value.trim();
  if (url) {
    setTimeout(function() { detectBusiness(); }, 300);
  }
})();

function showAuditSpinner() {
  var btn = document.getElementById('auditBtn');
  if (!btn) return;
  btn.disabled = true;
  btn.style.opacity = '0.5';
  btn.style.cursor = 'not-allowed';
  btn.innerHTML = '<span class="btn-spinner"></span>';
}

function hideAuditSpinner() {
  var btn = document.getElementById('auditBtn');
  if (!btn) return;
  btn.innerHTML = 'Check my site';
}

function detectBusiness() {
  var url = document.getElementById('base_url').value.trim();
  if (!url || url === _lastDetectedUrl) return;
  _lastDetectedUrl = url;

  disableAuditBtn();
  resetBusinessState();
  showAuditSpinner();

  fetch('/api/detect-business', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest'
    },
    body: JSON.stringify({ url: url })
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    hideAuditSpinner();
    var bizHidden = document.getElementById('business_name');
    var locHidden = document.getElementById('business_location');
    var detectedName = (data.business_name || '').trim();
    var detectedLoc = (data.location || '').trim();

    _detectedBizName = detectedName;
    _detectedCity = detectedLoc;
    _cityWasAutoDetected = !!detectedLoc;

    if (detectedName) {
      /* Business name was detected -- show confirmation row */
      bizHidden.value = detectedName;

      if (detectedLoc) {
        /* Both name and city detected -- just show confirmed name, enable button */
        locHidden.value = detectedLoc;
        showBizConfirmed(detectedName);
        enableAuditBtn();
      } else {
        /* Name detected but no city -- show override with city field, green label on top */
        showBizConfirmed(detectedName);
        showBizOverride(true, false);
        /* Pre-fill detected name in override so user only needs to add city */
        document.getElementById('override_biz_name').value = detectedName;
        /* Show green detected label above the override fields */
        var detectedLabel = document.getElementById('detected-biz-label');
        if (detectedLabel) {
          detectedLabel.textContent = 'Detected: ' + detectedName;
          detectedLabel.style.display = 'block';
        }
      }
    } else {
      /* No business name detected -- skip confirmation, show override fields directly */
      if (detectedLoc) {
        locHidden.value = detectedLoc;
        _cityWasAutoDetected = true;
        showBizOverride(false); /* no city field needed */
      } else {
        showBizOverride(true); /* show both name and city fields */
      }
    }
  })
  .catch(function(err) {
    console.error('Detect failed:', err);
    hideAuditSpinner();
    /* Show override fields so user can enter both manually */
    showBizOverride(true);
  });
}

/* NOTE: URL normalization (auto-adding https://) and city validation are
   handled in the dashboard.js submit handler to avoid conflicts. */

/* ── City suggestions using Google AutocompleteService with custom dropdown ── */
(function() {
  var _serviceReady = false;
  var _autocompleteService = null;
  var _debounceTimer = null;

  function initService() {
    if (_serviceReady) return;
    if (typeof google === 'undefined' || !google.maps || !google.maps.places) return;
    _autocompleteService = new google.maps.places.AutocompleteService();
    _serviceReady = true;
    attachListener();
  }

  function attachListener() {
    var cityInput = document.getElementById('override_biz_city');
    if (!cityInput || cityInput._suggestionsAttached) return;
    cityInput._suggestionsAttached = true;

    cityInput.addEventListener('input', function() {
      var query = cityInput.value.trim();
      clearTimeout(_debounceTimer);
      if (query.length < 2) {
        hideDropdown();
        return;
      }
      _debounceTimer = setTimeout(function() { fetchSuggestions(query); }, 250);
    });

    /* Hide dropdown when input loses focus (with delay for click) */
    cityInput.addEventListener('blur', function() {
      setTimeout(hideDropdown, 200);
      /* Sync to hidden field */
      var locHidden = document.getElementById('business_location');
      if (locHidden) {
        locHidden.value = cityInput.value;
        locHidden._userEdited = true;
      }
      syncAuditBtnState();
    });
  }

  function fetchSuggestions(query) {
    if (!_autocompleteService) return;
    _autocompleteService.getPlacePredictions(
      { input: query, types: ['(cities)'] },
      function(predictions, status) {
        var dropdown = document.getElementById('city-dropdown');
        if (!dropdown) return;
        dropdown.innerHTML = '';
        if (status === google.maps.places.PlacesServiceStatus.OK && predictions && predictions.length > 0) {
          for (var i = 0; i < Math.min(predictions.length, 5); i++) {
            var item = document.createElement('div');
            item.textContent = predictions[i].description;
            item.style.cssText = 'padding:10px 14px;color:#e0e0e0;cursor:pointer;font-size:0.9rem;line-height:1.4;border-bottom:1px solid rgba(255,255,255,0.06);';
            item.setAttribute('data-value', predictions[i].description);
            item.addEventListener('mousedown', function(e) {
              e.preventDefault(); /* prevent blur from firing first */
              var cityInput = document.getElementById('override_biz_city');
              cityInput.value = this.getAttribute('data-value');
              var locHidden = document.getElementById('business_location');
              if (locHidden) {
                locHidden.value = cityInput.value;
                locHidden._userEdited = true;
              }
              hideDropdown();
              syncAuditBtnState();
            });
            item.addEventListener('mouseover', function() {
              this.style.backgroundColor = 'rgba(59,130,246,0.15)';
            });
            item.addEventListener('mouseout', function() {
              this.style.backgroundColor = 'transparent';
            });
            /* Touch support */
            item.addEventListener('touchstart', function(e) {
              e.preventDefault();
              var cityInput = document.getElementById('override_biz_city');
              cityInput.value = this.getAttribute('data-value');
              var locHidden = document.getElementById('business_location');
              if (locHidden) {
                locHidden.value = cityInput.value;
                locHidden._userEdited = true;
              }
              hideDropdown();
              syncAuditBtnState();
            });
            dropdown.appendChild(item);
          }
          dropdown.style.display = 'block';
        } else {
          hideDropdown();
        }
      }
    );
  }

  function hideDropdown() {
    var dropdown = document.getElementById('city-dropdown');
    if (dropdown) {
      dropdown.style.display = 'none';
      dropdown.innerHTML = '';
    }
  }

  /* Expose for showBizOverride to call after city field becomes visible */
  window._tryInitPlacesAutocomplete = function() {
    if (_serviceReady) {
      attachListener();
    } else {
      initService();
    }
  };

  /* Wait for Google Maps API to load */
  function waitForGoogleMaps() {
    if (typeof google !== 'undefined' && google.maps && google.maps.places) {
      initService();
    } else {
      var attempts = 0;
      var checkInterval = setInterval(function() {
        attempts++;
        if (typeof google !== 'undefined' && google.maps && google.maps.places) {
          clearInterval(checkInterval);
          initService();
        } else if (attempts > 50) {
          clearInterval(checkInterval);
        }
      }, 200);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', waitForGoogleMaps);
  } else {
    waitForGoogleMaps();
  }
})();

/* -- Show loading indicator on form submit ---- */
document.getElementById('runForm').addEventListener('submit', function() {
  var indicator = document.getElementById('loading-indicator');
  var btn = document.getElementById('submitBtn');
  if (indicator && btn) {
    indicator.style.display = 'block';
    btn.disabled = true;
  }
});
