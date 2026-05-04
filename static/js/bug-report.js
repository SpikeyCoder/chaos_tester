/* ── Bug Report Module ──────────────────────────────────────── */
var bugReport = (function() {
    var recentErrors = [];

    /* Capture console errors */
    var origError = console.error;
    console.error = function() {
        origError.apply(console, arguments);
        var msg = Array.prototype.slice.call(arguments).map(function(a) {
            return typeof a === 'string' ? a : JSON.stringify(a);
        }).join(' ');
        recentErrors.push({ message: msg.slice(0, 500), ts: Date.now() });
        if (recentErrors.length > 5) recentErrors.shift();
    };
    window.addEventListener('error', function(e) {
        recentErrors.push({ message: (e.message || '') + ' at ' + (e.filename || '') + ':' + (e.lineno || ''), ts: Date.now() });
        if (recentErrors.length > 5) recentErrors.shift();
    });

    function getTechContext() {
        var touch = navigator.maxTouchPoints > 0;
        return {
            url: window.location.href,
            pageName: document.title,
            deviceType: touch ? 'Touch / Mobile' : 'Desktop',
            userAgent: navigator.userAgent,
            platform: navigator.platform || 'Unknown',
            viewportSize: window.innerWidth + '\u00d7' + window.innerHeight,
            screenSize: screen.width + '\u00d7' + screen.height,
            timestamp: new Date().toISOString(),
            recentErrors: recentErrors.map(function(e) {
                return '[' + new Date(e.ts).toISOString() + '] ' + e.message;
            })
        };
    }

    async function captureScreenshot() {
        try {
            if (typeof html2canvas === 'undefined') {
                /* dynamically load html2canvas */
                await new Promise(function(resolve, reject) {
                    var s = document.createElement('script');
                    s.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
                    s.onload = resolve;
                    s.onerror = reject;
                    document.head.appendChild(s);
                });
            }
            /* Hide bug overlay + button so screenshot captures the page behind */
            var overlay = document.getElementById('bugOverlay');
            var bugBtn = document.querySelector('.bug-btn');
            overlay.style.display = 'none';
            if (bugBtn) bugBtn.style.display = 'none';
            /* Small delay to let the browser repaint */
            await new Promise(function(r) { setTimeout(r, 50); });
            var canvas = await html2canvas(document.body, { useCORS: true, scale: 1, logging: false, backgroundColor: '#0f172a' });
            /* Restore bug overlay + button */
            overlay.style.display = '';
            if (bugBtn) bugBtn.style.display = '';
            return canvas.toDataURL('image/png', 0.85);
        } catch (e) {
            console.warn('Screenshot capture failed:', e);
            /* Restore in case of error */
            var ov = document.getElementById('bugOverlay');
            var bb = document.querySelector('.bug-btn');
            if (ov) ov.style.display = '';
            if (bb) bb.style.display = '';
            return null;
        }
    }

    return {
        open: function() {
            document.getElementById('bugOverlay').classList.add('open');
            document.getElementById('bugFormView').style.display = '';
            document.getElementById('bugSuccessView').style.display = 'none';
            document.getElementById('bugError').style.display = 'none';
            document.getElementById('bugSubmitBtn').disabled = false;
        },
        close: function() {
            document.getElementById('bugOverlay').classList.remove('open');
            setTimeout(function() {
                document.getElementById('bugDesc').value = '';
                document.getElementById('bugCharCount').textContent = '0';
                document.getElementById('bugIsFeature').checked = false;
                document.getElementById('bugScreenshot').checked = true;
                document.getElementById('bugSubmitBtn').disabled = false;
                document.getElementById('bugSubmitBtn').innerHTML = 'Submit Report';
                document.getElementById('bugFormView').style.display = '';
                document.getElementById('bugSuccessView').style.display = 'none';
                bugReport.toggleType();
            }, 200);
        },
        toggleType: function() {
            var isFeature = document.getElementById('bugIsFeature').checked;
            document.getElementById('bugIcon').textContent = isFeature ? 'Idea' : 'Bug';
            document.getElementById('bugTitle').textContent = isFeature ? 'Feature Request' : 'Report a Bug';
            document.getElementById('bugDesc').placeholder = isFeature
                ? "Describe the feature you'd like to see..."
                : 'Describe the bug or issue you experienced...';
        },
        submit: async function(e) {
            e.preventDefault();
            var desc = document.getElementById('bugDesc').value.trim();
            if (!desc) return;

            var btn = document.getElementById('bugSubmitBtn');
            var errDiv = document.getElementById('bugError');
            btn.disabled = true;
            btn.innerHTML = '<span class="bug-spinner"></span> ' +
                (document.getElementById('bugScreenshot').checked ? 'Capturing & submitting...' : 'Submitting...');
            errDiv.style.display = 'none';

            try {
                var screenshotData = null;
                if (document.getElementById('bugScreenshot').checked) {
                    screenshotData = await captureScreenshot();
                }

                var resp = await fetch('/api/bug-report', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
                    body: JSON.stringify({
                        description: desc,
                        isFeatureRequest: document.getElementById('bugIsFeature').checked,
                        screenshotData: screenshotData,
                        technicalContext: getTechContext()
                    })
                });

                if (!resp.ok) {
                    var body = await resp.json().catch(function() { return {}; });
                    throw new Error(body.error || 'Server error (' + resp.status + ')');
                }

                document.getElementById('bugFormView').style.display = 'none';
                document.getElementById('bugSuccessView').style.display = '';
                var msg = document.createElement('div');
                msg.style.cssText = 'position:fixed;bottom:24px;right:24px;background:var(--success);color:var(--bg);padding:14px 20px;border-radius:8px;font-size:0.9rem;z-index:1000;animation:slideUp .3s ease-out;';
                msg.textContent = 'Report submitted successfully!';
                document.body.appendChild(msg);
                setTimeout(function() { msg.remove(); }, 3500);
                setTimeout(function() { bugReport.close(); }, 2000);
            } catch (err) {
                errDiv.textContent = err.message || 'Failed to submit. Please try again.';
                errDiv.style.display = '';
                btn.disabled = false;
                btn.innerHTML = 'Submit Report';
            }
        }
    };
})();

/* Character counter */
document.getElementById('bugDesc').addEventListener('input', function() {
    document.getElementById('bugCharCount').textContent = this.value.length;
});

/* Wire up floating bug button + modal controls (CSP-compliant; no inline handlers) */
(function initBugReportHandlers() {
    var openBtn = document.querySelector('.bug-btn');
    if (openBtn) openBtn.addEventListener('click', function() { bugReport.open(); });

    var overlay = document.getElementById('bugOverlay');
    if (overlay) {
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) bugReport.close();
        });
        var closeBtn = overlay.querySelector('.bug-modal-close');
        if (closeBtn) closeBtn.addEventListener('click', function() { bugReport.close(); });
    }

    var form = document.getElementById('bugForm');
    if (form) form.addEventListener('submit', bugReport.submit);

    var featureCheckbox = document.getElementById('bugIsFeature');
    if (featureCheckbox) featureCheckbox.addEventListener('change', bugReport.toggleType);
})();